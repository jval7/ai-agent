import asyncio
import dataclasses
import typing
import unittest.mock as mock

import pytest

import src.adapters.outbound.firestore.event_stream_adapter as event_stream_adapter_module
import src.adapters.outbound.firestore.paths as firestore_paths
import src.ports.event_stream_port as event_stream_port


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


class _FakeFirestoreClient:
    def __init__(self) -> None:
        self.conversations = _FakeCollection()
        self.scheduling_requests = _FakeCollection()
        self.scheduled_reminders = _FakeCollection()


def _patch_paths(monkeypatch: pytest.MonkeyPatch, fake_client: _FakeFirestoreClient) -> None:
    monkeypatch.setattr(
        firestore_paths,
        "tenant_conversations_collection",
        lambda _client, _tenant_id: fake_client.conversations,
    )
    monkeypatch.setattr(
        firestore_paths,
        "tenant_scheduling_requests_collection",
        lambda _client, _tenant_id: fake_client.scheduling_requests,
    )
    monkeypatch.setattr(
        firestore_paths,
        "tenant_scheduled_reminders_collection",
        lambda _client, _tenant_id: fake_client.scheduled_reminders,
    )


def test_subscribe_registers_listeners_and_emits_events_by_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeFirestoreClient()
    _patch_paths(monkeypatch, fake_client)
    adapter = event_stream_adapter_module.FirestoreEventStreamAdapter(client=mock.Mock())

    async def scenario() -> list[event_stream_port.StreamEvent]:
        subscription = adapter.subscribe(tenant_id="tenant-1")

        # Bootstrap snapshot (ignored)
        fake_client.conversations.fire([_FakeChange(_FakeDocumentRef("c1"))])
        fake_client.scheduling_requests.fire([_FakeChange(_FakeDocumentRef("req1"))])
        fake_client.scheduled_reminders.fire([_FakeChange(_FakeDocumentRef("rem1"))])

        # Post-bootstrap changes (emitted)
        fake_client.conversations.fire([_FakeChange(_FakeDocumentRef("c2"))])
        fake_client.scheduling_requests.fire([_FakeChange(_FakeDocumentRef("req2"))])
        fake_client.scheduled_reminders.fire([_FakeChange(_FakeDocumentRef("rem2"))])

        collected: list[event_stream_port.StreamEvent] = []
        for _ in range(3):
            collected.append(await asyncio.wait_for(subscription.queue.get(), timeout=0.1))

        subscription.teardown()
        assert fake_client.conversations.watch.unsubscribed is True
        assert fake_client.scheduling_requests.watch.unsubscribed is True
        assert fake_client.scheduled_reminders.watch.unsubscribed is True
        return collected

    events = asyncio.run(scenario())
    by_type = {event.type: event.payload for event in events}
    assert by_type == {
        "conversation.updated": {"id": "c2"},
        "scheduling_request.updated": {"id": "req2"},
        "reminder.updated": {"id": "rem2"},
    }


def test_subscribe_emits_one_event_per_change(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeFirestoreClient()
    _patch_paths(monkeypatch, fake_client)
    adapter = event_stream_adapter_module.FirestoreEventStreamAdapter(client=mock.Mock())

    async def scenario() -> list[str]:
        subscription = adapter.subscribe(tenant_id="tenant-1")
        try:
            fake_client.conversations.fire([])
            fake_client.conversations.fire(
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


def test_subscribe_drops_only_initial_bootstrap_per_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = _FakeFirestoreClient()
    _patch_paths(monkeypatch, fake_client)
    adapter = event_stream_adapter_module.FirestoreEventStreamAdapter(client=mock.Mock())

    async def scenario() -> asyncio.Queue[event_stream_port.StreamEvent]:
        subscription = adapter.subscribe(tenant_id="t")
        try:
            fake_client.conversations.fire([_FakeChange(_FakeDocumentRef("c1"))])
            fake_client.scheduling_requests.fire([_FakeChange(_FakeDocumentRef("r1"))])
            fake_client.scheduled_reminders.fire([_FakeChange(_FakeDocumentRef("re1"))])
            fake_client.conversations.fire([_FakeChange(_FakeDocumentRef("c2"))])
            fake_client.scheduling_requests.fire([_FakeChange(_FakeDocumentRef("r2"))])
            fake_client.scheduled_reminders.fire([_FakeChange(_FakeDocumentRef("re2"))])
            return subscription.queue
        finally:
            subscription.teardown()

    queue = asyncio.run(scenario())
    assert queue.qsize() == 3
