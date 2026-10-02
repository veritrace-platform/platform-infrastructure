"""Command line of the demonstration kit.

    veritrace-demo seed         register the demo companies and create their data (idempotent)
    veritrace-demo scenario     run the M1 acceptance scenario
    veritrace-demo watch EMAIL  print the notifications of a demo account, optionally following SSCCs
    veritrace-demo accounts     list the demo accounts

The API is reached at API_URL (default http://localhost:8000, the gateway). Demo accounts use DEMO_PASSWORD. The
scenario publishes readings to MQTT_URL (default mqtt://localhost:1883) as MQTT_USERNAME (default fleet-simulator)
with MQTT_PASSWORD.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
from collections.abc import Sequence
from types import FrameType

from veritrace_demo import fixtures, scenario
from veritrace_demo.client import Api, ApiError
from veritrace_demo.notifications import Listener, websocket_url
from veritrace_demo.seed import SeedError, seed

MIN_PASSWORD_LENGTH = 12


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="    %(message)s", stream=sys.stdout)
    # Requests are reported by the steps; the HTTP client's own log would repeat them.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.command == "accounts":
        print_accounts()
        return 0
    try:
        password = _password()
    except ValueError as err:
        print(err, file=sys.stderr)
        return 2
    api_url = os.environ.get("API_URL", "http://localhost:8000")
    try:
        match args.command:
            case "seed":
                return run_seed(api_url, password)
            case "scenario":
                settings = scenario.Settings(
                    api_url=api_url,
                    password=password,
                    mqtt_url=os.environ.get("MQTT_URL", "mqtt://localhost:1883"),
                    mqtt_username=os.environ.get("MQTT_USERNAME", "fleet-simulator"),
                    mqtt_password=_required("MQTT_PASSWORD"),
                )
                return scenario.run(settings)
            case _:
                return watch(api_url, password, args.email, args.sscc)
    except ValueError as err:
        print(err, file=sys.stderr)
        return 2


def run_seed(api_url: str, password: str) -> int:
    api = Api(api_url)
    try:
        seeded = seed(api, password)
    except (SeedError, ApiError, OSError) as err:
        print(f"The seed failed: {err}", file=sys.stderr)
        return 1
    finally:
        api.close()
    print(f"Seeded: {seeded.summary()}.")
    print("Every demo account signs in with DEMO_PASSWORD; `veritrace-demo accounts` lists them.")
    return 0


def watch(api_url: str, password: str, email: str, ssccs: list[str]) -> int:
    """Print the notifications of an account until interrupted."""
    stop = threading.Event()

    def handle(_signum: int, _frame: FrameType | None) -> None:
        stop.set()

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    api = Api(api_url)
    try:
        token = api.login(email, password)
        listener = Listener(
            websocket_url(api_url), token, email, on_message=lambda _n, m: print(_describe(m), flush=True)
        )
    except (ApiError, OSError) as err:
        print(f"Cannot watch as {email}: {err}", file=sys.stderr)
        return 1
    finally:
        api.close()
    for sscc in ssccs:
        listener.subscribe(sscc)
    print(f"Watching the notifications of {email}; press Ctrl+C to stop.", flush=True)
    while not stop.wait(1):
        if listener.close_code is not None:
            print(f"The server closed the connection ({listener.close_code}).")
            return 1
    listener.close()
    return 0


def _describe(message: dict) -> str:
    data = message.get("data") or {}
    match message["type"]:
        case "telemetry.reading":
            reading = f"{data['sscc']}  {data['temperature_celsius']} °C  ({data['device_id']})"
            return f"{message['sent_at']}  reading   {reading}"
        case "cold_chain.breach_confirmed":
            return (
                f"{message['sent_at']}  BREACH    {data['sscc']}  {data['temperature_celsius']} °C outside "
                f"{data['min_temp_celsius']}–{data['max_temp_celsius']} °C since {data['started_at']}"
            )
        case "cold_chain.breach_resolved":
            return (
                f"{message['sent_at']}  resolved  {data['sscc']}  after {data['duration_seconds']} s, "
                f"peak {data['extreme_temperature_celsius']} °C"
            )
        case "shipment.recalled":
            return f"{message['sent_at']}  RECALL    {data['sscc']}  lot {data['lot_number']}: {data['reason']}"
        case "subscribed" | "unsubscribed":
            return f"{message['sent_at']}  {message['type']}  {data['sscc']}"
        case "error":
            return f"{message['sent_at']}  error     {data['code']}: {data['message']}"
    return f"{message['sent_at']}  {message['type']}"


def print_accounts() -> None:
    print(f"{'Company':12} {'Role':18} {'Email':30} Name")
    for company in fixtures.COMPANIES:
        for a in company.accounts:
            print(f"{company.code:12} {a.role:18} {a.email:30} {a.full_name}")
    print("\nEvery account signs in with DEMO_PASSWORD from platform-infrastructure/.env.")


def _password() -> str:
    password = _required("DEMO_PASSWORD")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"DEMO_PASSWORD must have at least {MIN_PASSWORD_LENGTH} characters")
    return password


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="veritrace-demo", description="VeriTrace demonstration kit.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed", help="register the demo companies and create their data (idempotent)")
    commands.add_parser("scenario", help="run the M1 acceptance scenario")
    watch_cmd = commands.add_parser("watch", help="print the notifications of a demo account")
    watch_cmd.add_argument("email", help="the account, for example admin@sgfresh.example")
    watch_cmd.add_argument("--sscc", action="append", default=[], help="also follow this SSCC's live readings")
    commands.add_parser("accounts", help="list the demo accounts")
    return parser
