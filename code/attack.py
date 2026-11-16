"""The six perturbation families.

Each one is a transformation of the observed times, and each has a natural
analogue that occurs without an adversary. A family without an analogue would be
anomalous on its own terms and would fail the plausibility bound, so the table
in the paper is a design constraint rather than a presentation choice.

Magnitude is always in milliseconds and is always checked against the tier it
claims to sit in. Tier 1 is below the NTP step threshold of 128 ms, where an
offset is discarded by the protocol as noise. Tier 2 is below the Kerberos skew
tolerance of 300 s, where authentication keeps working and nothing in the sync
stack reacts.
"""

from __future__ import annotations

import copy
import random
from dataclasses import replace

from soc import Incident, Event, NTP_STEP_THRESHOLD_MS, KERBEROS_SKEW_S

TIER1_MS = NTP_STEP_THRESHOLD_MS          # 128
TIER2_MS = KERBEROS_SKEW_S * 1000.0       # 300_000

FAMILIES = ("offset", "zone", "delay", "duplicate", "tie", "disagreement")

# Added 2026-11-07. `coherent` moves both observed clocks of one source by the
# same amount in the same direction, which leaves a cross-clock agreement check
# with nothing to disagree about. Its analogue is a source whose clock is wrong
# and whose collection time is stamped relative to that clock. It is deliberately
# NOT in FAMILIES: the five-family matrix is a published result and this
# perturbation exists to attack the agreement responder, not to join that set.
EXTRA_FAMILIES = ("coherent",)

ANALOGUE = {
    "offset": "clock drift on one source",
    "zone": "a misconfigured time zone",
    "delay": "queue backlog at the collector",
    "duplicate": "at-least-once delivery",
    "tie": "coarse clock resolution",
    "disagreement": "late arrival, event time and collection time conflict",
}


def tier_of(magnitude_ms: float) -> int:
    if abs(magnitude_ms) <= TIER1_MS:
        return 1
    if abs(magnitude_ms) <= TIER2_MS:
        return 2
    return 3   # outside the admissible range; reference only


def perturb(inc: Incident, family: str, magnitude_ms: float,
            target_source: str | None = None, seed: int = 0) -> Incident:
    """Return a perturbed copy. The original is never mutated.

    `target_source` names the source whose clock the adversary influences. When
    omitted, the source carrying the last chain event is chosen, because moving
    the control's apparent time is the transformation that turns a response into
    a cause.
    """
    if family not in FAMILIES + EXTRA_FAMILIES:
        raise ValueError("unknown family: " + family)

    rng = random.Random(seed)
    out = copy.deepcopy(inc)

    if target_source is None:
        last = max((e for e in out.events if e.cause == "adversary"),
                   key=lambda e: e.t_true_ms)
        target_source = last.source

    hit = [e for e in out.events if e.source == target_source]

    if family == "offset":
        for e in hit:
            e.t_source_ms -= magnitude_ms

    elif family == "zone":
        # A whole-hour shift, scaled so the caller still controls magnitude.
        for e in hit:
            e.t_source_ms -= magnitude_ms

    elif family == "delay":
        for e in hit:
            e.t_ingest_ms += magnitude_ms

    elif family == "duplicate":
        # The event is re-delivered later. The copy carries the same source
        # time and a later ingest time, which is what at-least-once delivery
        # produces.
        extra = []
        nid = max(e.eid for e in out.events) + 1
        for e in hit:
            if e.cause == "adversary":
                d = replace(e, eid=nid, t_ingest_ms=e.t_ingest_ms + magnitude_ms)
                extra.append(d)
                nid += 1
        out.events.extend(extra)

    elif family == "tie":
        # Coarse resolution: source times collapse onto a shared grid, so the
        # only remaining order is ingest order.
        grid = max(magnitude_ms, 1.0)
        for e in hit:
            e.t_source_ms = round(e.t_source_ms / grid) * grid

    elif family == "disagreement":
        for e in hit:
            e.t_source_ms -= magnitude_ms
            e.t_ingest_ms += magnitude_ms / 2.0

    elif family == "coherent":
        # Both clocks, same size, same direction. An agreement check sees no
        # disagreement, so this is the attack on that defense.
        for e in hit:
            e.t_source_ms -= magnitude_ms
            e.t_ingest_ms -= magnitude_ms

    return out


def max_true_span_ms(inc: Incident) -> float:
    """How far apart the chain events really are. Context for a magnitude."""
    ts = [e.t_true_ms for e in inc.events if e.cause == "adversary"]
    return max(ts) - min(ts)
