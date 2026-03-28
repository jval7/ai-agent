"""Delete Google Calendar events for a given date range.

Reads the Google Calendar OAuth refresh_token from Firestore, refreshes it,
and uses the resulting access_token to list and delete events.

Requires:
    - .secrets/make_credentials.env with OWNER_EMAIL and OWNER_PASSWORD
    - ADC with Firestore access (service account or gcloud auth)

Usage:
    uv run python scripts/cleanup_calendar_events.py
    uv run python scripts/cleanup_calendar_events.py --date 2026-03-27
    uv run python scripts/cleanup_calendar_events.py --from-date 2026-03-01 --to-date 2026-03-31
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys
import typing

import google.cloud.firestore as google_cloud_firestore
import httpx

# ---------------------------------------------------------------------------
# Load .secrets/make_credentials.env
# ---------------------------------------------------------------------------
_SECRETS_DIR = pathlib.Path(__file__).resolve().parent.parent / ".secrets"


def _load_env_file(path: pathlib.Path) -> None:
    """Load KEY=VALUE lines into os.environ (does not overwrite existing vars)."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(_SECRETS_DIR / "make_credentials.env")
_load_env_file(_SECRETS_DIR / "make_api_base.env")

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "")
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "")

_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"


# ---------------------------------------------------------------------------
# Backend auth
# ---------------------------------------------------------------------------
def _login(base_url: str, email: str, password: str) -> str:
    """Login to the backend and return the access token."""
    response = httpx.post(
        f"{base_url}/v1/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token: str = response.json()["access_token"]
    return token


# ---------------------------------------------------------------------------
# Google Calendar token via Firestore + OAuth refresh
# ---------------------------------------------------------------------------
_GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _get_calendar_credentials_from_firestore(
    tenant_id: str,
) -> tuple[str, str, str]:
    """Read calendar_id, refresh_token from Firestore and refresh to get access_token.

    Returns (access_token, calendar_id, tenant_id).
    """
    client = google_cloud_firestore.Client()
    doc_ref = (
        client.collection("tenants")
        .document(tenant_id)
        .collection("google_calendar_connection")
        .document("default")
    )
    doc = doc_ref.get()
    if not doc.exists:
        print(f"No Google Calendar connection found for tenant {tenant_id}")
        sys.exit(1)

    data = doc.to_dict()
    if data is None:
        print("Google Calendar connection document is empty")
        sys.exit(1)

    calendar_id = data.get("calendar_id")
    refresh_token = data.get("refresh_token")
    if not calendar_id or not refresh_token:
        print(f"Missing calendar_id or refresh_token in Firestore. calendar_id={calendar_id}")
        sys.exit(1)

    # Get client_id and client_secret from backend secret
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        # Try loading from GCP secret
        try:
            import subprocess

            gcloud_cmd = [
                "gcloud",
                "secrets",
                "versions",
                "access",
                "latest",
                "--secret=AI_AGENT_APP_CONFIG_JSON",
            ]
            result = subprocess.run(  # noqa: S603
                gcloud_cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                secret_data = json.loads(result.stdout)
                client_id = secret_data.get("GOOGLE_OAUTH_CLIENT_ID", "")
                client_secret = secret_data.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
        except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired):
            pass

    if not client_id or not client_secret:
        print("GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are required.")
        print("Set them as env vars or ensure gcloud can access AI_AGENT_APP_CONFIG_JSON secret.")
        sys.exit(1)

    # Refresh the token
    response = httpx.post(
        _GOOGLE_OAUTH_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    response.raise_for_status()
    access_token: str = response.json()["access_token"]

    return access_token, calendar_id, tenant_id


def _list_events(
    gc_token: str,
    calendar_id: str,
    time_min: datetime.datetime,
    time_max: datetime.datetime,
) -> list[dict[str, typing.Any]]:
    """List all events in [time_min, time_max) from the given calendar."""
    params: dict[str, str | int] = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 250,
        "q": "Psi. Alejandra Escobar",
    }
    headers = {"Authorization": f"Bearer {gc_token}"}
    response = httpx.get(
        f"{_CALENDAR_API_BASE}/calendars/{calendar_id}/events",
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    items: list[dict[str, typing.Any]] = response.json().get("items", [])
    return items


def _delete_event(gc_token: str, calendar_id: str, event_id: str) -> None:
    """Delete a single calendar event by ID."""
    headers = {"Authorization": f"Bearer {gc_token}"}
    response = httpx.delete(
        f"{_CALENDAR_API_BASE}/calendars/{calendar_id}/events/{event_id}",
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _format_event_time(event: dict[str, typing.Any]) -> tuple[str, str]:
    start_raw = event.get("start", {})
    end_raw = event.get("end", {})
    start = start_raw.get("dateTime") or start_raw.get("date") or "?"
    end = end_raw.get("dateTime") or end_raw.get("date") or "?"
    return start, end


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete Google Calendar events for a given date range.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run python scripts/cleanup_calendar_events.py\n"
            "  uv run python scripts/cleanup_calendar_events.py --date 2026-03-27\n"
            "  uv run python scripts/cleanup_calendar_events.py --from-date 2026-03-01 --to-date 2026-03-31\n"
        ),
    )
    parser.add_argument(
        "--date",
        help="Single date to clean up (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--from-date",
        dest="from_date",
        help="Start date of range (YYYY-MM-DD). Use together with --to-date.",
    )
    parser.add_argument(
        "--to-date",
        dest="to_date",
        help="End date of range, inclusive (YYYY-MM-DD). Use together with --from-date.",
    )
    return parser.parse_args()


def _resolve_time_range(
    args: argparse.Namespace,
) -> tuple[datetime.datetime, datetime.datetime]:
    """Return (time_min, time_max) as timezone-aware datetimes."""
    local_tz = datetime.datetime.now().astimezone().tzinfo

    if args.from_date and args.to_date:
        time_min = datetime.datetime.fromisoformat(args.from_date).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=local_tz
        )
        time_max = datetime.datetime.fromisoformat(args.to_date).replace(
            hour=23, minute=59, second=59, microsecond=0, tzinfo=local_tz
        )
    elif args.date:
        time_min = datetime.datetime.fromisoformat(args.date).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=local_tz
        )
        time_max = time_min + datetime.timedelta(days=1)
    else:
        # Default: current month
        today = datetime.date.today()
        time_min = datetime.datetime(today.year, today.month, 1, 0, 0, 0, tzinfo=local_tz)
        next_month = today.month % 12 + 1
        next_month_year = today.year + (1 if next_month == 1 else 0)
        time_max = datetime.datetime(next_month_year, next_month, 1, 0, 0, 0, tzinfo=local_tz)

    return time_min, time_max


