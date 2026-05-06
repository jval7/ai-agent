import asyncio
import dataclasses
import typing

import src.ports.event_stream_port as event_stream_port
import src.services.use_cases.event_stream_service as event_stream_service_module

# ---------------------------------------------------------------------------
# Fakes — shared by all tests
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _FakeDocumentRef:
    id: str


@dataclasses.dataclass
class _FakeChange:
    document: _FakeDocumentRef


class _FakeWatch:
    def __init__(self) -> None:
        self.unsubscribed = False

    def unsubscribe(self) -> None:
        self.unsubscribed = True


class _FakeCollection:
    def __init__(self) -> None:
        self.callback: typing.Callable[..., None] | None = None
        self.watch = _FakeWatch()

    def on_snapshot(self, callback: typing.Callable[..., None]) -> _FakeWatch:
        self.callback = callback
        return self.watch

    def fire(self, changes: list[_FakeChange]) -> None:
        if self.callback is None:
            raise AssertionError("on_snapshot callback was never registered")
        self.callback([], changes, None)


class _FakeEventStreamAdapter(event_stream_port.EventStreamPort):
    """In-memory adapter that mirrors the Firestore adapter's behaviour.

    Registers three fake collections and supports firing Firestore-like
    change events against them so the full bootstrap-skip / enqueue logic
    can be exercised without touching real Firestore.
    """

    def __init__(self) -> None:
        self.conversations = _FakeCollection()
        self.scheduling_requests = _FakeCollection()
        self.scheduled_reminders = _FakeCollection()

    def subscribe(self, tenant_id: str) -> event_stream_port.EventSubscription:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[event_stream_port.StreamEvent] = asyncio.Queue()
        watches: list[_FakeWatch] = []

        def enqueue(event: event_stream_port.StreamEvent) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def make_callback(event_type: str) -> typing.Callable[..., None]:
            state = {"bootstrapped": False}

            def callback(
                _col_snapshot: typing.Any,
                changes: typing.Any,
                _read_time: typing.Any,
            ) -> None:
                if not state["bootstrapped"]:
                    state["bootstrapped"] = True
                    return
                for change in changes:
                    document_id = change.document.id
                    enqueue(
                        event_stream_port.StreamEvent(type=event_type, payload={"id": document_id})
                    )

            return callback

        watches.append(self.conversations.on_snapshot(make_callback("conversation.updated")))
        watches.append(
            self.scheduling_requests.on_snapshot(make_callback("scheduling_request.updated"))
        )
        watches.append(self.scheduled_reminders.on_snapshot(make_callback("reminder.updated")))

        def teardown() -> None:
            for watch in watches:
                watch.unsubscribe()

        return event_stream_port.EventSubscription(queue=queue, teardown=teardown)


def _make_service() -> tuple[
    event_stream_service_module.EventStreamService, _FakeEventStreamAdapter
]:
    adapter = _FakeEventStreamAdapter()
    service = event_stream_service_module.EventStreamService(event_stream=adapter)
    return service, adapter


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_subscribe_registers_listeners_and_emits_events_by_type() -> None:
    service, adapter = _make_service()

    async def scenario() -> list[event_stream_port.StreamEvent]:
        subscription = service.subscribe(tenant_id="tenant-1")

        # Bootstrap snapshot (ignored)
        adapter.conversations.fire([_FakeChange(_FakeDocumentRef("c1"))])
        adapter.scheduling_requests.fire([_FakeChange(_FakeDocumentRef("req1"))])
        adapter.scheduled_reminders.fire([_FakeChange(_FakeDocumentRef("rem1"))])

        # Post-bootstrap changes (emitted)
        adapter.conversations.fire([_FakeChange(_FakeDocumentRef("c2"))])
        adapter.scheduling_requests.fire([_FakeChange(_FakeDocumentRef("req2"))])
        adapter.scheduled_reminders.fire([_FakeChange(_FakeDocumentRef("rem2"))])

        collected: list[event_stream_port.StreamEvent] = []
        for _ in range(3):
            collected.append(await asyncio.wait_for(subscription.queue.get(), timeout=0.1))

        subscription.teardown()
        assert adapter.conversations.watch.unsubscribed is True
        assert adapter.scheduling_requests.watch.unsubscribed is True
        assert adapter.scheduled_reminders.watch.unsubscribed is True
        return collected

    events = asyncio.run(scenario())
    by_type = {event.type: event.payload for event in events}
    assert by_type == {
        "conversation.updated": {"id": "c2"},
        "scheduling_request.updated": {"id": "req2"},
        "reminder.updated": {"id": "rem2"},
    }


def test_subscribe_emits_one_event_per_change() -> None:
    service, adapter = _make_service()

    async def scenario() -> list[str]:
        subscription = service.subscribe(tenant_id="tenant-1")
        try:
            adapter.conversations.fire([])
            adapter.conversations.fire(
                [
                    _FakeChange(_FakeDocumentRef("a")),
                    _FakeChange(_FakeDocumentRef("b")),
                    _FakeChange(_FakeDocumentRef("c")),
                ]
            )
            ids: list[str] = []
            for _ in range(3):
                event = await asyncio.wait_for(subscription.queue.get(), timeout=0.1)
                ids.append(event.payload["id"])
            return ids
        finally:
            subscription.teardown()

    assert asyncio.run(scenario()) == ["a", "b", "c"]


def test_subscribe_drops_only_initial_bootstrap_per_collection() -> None:
    service, adapter = _make_service()

    async def scenario() -> asyncio.Queue[event_stream_port.StreamEvent]:
        subscription = service.subscribe(tenant_id="t")
        try:
            adapter.conversations.fire([_FakeChange(_FakeDocumentRef("c1"))])
            adapter.scheduling_requests.fire([_FakeChange(_FakeDocumentRef("r1"))])
            adapter.scheduled_reminders.fire([_FakeChange(_FakeDocumentRef("re1"))])
            adapter.conversations.fire([_FakeChange(_FakeDocumentRef("c2"))])
            adapter.scheduling_requests.fire([_FakeChange(_FakeDocumentRef("r2"))])
            adapter.scheduled_reminders.fire([_FakeChange(_FakeDocumentRef("re2"))])
            return subscription.queue
        finally:
            subscription.teardown()

    queue = asyncio.run(scenario())
    assert queue.qsize() == 3
