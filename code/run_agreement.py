"""The cross-clock agreement responder, and the perturbation that defeats it.

Added 2026-11-07. Two questions are answered here and they have different
answers.

The first is whether a parameter-free discipline escapes the interval defense's
problem. It does. Agreement asks only whether the two observed clocks still
order the suspicious events the same way, so there is no half-width to size
wrongly, and it keeps its unperturbed accuracy while never naming a wrong
origin.

The second is whether that costs the adversary anything. It does not. A
coherent shift moves both clocks of one source by the same amount in the same
direction, which leaves the two orderings in agreement, and it misattributes at
the same magnitude the undefended source-time ordering pays.

    python run_agreement.py
"""

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soc import corpus, topology_hash
from attack import FAMILIES
from responder import OrderingResponder, AgreementResponder
from search import baseline_correct, minimum_perturbation

N = 30
SEED = 20260920
GAP = (4000.0, 25000.0)
GAP_LABEL = "4 s - 25 s"
TESTED = tuple(f for f in FAMILIES if f != "zone") + ("coherent",)


def cell(responder, incidents, family):
    usable = [i for i in incidents if baseline_correct(i, responder)]
    if not usable:
        return None, 0, 0, 0
    minima, abstain = [], 0
    for inc in usable:
        m, _ = minimum_perturbation(inc, responder, family)
        if m is not None:
            minima.append(m)
        else:
            a, _ = minimum_perturbation(inc, responder, family, objective="any")
            if a is not None:
                abstain += 1
    med = statistics.median(minima) if minima else None
    return med, len(minima), len(usable), abstain


def main():
    print("Cross-clock agreement and the coherent perturbation")
    print("topology %s | seed %d | N=%d | gap %s" %
          (topology_hash(), SEED, N, GAP_LABEL))
    print("zone is excluded: a whole-hour shift is inadmissible, see the paper")
    incidents = corpus(N, SEED, gap_range_ms=GAP)

    for responder, label in ((OrderingResponder("time"), "order by source time"),
                             (OrderingResponder("received"), "order by ingest time"),
                             (AgreementResponder(), "cross-clock agreement")):
        ok = sum(1 for i in incidents if baseline_correct(i, responder))
        print()
        print("=" * 72)
        print("  %s   unperturbed: %d/%d correct" % (label, ok, N))
        print("=" * 72)
        print("  %-14s %11s %12s %9s" %
              ("family", "median ms", "misattrib", "abstain"))
        print("  " + "-" * 68)
        for fam in TESTED:
            med, mis, usable, ab = cell(responder, incidents, fam)
            print("  %-14s %11s %8d/%-3d %9s" % (
                fam,
                "%.0f" % med if med is not None else "none",
                mis, usable, ab if ab else "-"))


if __name__ == "__main__":
    main()