def main() -> None:
    args = _parse_args()
    time_min, time_max = _resolve_time_range(args)

    print(f"Searching for events between {time_min.isoformat()} and {time_max.isoformat()}")

    # --- Step 1: login to get tenant_id ---
    if not OWNER_EMAIL or not OWNER_PASSWORD:
        print(
            "OWNER_EMAIL and OWNER_PASSWORD are required.\n"
            "Set them in .secrets/make_credentials.env or as environment variables."
        )
        sys.exit(1)

    print(f"Logging in to backend at {API_BASE}...")
    backend_token = _login(API_BASE, OWNER_EMAIL, OWNER_PASSWORD)

    # Extract tenant_id from JWT (no verification needed, it's our own token)
    import base64

    jwt_payload = backend_token.split(".")[1]
    jwt_payload += "=" * (4 - len(jwt_payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(jwt_payload))
    tenant_id = claims["tenant_id"]

    # --- Step 2: get calendar credentials from Firestore ---
    print(f"Reading calendar credentials from Firestore (tenant={tenant_id[:8]}...)...")
    gc_token, calendar_id, _ = _get_calendar_credentials_from_firestore(tenant_id)
    print(f"Calendar ID: {calendar_id}")

    # --- Step 3: list events ---
    print("Fetching events from Google Calendar...")
    events = _list_events(gc_token, calendar_id, time_min, time_max)

    if not events:
        print("No events found in that date range.")
        return

    print(f"\nFound {len(events)} event(s):\n")
    for i, event in enumerate(events, 1):
        start, end = _format_event_time(event)
        summary = event.get("summary") or "(no title)"
        status = event.get("status", "")
        organizer = event.get("organizer", {}).get("email", "")
        print(f"  {i:2d}. {summary}")
        print(f"      {start} -> {end}")
        if status:
            print(f"      status={status}  organizer={organizer}")
        print()

    # --- Step 4: confirm deletion ---
    try:
        confirm = input(f"Delete these {len(events)} event(s)? (y/N): ").strip().lower()
    except EOFError:
        confirm = ""

    if confirm not in ("y", "yes"):
        print("Cancelled.")
        return

    # --- Step 5: delete ---
    deleted = 0
    failed = 0
    for event in events:
        event_id: str = event["id"]
        summary = event.get("summary") or "(no title)"
        try:
            _delete_event(gc_token, calendar_id, event_id)
            deleted += 1
            print(f"  Deleted: {summary}")
        except httpx.HTTPStatusError as exc:
            failed += 1
            print(f"  Error deleting '{summary}': HTTP {exc.response.status_code}")

    print(f"\n{deleted}/{len(events)} event(s) deleted.", end="")
    if failed:
        print(f" {failed} failed.")
    else:
        print()


if __name__ == "__main__":
    main()
