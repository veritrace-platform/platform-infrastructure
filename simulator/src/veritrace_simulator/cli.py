"""Command line: replays a scenario for a fleet of devices.

    veritrace-simulator list
    veritrace-simulator run sustained-breach --sscc 089300010000000018 [--devices-per-shipment 2] [--loop]

The broker connection comes from MQTT_URL (default mqtt://localhost:1883), MQTT_USERNAME (default
fleet-simulator), and MQTT_PASSWORD.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
import time
from collections.abc import Callable, Sequence
from types import FrameType

from veritrace_simulator import scenario as scenarios
from veritrace_simulator.fleet import devices_for, timeline
from veritrace_simulator.publisher import MqttPublisher, PrintPublisher, Publisher, PublishError

log = logging.getLogger("veritrace_simulator")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stderr)
    if args.command == "list":
        for name in scenarios.bundled():
            print(f"{name:20} {scenarios.load(name).description}")
        return 0

    try:
        scenario = scenarios.load(args.scenario)
        devices = devices_for(args.sscc, args.devices_per_shipment, scenario.interval_seconds, args.seed)
    except ValueError as err:
        log.error("%s", err)
        return 2

    stop = threading.Event()
    _on_signals(stop.set)
    try:
        publisher: Publisher = PrintPublisher() if args.dry_run else _mqtt_publisher()
    except (PublishError, ValueError) as err:
        log.error("%s", err)
        return 1
    try:
        return play(scenario, devices, publisher, stop, loop=args.loop, max_ticks=args.ticks, realtime=not args.dry_run)
    except PublishError as err:
        log.error("%s", err)
        return 1
    finally:
        publisher.close()


def play(
    scenario: scenarios.Scenario,
    devices: list,
    publisher: Publisher,
    stop: threading.Event,
    *,
    loop: bool = False,
    max_ticks: int | None = None,
    realtime: bool = True,
    clock: Callable[[], float] = time.time,
) -> int:
    """Publish the scenario's readings, one tick per interval of wall-clock time unless realtime is false."""
    log.info(
        "playing %s (%.0f s) for %d device(s) on %d shipment(s)",
        scenario.name,
        scenario.duration_seconds,
        len(devices),
        len({d.sscc for d in devices}),
    )
    start = clock()
    played = 0
    while True:
        for tick in timeline(scenario, devices, int(start * 1000)):
            if realtime and stop.wait(max(0.0, start + tick.elapsed_seconds - clock())):
                return 0
            if stop.is_set():
                return 0
            for message in tick.messages:
                publisher.publish(message.device.topic, message.payload)
            temperatures = ", ".join(f"{m.payload['temperature_c']:.2f}" for m in tick.messages) or "silent"
            log.info("+%4.0fs %-20s %s", tick.elapsed_seconds, tick.phase, temperatures)
            played += 1
            if max_ticks is not None and played >= max_ticks:
                return 0
        if not loop:
            return 0
        start += scenario.duration_seconds


def _mqtt_publisher() -> MqttPublisher:
    password = os.environ.get("MQTT_PASSWORD", "")
    if not password:
        raise ValueError("MQTT_PASSWORD is required")
    return MqttPublisher(
        os.environ.get("MQTT_URL", "mqtt://localhost:1883"),
        os.environ.get("MQTT_USERNAME", "fleet-simulator"),
        password,
    )


def _on_signals(handler: Callable[[], None]) -> None:
    def handle(_signum: int, _frame: FrameType | None) -> None:
        handler()

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="veritrace-simulator", description="Replay cold-chain scenarios over MQTT.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list the bundled scenarios")
    run = commands.add_parser("run", help="replay a scenario")
    run.add_argument("scenario", help="name of a bundled scenario, or path to a scenario file")
    run.add_argument("--sscc", action="append", required=True, help="SSCC of a shipment to report on; repeatable")
    run.add_argument("--devices-per-shipment", type=int, default=1, help="devices on each shipment (default 1)")
    run.add_argument("--loop", action="store_true", help="repeat the scenario until stopped")
    run.add_argument("--ticks", type=int, help="stop after this many intervals")
    run.add_argument("--seed", type=int, help="seed of the temperature noise, for reproducible runs")
    run.add_argument("--dry-run", action="store_true", help="print the readings at once instead of publishing them")
    return parser
