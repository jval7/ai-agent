import asyncio
import dataclasses
import typing

import google.cloud.firestore as google_cloud_firestore

import src.adapters.outbound.firestore.paths as firestore_paths


@dataclasses.dataclass(frozen=True)
class StreamEvent:
    type: str
    payload: dict[str, str]


@dataclasses.dataclass(frozen=True)
class EventSubscription:
    queue: asyncio.Queue[StreamEvent]
    teardown: typing.Callable[[], None]


class EventStreamService:
    def __init__(self, firestore_client: google_cloud_firestore.Client) -> None:
        self._client = firestore_client

    def subscribe(self, tenant_id: str) -> EventSubscription:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue()
        watches: list[typing.Any] = []

        def enqueue(event: StreamEvent) -> None:
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
                    enqueue(StreamEvent(type=event_type, payload={"id": document_id}))

            return callback

        conversations_collection = firestore_paths.tenant_conversations_collection(
            self._client, tenant_id
        )
        scheduling_requests_collection = firestore_paths.tenant_scheduling_requests_collection(
            self._client, tenant_id
        )
        scheduled_reminders_collection = firestore_paths.tenant_scheduled_reminders_collection(
            self._client, tenant_id
        )

        watches.append(conversations_collection.on_snapshot(make_callback("conversation.updated")))
        watches.append(
            scheduling_requests_collection.on_snapshot(make_callback("scheduling_request.updated"))
        )
        watches.append(
            scheduled_reminders_collection.on_snapshot(make_callback("reminder.updated"))
        )

        def teardown() -> None:
            for watch in watches:
                watch.unsubscribe()

        return EventSubscription(queue=queue, teardown=teardown)
