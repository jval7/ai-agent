import src.ports.event_stream_port as event_stream_port

# Re-export domain types so existing callers don't need to change import paths.
StreamEvent = event_stream_port.StreamEvent
EventSubscription = event_stream_port.EventSubscription


class EventStreamService:
    def __init__(self, event_stream: event_stream_port.EventStreamPort) -> None:
        self._event_stream = event_stream

    def subscribe(self, tenant_id: str) -> event_stream_port.EventSubscription:
        return self._event_stream.subscribe(tenant_id)
