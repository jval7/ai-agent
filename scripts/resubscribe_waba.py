"""Re-subscribe all (or one) WhatsApp Business Accounts to the canonical
webhook fields, including ``smb_message_echoes``. Without that field, Meta
does not deliver the messages the professional sends from the WhatsApp app
on their phone, so the inbox panel never sees them.

Reads connections directly from Firestore (``tenants/*/whatsapp_connection/default``)
and posts to ``/{waba}/subscribed_apps`` with the explicit
``subscribed_fields=["messages","smb_message_echoes"]`` body.

The previous subscription (default fields, set on Embedded Signup) is
replaced by this one. Idempotent: re-running it keeps the same state.

Requires:
    - ADC with Firestore access (``GOOGLE_APPLICATION_CREDENTIALS``)
    - Optional ``META_API_VERSION`` env var (defaults to ``v23.0``)

Usage:
    uv run python scripts/resubscribe_waba.py
    uv run python scripts/resubscribe_waba.py --tenant-id <id>
    uv run python scripts/resubscribe_waba.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
import typing

import google.cloud.firestore as google_cloud_firestore
import httpx

import src.adapters.outbound.firestore.paths as firestore_paths

_DEFAULT_META_API_VERSION = "v23.0"
_SUBSCRIBED_FIELDS = ["messages", "smb_message_echoes"]


def _iter_connected_wabas(
    client: google_cloud_firestore.Client,
    tenant_id_filter: str | None,
) -> typing.Iterator[tuple[str, str, str]]:
    """Yield (tenant_id, access_token, business_account_id) for every
    CONNECTED whatsapp_connection in Firestore."""
    query = client.collection_group(firestore_paths.WHATSAPP_CONNECTION_COLLECTION)
    for snapshot in query.stream():
        data = snapshot.to_dict()
        if data is None:
            continue
        if data.get("status") != "CONNECTED":
            continue
        tenant_ref = snapshot.reference.parent.parent
        if tenant_ref is None:
            continue
        tenant_id = data.get("tenant_id") or tenant_ref.id
        if tenant_id_filter is not None and tenant_id != tenant_id_filter:
            continue
        access_token = data.get("access_token")
        business_account_id = data.get("business_account_id")
        if not isinstance(access_token, str) or not access_token:
            print(f"  skip tenant={tenant_id}: missing access_token")
            continue
        if not isinstance(business_account_id, str) or not business_account_id:
            print(f"  skip tenant={tenant_id}: missing business_account_id")
            continue
        yield tenant_id, access_token, business_account_id


def _resubscribe_waba(
    http_client: httpx.Client,
    meta_api_version: str,
    access_token: str,
    business_account_id: str,
) -> None:
    """POST /{waba}/subscribed_apps with explicit subscribed_fields. Raises
    on non-2xx or when Meta does not echo ``success: true``."""
    url = f"https://graph.facebook.com/{meta_api_version}/{business_account_id}/subscribed_apps"
    response = http_client.post(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        json={"subscribed_fields": _SUBSCRIBED_FIELDS},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise RuntimeError(f"meta did not return success=true: {payload!r}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-subscribe WhatsApp Business Accounts to messages + smb_message_echoes."
    )
    parser.add_argument(
        "--tenant-id",
        dest="tenant_id",
        help="Re-subscribe only this tenant. Default: all CONNECTED tenants.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="List affected tenants without calling Meta.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    meta_api_version = os.environ.get("META_API_VERSION", _DEFAULT_META_API_VERSION)
    firestore_client = google_cloud_firestore.Client()

    summary_ok: list[str] = []
    summary_fail: list[tuple[str, str]] = []

    with httpx.Client(timeout=15.0) as http_client:
        for tenant_id, access_token, business_account_id in _iter_connected_wabas(
            firestore_client, args.tenant_id
        ):
            if args.dry_run:
                print(
                    f"[DRY] would re-subscribe tenant={tenant_id} "
                    f"waba={business_account_id} fields={_SUBSCRIBED_FIELDS}"
                )
                summary_ok.append(tenant_id)
                continue
            try:
                _resubscribe_waba(
                    http_client=http_client,
                    meta_api_version=meta_api_version,
                    access_token=access_token,
                    business_account_id=business_account_id,
                )
                print(f"[OK]  tenant={tenant_id} waba={business_account_id}")
                summary_ok.append(tenant_id)
            except (httpx.HTTPError, RuntimeError) as exc:
                print(f"[ERR] tenant={tenant_id} waba={business_account_id}: {exc}")
                summary_fail.append((tenant_id, str(exc)))

    print()
    print(f"Done. {len(summary_ok)} ok, {len(summary_fail)} failed.")
    if summary_fail:
        for tenant_id, reason in summary_fail:
            print(f"  - {tenant_id}: {reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
