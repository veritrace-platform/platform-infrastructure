import dataclasses
import datetime as dt

import pytest
from veritrace_simulator.fleet import devices_for, timeline

from veritrace_demo import evaluation

SSCC = "089300010000000018"


def readings_of(journey, episode):
    """The noise-free temperatures of an episode, as (seconds, °C)."""
    quiet = dataclasses.replace(journey.scenario, jitter_celsius=0.0)
    devices = devices_for([SSCC], 1, quiet.interval_seconds, seed=1)
    return [
        (tick.elapsed_seconds, m.payload["temperature_c"])
        for tick in timeline(quiet, devices, 0)
        for m in tick.messages
        if episode.start_seconds <= tick.elapsed_seconds < episode.end_seconds
    ]


def longest_excursion(readings):
    longest, start = 0.0, None
    for t, c in readings:
        if evaluation.T_MIN <= c <= evaluation.T_MAX:
            start = None
        else:
            start = t if start is None else start
            longest = max(longest, t - start)
    return longest


def test_a_seed_builds_the_same_journey():
    assert evaluation.build(7, 20) == evaluation.build(7, 20)
    assert evaluation.build(7, 20) != evaluation.build(8, 20)


@pytest.mark.parametrize("seed", range(10))
def test_episodes_breach_exactly_when_expected(seed):
    journey = evaluation.build(seed, 20)
    kinds = {e.kind for e in journey.episodes}
    assert len(journey.episodes) == 20
    assert kinds <= set(evaluation.KINDS)
    for episode in journey.episodes:
        excursion = longest_excursion(readings_of(journey, episode))
        if episode.breach_expected:
            assert excursion >= evaluation.CONFIRM_SECONDS, episode
        else:
            assert excursion == 0, episode


def test_episodes_follow_each_other_with_steady_stretches():
    journey = evaluation.build(3, 12)
    ends = [e.end_seconds for e in journey.episodes]
    starts = [e.start_seconds for e in journey.episodes]
    assert starts[0] == 15 * 60
    assert all(nxt - end >= 10 * 60 for end, nxt in zip(ends, starts[1:], strict=False))
    assert journey.duration_seconds - ends[-1] >= 10 * 60


def test_a_journey_stays_within_the_past_that_ingestion_accepts():
    with pytest.raises(ValueError, match="longer than 20 hours"):
        evaluation.build(1, 80)


def test_match_assigns_warnings_and_incidents_to_episodes():
    journey = evaluation.build(5, 4)
    started = 1_790_000_000.0

    def at(seconds):
        return dt.datetime.fromtimestamp(started + seconds, dt.UTC).isoformat().replace("+00:00", "Z")

    first, second = journey.episodes[0], journey.episodes[1]
    warnings = [
        {"issued_at": at(first.start_seconds + 60), "outcome": "BREACHED", "lead_time_seconds": 180},
        {"issued_at": at(first.start_seconds + 600), "outcome": "CLEARED", "lead_time_seconds": None},
        {"issued_at": at(second.start_seconds + 30), "outcome": None, "lead_time_seconds": None},
        {"issued_at": at(5), "outcome": "CLEARED", "lead_time_seconds": None},  # before any episode
    ]
    incidents = [{"started_at": at(first.start_seconds + 240)}]
    outcomes = evaluation.match(journey, started, warnings, incidents)
    assert [(o.incidents, o.warning, o.lead_time_seconds) for o in outcomes[:3]] == [
        (1, "BREACHED", 180),
        (0, "OPEN", None),
        (0, "none", None),
    ]
