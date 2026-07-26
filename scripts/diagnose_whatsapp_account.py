"""Diagnose the health of every connected WhatsApp Business Account.

For each ``whatsapp_connection`` in Firestore, queries Meta Graph API with the
stored access token and reports:

- The Business Portfolio that OWNS the WABA (``owner_business_info``): id and
  name. This answers "which Facebook profile/portfolio holds the account" when
  Embedded Signup created the WABA under an unexpected login.
- ``health_status``: per-entity messaging health (BUSINESS / WABA / APP /
  PHONE_NUMBER), each with ``can_send_message`` and Meta's own error codes,
  descriptions and suggested solutions. This pinpoints WHICH layer is blocked.
- ``account_review_status`` of the WABA and phone-number status fields
  (``status``, ``quality_rating``, ``name_status``, ``messaging_limit_tier``).
- A direct link to Meta Business Support Home for the owning portfolio, where
  restrictions are appealed.

Read-only: performs GET requests only; never mutates Meta or Firestore state.

Requires:
    - ADC with Firestore access (``GOOGLE_APPLICATION_CREDENTIALS``)
    - Optional ``META_API_VERSION`` env var (defaults to ``v23.0``)
    - ``GOOGLE_CLOUD_PROJECT`` to pick which env's Firestore to read from.

Usage:
    # via Makefile:
    make diagnose-whatsapp GOOGLE_CLOUD_PROJECT=ai-agent-calendar-2603011621
    make diagnose-whatsapp GOOGLE_CLOUD_PROJECT=<id> ARGS="--tenant-id <id>"

    # direct:
    GOOGLE_CLOUD_PROJECT=<id> uv run python scripts/diagnose_whatsapp_account.py
    uv run python scripts/diagnose_whatsapp_account.py --tenant-id <id>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import typing

import google.cloud.firestore as google_cloud_firestore
import httpx

_DEFAULT_META_API_VERSION = "v23.0"
# Mirrors WHATSAPP_CONNECTION_COLLECTION in src/adapters/outbound/firestore/paths.py.
# Duplicated here so the script stays import-free and runs as a standalone CLI.
_WHATSAPP_CONNECTION_COLLECTION = "whatsapp_connection"

_WABA_FIELDS = "id,name,account_review_status,ownership_type,owner_business_info"
_PHONE_FIELDS = (
    "display_phone_number,verified_name,status,quality_rating,"
    "name_status,messaging_limit_tier,code_verification_status"
)


class _GraphApiError(RuntimeError):
    """Graph API returned an error payload; carries Meta's structured error."""

    def __init__(self, error: dict[str, typing.Any]) -> None:
        self.error = error
        super().__init__(json.dumps(error, ensure_ascii=False))


def _iter_connections(
    client: google_cloud_firestore.Client,
    tenant_id_filter: str | None,
) -> typing.Iterator[dict[str, typing.Any]]:
    """Yield connection dicts (any status) with a resolved ``tenant_id`` key."""
    query = client.collection_group(_WHATSAPP_CONNECTION_COLLECTION)
    for snapshot in query.stream():
        data = snapshot.to_dict()
        if data is None:
            continue
        tenant_ref = snapshot.reference.parent.parent
        if tenant_ref is None:
            continue
        data["tenant_id"] = data.get("tenant_id") or tenant_ref.id
        if tenant_id_filter is not None and data["tenant_id"] != tenant_id_filter:
            continue
        yield data


