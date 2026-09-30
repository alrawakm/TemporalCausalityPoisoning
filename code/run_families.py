"""The full family matrix, at one gap, against all three responders.

The offset sweep suggested two things that cannot be claimed from it alone: that
ordering by collector receipt defeats the attack, and that the interval defense
does not work. Neither survives unless every family is tested, because `delay`
and `disagreement` act on the ingest time rather than the source time.

    python run_families.py
"""

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soc import corpus, topology_hash, NTP_STEP_THRESHOLD_MS
from attack import FAMILIES, ANALOGUE, TIER1_MS, TIER2_MS
from responder import OrderingResponder, IntervalResponder
from search import baseline_correct, minimum_perturbation, score

N = 30
SEED = 20260920
GAP = (4000.0, 25000.0)          # the ordinary hands-on pace
GAP_LABEL = "4 s - 25 s"


def cell(responder, incidents, family):
    usable = [i for i in incidents if baseline_correct(i, responder)]
    if not usable:
        return None, 0, 0, 0, "-", 0
    minima, material, sources, abstain = [], 0, {}, 0
    for inc in usable:
        m, src = minimum_perturbation(inc, responder, family)
        if m is not None:
            minima.append(m)
            sources[src] = sources.get(src, 0) + 1
            if score(inc, responder, family, m, source=src).material:
                material += 1
        else:
            # No misattribution reachable. Did it abstain instead?
            a, _ = minimum_perturbation(inc, responder, family, objective="any")
            if a is not None:
                abstain += 1
    if not minima:
        return None, 0, len(usable), 0, "-", abstain
    top = max(sources, key=sources.get)
    return statistics.median(minima), len(minima), len(usable), material, top, abstain


def main():
    print("Temporal Causality Poisoning - family matrix")
    print("topology %s | seed %d | N=%d | gap %s" % (topology_hash(), SEED, N, GAP_LABEL))
    print("tier1 <= %.0f ms | tier2 <= %.0f ms" % (TIER1_MS, TIER2_MS))

    incidents = corpus(N, SEED, gap_range_ms=GAP)

    responders = [
        (OrderingResponder("time"), "order by source time"),
        (OrderingResponder("received"), "order by ingest time"),
        (IntervalResponder(NTP_STEP_THRESHOLD_MS), "interval, 128 ms"),
    ]

    for responder, label in responders:
        print()
        print("=" * 86)
        print("  %s" % label)
        print("=" * 86)
        print("  %-14s %11s %12s %9s %9s  %s" %
              ("family", "median ms", "misattrib", "material", "abstain", "source"))
        print("  " + "-" * 82)
        for fam in FAMILIES:
            med, mis, usable, material, src, abst = cell(responder, incidents, fam)
            print("  %-14s %11s %8d/%-3d %9s %9s  %s" % (
                fam,
                "%.0f" % med if med is not None else "none",
                mis, usable,
                "%d" % material if mis else "-",
                "%d" % abst if abst else "-",
                src))


if __name__ == "__main__":
    main()
