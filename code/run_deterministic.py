"""Run the pipeline against the deterministic responders.

Spends no quota. Two purposes. It validates the mechanism end to end before any
paid call, and it produces the graph-and-rules baseline that the paper compares
the language-model responder against.

The sweep is over the inter-event gap, because an earlier run showed the gap
bounds the answer: an adversary who wants a later suspicious event to appear
first must close the distance between them. The interesting quantity is
therefore a relationship rather than a single number.

    python run_deterministic.py
"""

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soc import corpus, topology_hash, NTP_STEP_THRESHOLD_MS, KERBEROS_SKEW_S
from attack import FAMILIES, TIER1_MS, TIER2_MS
from responder import OrderingResponder, IntervalResponder
from search import baseline_correct, minimum_perturbation, score

N = 30
SEED = 20260920

# Inter-event gaps, from fast automated tooling to slow hands-on operation.
GAPS = [
    ("50 ms - 200 ms", (50.0, 200.0)),
    ("1 s - 5 s", (1000.0, 5000.0)),
    ("4 s - 25 s", (4000.0, 25000.0)),
    ("30 s - 120 s", (30000.0, 120000.0)),
]


def sweep_gap(responder, label, gap_label, gap_range):
    incidents = corpus(N, SEED, gap_range_ms=gap_range)
    usable = [i for i in incidents if baseline_correct(i, responder)]
    if not usable:
        print("  %-16s %-16s  no correct baseline, excluded" % (gap_label, "-"))
        return

    minima, sources, material = [], {}, 0
    for inc in usable:
        m, src = minimum_perturbation(inc, responder, "offset")
        if m is not None:
            minima.append(m)
            sources[src] = sources.get(src, 0) + 1
            if score(inc, responder, "offset", m, source=src).material:
                material += 1

    if not minima:
        print("  %-16s  no flip within %.0f s" % (gap_label, TIER2_MS / 1000))
        return

    med = statistics.median(minima)
    t1 = sum(1 for m in minima if m <= TIER1_MS) / len(minima)
    top = max(sources, key=sources.get) if sources else "-"
    print("  %-16s %9.0f %9.0f %9.0f %7.0f%% %7.0f%% %6d/%-3d  %s" % (
        gap_label, med, min(minima), max(minima),
        100 * t1, 100 * material / len(minima),
        len(minima), len(usable), top))


def header(label):
    print()
    print("=" * 92)
    print("  " + label)
    print("=" * 92)
    print("  %-16s %9s %9s %9s %8s %8s %10s  %s" %
          ("gap", "median", "min", "max", "tier1", "material", "flipped", "best source"))
    print("  " + "-" * 88)


def main():
    print("Temporal Causality Poisoning - deterministic sweep")
    print("topology %s | seed %d | N=%d per cell" % (topology_hash(), SEED, N))
    print("tier1 <= %.0f ms (NTP discards as noise) | tier2 <= %.0f s (Kerberos skew)"
          % (TIER1_MS, KERBEROS_SKEW_S))
    print("all magnitudes in milliseconds, family = offset")

    for responder, label in (
        (OrderingResponder("time"), "ORDERING responder, trusts source time"),
        (OrderingResponder("received"), "ORDERING responder, trusts ingest time"),
        (IntervalResponder(NTP_STEP_THRESHOLD_MS), "INTERVAL responder (defense), half-width 128 ms"),
    ):
        header(label)
        for gap_label, gap_range in GAPS:
            sweep_gap(responder, label, gap_label, gap_range)


if __name__ == "__main__":
    main()
