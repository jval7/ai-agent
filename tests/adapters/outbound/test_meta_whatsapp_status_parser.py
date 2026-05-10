"""Tests for the Meta webhook ``statuses[]`` parser.

The parser walks the same payload shape used for inbound messages but reads
the lifecycle callbacks Meta emits for outbound messages (sent → delivered →
read, or failed). The fixtures here are real-shaped payloads taken from the
WhatsApp Cloud API documentation.
"""

import src.adapters.outbound.whatsapp_meta.meta_whatsapp_provider_adapter as meta_adapter_mod
import src.infra.settings as app_settings


def _settings() -> app_settings.Settings:
    return app_settings.Settings.model_construct(
        meta_app_id="app",
        meta_app_secret="secret",
        meta_redirect_uri="https://example.test/cb",
        meta_api_version="v22.0",
    )


def _adapter() -> meta_adapter_mod.MetaWhatsappProviderAdapter:
    return meta_adapter_mod.MetaWhatsappProviderAdapter(_settings())


def test_parse_message_status_events_reads_failed_with_error_details() -> None:
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "1234567890",
                                "phone_number_id": "phone-123",
                            },
                            "statuses": [
                                {
                                    "id": "wamid.HBgL...XYZ",
                                    "status": "failed",
                                    "timestamp": "1746810000",
                                    "recipient_id": "34645136263",
                                    "errors": [
                                        {
                                            "code": 131026,
                                            "title": "Message undeliverable",
                                            "message": "Message undeliverable",
                                            "error_data": {
                                                "details": (
                                                    "Receiver is incapable of "
                                                    "receiving this message"
                                                ),
                                            },
                                        }
                                    ],
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    events = _adapter().parse_message_status_events(payload)

    assert len(events) == 1
    event = events[0]
    assert event.phone_number_id == "phone-123"
    assert event.provider_message_id == "wamid.HBgL...XYZ"
    assert event.recipient_id == "34645136263"
    assert event.status == "failed"
    assert event.timestamp_epoch_seconds == 1746810000
    assert event.error_code == 131026
    assert event.error_title == "Message undeliverable"
    assert event.error_message == "Receiver is incapable of receiving this message"
    # The composite event id keeps lifecycle callbacks deduped per status.
    assert event.provider_event_id == "wamid.HBgL...XYZ:failed"


def test_parse_message_status_events_reads_delivered_and_read() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "phone-1"},
                            "statuses": [
                                {
                                    "id": "wamid.AAA",
                                    "status": "delivered",
                                    "timestamp": "1746810010",
                                    "recipient_id": "57311",
                                },
                                {
                                    "id": "wamid.AAA",
                                    "status": "read",
                                    "timestamp": "1746810050",
                                    "recipient_id": "57311",
                                },
                            ],
                        },
                    }
                ]
            }
        ]
    }

    events = _adapter().parse_message_status_events(payload)

    statuses = [event.status for event in events]
    assert statuses == ["delivered", "read"]
    assert events[0].error_code is None
    assert events[1].error_code is None


def test_parse_message_status_events_returns_empty_when_no_statuses() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "phone-1"},
                            "messages": [
                                {
                                    "id": "wamid.X",
                                    "from": "57311",
                                    "type": "text",
                                    "text": {"body": "hi"},
                                }
                            ],
                        },
                    }
                ]
            }
        ]
    }

    assert _adapter().parse_message_status_events(payload) == []


def test_parse_message_status_events_skips_unknown_status_values() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "phone-1"},
                            "statuses": [
                                {
                                    "id": "wamid.A",
                                    "status": "queued",  # Not part of the contract
                                    "recipient_id": "57311",
                                }
                            ],
                        },
                    }
                ]
            }
        ]
    }

    assert _adapter().parse_message_status_events(payload) == []


def test_parse_message_status_events_handles_malformed_payload_gracefully() -> None:
    assert _adapter().parse_message_status_events({}) == []
    assert _adapter().parse_message_status_events({"entry": "not-a-list"}) == []
    assert _adapter().parse_message_status_events({"entry": [None]}) == []
    assert _adapter().parse_message_status_events({"entry": [{"changes": [None]}]}) == []
