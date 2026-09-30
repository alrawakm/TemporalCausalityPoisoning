"""The correlation-rule baseline, and what it reveals about the corpus.

The language-model arm is compared against a clock-sorter. A reviewer will
object immediately that no deployed correlation engine reconstructs an incident
by sorting timestamps, so the null is a straw man. This script answers that
objection with a measurement instead of an argument.

It runs two deterministic responders over the same perturbed incidents:

  ordering  sorts by observed time, blames the earliest suspicious event
  rule      orders by action type, never consults the clock except to break ties

    python rule_baseline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soc import corpus, topology_hash, CHAIN_ACTIONS
from attack import perturb
from responder import OrderingResponder, RuleOrderResponder
from search import minimum_perturbation

N = 20
SEED = 20260920
GAP = (4000.0, 25000.0)
FAMILY = "disagreement"
MULTIPLES = (0.0, 0.5, 1.0, 1.25, 1.5, 1.75, 2.0)


def evaluate(shared_vocab: bool):
    incidents = corpus(N, SEED, gap_range_ms=GAP, shared_vocab=shared_vocab)
    clock = OrderingResponder("time")
    rule = RuleOrderResponder()

    plan = []
    for inc in incidents:
        pred, src = minimum_perturbation(inc, clock, FAMILY)
        if pred is not None:
            plan.append((inc, pred, src))

    out = []
    for mult in MULTIPLES:
        c_ok = r_ok = 0
        for inc, pred, src in plan:
            p = inc if mult == 0.0 else perturb(inc, FAMILY, pred * mult, target_source=src)
            c_ok += clock.respond(p).origin == inc.origin
            r_ok += rule.respond(p).origin == inc.origin
        n = len(plan)
        out.append((mult, round(100 * c_ok / n), round(100 * r_ok / n)))
    return len(plan), len(incidents), out


def vocab_overlap(shared_vocab: bool):
    incidents = corpus(N, SEED, gap_range_ms=GAP, shared_vocab=shared_vocab)
    amb = [e.action for inc in incidents for e in inc.events if e.cause == "ambient"]
    coll = sum(1 for x in amb if x in CHAIN_ACTIONS)
    return coll, len(amb)


def main():
    print("Temporal Causality Poisoning - deterministic baselines")
    print("topology %s | seed %d | N=%d | family %s" % (topology_hash(), SEED, N, FAMILY))
    print()

    results = {}
    for shared, label in ((False, "A  vocabularies disjoint"),
                          (True,  "B  vocabularies shared")):
        kept, total, rows = evaluate(shared)
        coll, amb = vocab_overlap(shared)
        results[shared] = rows
        print("  %s" % label)
        print("  incidents with a clock-sorter prediction: %d of %d" % (kept, total))
        print("  ambient events using a chain action type: %d of %d (%.0f%%)"
              % (coll, amb, 100.0 * coll / amb))
        print()
        print("    %-10s %14s %14s" % ("multiple", "clock correct", "rule correct"))
        print("    " + "-" * 42)
        for mult, c, r in rows:
            print("    %-10s %13d%% %13d%%" % ("%.2fx" % mult, c, r))
        print()

    a_one = dict((m, r) for m, _, r in results[False])[1.0]
    b_one = dict((m, r) for m, _, r in results[True])[1.0]
    print("  Rule baseline at 1.0x:  A %d%%   B %d%%" % (a_one, b_one))
    print()
    if a_one == 100 and b_one < 100:
        print("  The rule's immunity was a property of the corpus, not of the rule.")
        print("  Once benign events share the chain's vocabulary, knowing the")
        print("  vocabulary stops being sufficient and ordering evidence is needed")
        print("  again, so the perturbation reaches a typed correlation rule too.")
    elif b_one == 100:
        print("  The rule survives both conditions. The attack does not threaten a")
        print("  typed correlation engine, and the paper has to say so plainly.")


if __name__ == "__main__":
    main()