def _graph_get(
    http_client: httpx.Client,
    meta_api_version: str,
    access_token: str,
    path: str,
    fields: str,
) -> dict[str, typing.Any]:
    """GET a Graph API node. Raises _GraphApiError with Meta's structured
    error payload (code, subcode, user message) instead of a bare HTTP error,
    because those codes ARE the diagnosis (190 = token invalid, 131031 =
    account locked, 10/200 = permission)."""
    url = f"https://graph.facebook.com/{meta_api_version}/{path}"
    response = http_client.get(
        url,
        params={"fields": fields},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected non-object response: {payload!r}")
    error = payload.get("error")
    if isinstance(error, dict):
        raise _GraphApiError(error)
    response.raise_for_status()
    return payload


def _print_graph_error(prefix: str, exc: _GraphApiError) -> None:
    code = exc.error.get("code")
    subcode = exc.error.get("error_subcode")
    message = exc.error.get("message")
    user_msg = exc.error.get("error_user_msg")
    print(f"{prefix} Graph API error code={code} subcode={subcode}")
    print(f"{prefix}   message: {message}")
    if user_msg:
        print(f"{prefix}   detail:  {user_msg}")
    if code == 190:
        print(
            f"{prefix}   hint: token invalid/revoked. A portfolio-level restriction or a"
            f" password/session reset invalidates Embedded Signup tokens; the tenant must"
            f" re-run Embedded Signup once the account is recovered."
        )
    if code in (10, 200):
        print(
            f"{prefix}   hint: permission error. The app may have lost access to the WABA"
            f" (e.g. removed from the portfolio, or the portfolio is restricted)."
        )


def _print_health_status(health: dict[str, typing.Any]) -> None:
    print(
        f"    health.overall_status: {health.get('can_send_message', health.get('overall_status'))}"
    )
    entities = health.get("entities")
    if not isinstance(entities, list):
        return
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        entity_type = entity.get("entity_type")
        entity_id = entity.get("id")
        can_send = entity.get("can_send_message")
        print(f"      - {entity_type} {entity_id}: can_send_message={can_send}")
        additional_info = entity.get("additional_info")
        if isinstance(additional_info, list):
            for info in additional_info:
                print(f"          info: {info}")
        errors = entity.get("errors")
        if isinstance(errors, list):
            for error in errors:
                if not isinstance(error, dict):
                    continue
                print(
                    f"          error [{error.get('error_code')}]: {error.get('error_description')}"
                )
                solution = error.get("possible_solution")
                if solution:
                    print(f"          solution: {solution}")


def _diagnose_waba(
    http_client: httpx.Client,
    meta_api_version: str,
    access_token: str,
    business_account_id: str,
) -> None:
    print(f"  WABA {business_account_id}:")
    try:
        waba = _graph_get(
            http_client, meta_api_version, access_token, business_account_id, _WABA_FIELDS
        )
    except _GraphApiError as exc:
        _print_graph_error("    [ERR]", exc)
    else:
        print(f"    name:                  {waba.get('name')}")
        print(f"    account_review_status: {waba.get('account_review_status')}")
        print(f"    ownership_type:        {waba.get('ownership_type')}")
        owner = waba.get("owner_business_info")
        if isinstance(owner, dict):
            owner_id = owner.get("id")
            print(f"    owner portfolio:       id={owner_id} name={owner.get('name')!r}")
            print(
                f"    appeal / support page: "
                f"https://business.facebook.com/business-support-home/?business_id={owner_id}"
            )
            print(
                "    NOTE: only a Facebook login with admin access to THAT portfolio can"
                " open the support page and appeal. The portfolio name above is the clue"
                " to find which login owns it."
            )
        else:
            print("    owner portfolio:       (not returned — token may lack scope)")

    try:
        health = _graph_get(
            http_client, meta_api_version, access_token, business_account_id, "health_status"
        )
    except _GraphApiError as exc:
        _print_graph_error("    [ERR health_status]", exc)
        return
    health_status = health.get("health_status")
    if isinstance(health_status, dict):
        _print_health_status(health_status)
    else:
        print("    health_status: (not returned)")


def _diagnose_phone(
    http_client: httpx.Client,
    meta_api_version: str,
    access_token: str,
    phone_number_id: str,
) -> None:
    print(f"  Phone {phone_number_id}:")
    try:
        phone = _graph_get(
            http_client, meta_api_version, access_token, phone_number_id, _PHONE_FIELDS
        )
    except _GraphApiError as exc:
        _print_graph_error("    [ERR]", exc)
        return
    print(f"    display_phone_number:     {phone.get('display_phone_number')}")
    print(f"    verified_name:            {phone.get('verified_name')}")
    print(f"    status:                   {phone.get('status')}")
    print(f"    quality_rating:           {phone.get('quality_rating')}")
    print(f"    name_status:              {phone.get('name_status')}")
    print(f"    messaging_limit_tier:     {phone.get('messaging_limit_tier')}")
    print(f"    code_verification_status: {phone.get('code_verification_status')}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose WhatsApp Business Account health and portfolio ownership."
    )
    parser.add_argument(
        "--tenant-id",
        dest="tenant_id",
        help="Diagnose only this tenant. Default: every connection in Firestore.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    meta_api_version = os.environ.get("META_API_VERSION", _DEFAULT_META_API_VERSION)
    firestore_client = google_cloud_firestore.Client()

    # Print the resolved GCP project up-front. The Firestore SDK and gcloud CLI
    # resolve project independently — gcloud config is not enough — so it is
    # easy to think you are running against prod while the SDK is hitting dev.
    print(f"GCP project (Firestore): {firestore_client.project}")
    print(f"Meta API version:        {meta_api_version}")
    print()

    found = 0
    with httpx.Client(timeout=15.0) as http_client:
        for connection in _iter_connections(firestore_client, args.tenant_id):
            found += 1
            tenant_id = connection["tenant_id"]
            status = connection.get("status")
            print(f"tenant={tenant_id} connection.status={status}")
            access_token = connection.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                print("  [skip] missing access_token")
                print()
                continue
            business_account_id = connection.get("business_account_id")
            if isinstance(business_account_id, str) and business_account_id:
                _diagnose_waba(http_client, meta_api_version, access_token, business_account_id)
            else:
                print("  [skip] missing business_account_id")
            phone_number_id = connection.get("phone_number_id")
            if isinstance(phone_number_id, str) and phone_number_id:
                _diagnose_phone(http_client, meta_api_version, access_token, phone_number_id)
            else:
                print("  [skip] missing phone_number_id")
            print()

    if found == 0:
        print("No whatsapp_connection documents matched.")
        sys.exit(1)


if __name__ == "__main__":
    main()
