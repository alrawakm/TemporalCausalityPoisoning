"""The language-model arm.

The deterministic sweep produced a prediction rather than a finding: the minimum
effective perturbation equals the inter-event gap, ratio 1.02 to 1.03 across
four orders of magnitude. That is what a pure clock-sorter does, and it is
arithmetic rather than a result.

This experiment tests the prediction. A responder that reads only the clock
should flip at 1.0 times the predicted minimum and not below it. A responder
that reads meaning should deviate, and the deviation is the finding.

So the design does not bisect. Bisection costs about nineteen calls per
incident. Testing at multiples of a known prediction costs four, and answers a
sharper question.

    python run_llm.py --dry-run          show the cost and one prompt, spend nothing
    python run_llm.py --mock             validate the pipeline against a fake sorter
    python run_llm.py --provider openai  run it for real
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soc import corpus, topology_hash
from attack import perturb, ANALOGUE
from responder import LLMResponder, OrderingResponder
from search import minimum_perturbation
from llm_client import CachedClient, MockSorterClient

N = 20
SEED = 20260920
GAP = (4000.0, 25000.0)
FAMILY = "disagreement"       # the only family that beats both clock orderings
MULTIPLES = (0.0, 0.5, 1.0, 1.25, 1.5, 1.75, 2.0)
REPEATS = 3        # the responder is stochastic; rates need repeats


def predicted_minimum(inc) -> tuple[float | None, str | None]:
    """The clock-sorter's cost for this incident. The null hypothesis."""
    return minimum_perturbation(inc, OrderingResponder("time"), FAMILY)


def run(client, show_flags: bool, dry_run: bool = False,
        shared_vocab: bool = False, multiples=MULTIPLES, repeats=REPEATS):
    incidents = corpus(N, SEED, gap_range_ms=GAP, shared_vocab=shared_vocab)
    responder = LLMResponder(client, show_flags=show_flags)

    plan = []
    for inc in incidents:
        pred, src = predicted_minimum(inc)
        if pred is None:
            continue
        plan.append((inc, pred, src))

    calls = len(plan) * len(multiples) * repeats
    print("incidents with a clock-sorter prediction: %d of %d" % (len(plan), len(incidents)))
    print("magnitudes per incident: %s x predicted" % (", ".join(str(m) for m in multiples)))
    print("repeats per cell: %d" % repeats)
    print("total calls: %d" % calls)

    if dry_run:
        inc, pred, src = plan[0]
        print("\npredicted minimum for incident 0: %.0f ms on source %s" % (pred, src))
        print("true origin (never shown): %s" % inc.origin)
        print("\n--- prompt as the responder sees it ---")
        print(responder.render(perturb(inc, FAMILY, pred, target_source=src)))
        return None

    rows = []
    for inc, pred, src in plan:
        base_origin = None
        for mult in multiples:
          for rep in range(repeats):
            mag = pred * mult
            # The perturbation is deterministic in its seed, so repeats vary the
            # responder rather than the stimulus. That is the quantity that
            # needs averaging: the same prompt answered more than once.
            p = inc if mult == 0.0 else perturb(inc, FAMILY, mag, target_source=src)
            v = responder.respond(p, nonce=rep)
            if mult == 0.0 and rep == 0:
                base_origin = v.origin
            rows.append({
                "rep": rep,
                "iid": inc.iid, "mult": mult, "magnitude_ms": mag,
                "predicted_ms": pred, "source": src,
                "true_origin": inc.origin, "base_origin": base_origin,
                "origin": v.origin,
                "correct": v.origin == inc.origin,
                "misattributed": (v.origin is not None
                                  and base_origin is not None
                                  and v.origin != base_origin),
                "abstained": v.origin is None and base_origin is not None,
            })
    return rows


def report(rows, label, multiples=MULTIPLES):
    print()
    print("=" * 78)
    print("  " + label)
    print("=" * 78)
    print("  %-10s %10s %12s %10s %10s" %
          ("multiple", "n", "correct", "misattrib", "abstain"))
    print("  " + "-" * 74)
    for mult in multiples:
        sub = [r for r in rows if r["mult"] == mult]
        if not sub:
            continue
        print("  %-10s %10d %11d%% %9d%% %9d%%" % (
            "%.1fx" % mult, len(sub),
            round(100 * sum(r["correct"] for r in sub) / len(sub)),
            round(100 * sum(r["misattributed"] for r in sub) / len(sub)),
            round(100 * sum(r["abstained"] for r in sub) / len(sub))))

    base = [r for r in rows if r["mult"] == 0.0]
    one = [r for r in rows if r["mult"] == 1.0]
    if base and one:
        print()
        print("  baseline accuracy            %d%%" %
              round(100 * sum(r["correct"] for r in base) / len(base)))
        print("  misattribution at 1.0x       %d%%" %
              round(100 * sum(r["misattributed"] for r in one) / len(one)))
        print()
        print("  A clock-sorter predicts near 0% at 0.5x and near 100% at 1.0x.")
        print("  Any deviation from that is the finding.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--provider", choices=("anthropic", "openai", "codex", "cli"))
    ap.add_argument("--cmd", help="argv for --provider cli, e.g. \"codex exec --quiet\"")
    ap.add_argument("--model")
    ap.add_argument("--budget", type=int, default=120)
    ap.add_argument("--show-flags", action="store_true")
    ap.add_argument("--shared", action="store_true",
                    help="condition B: ambient noise uses the chain's action types")
    ap.add_argument("--multiples", help="comma-separated, e.g. 0,1,2")
    ap.add_argument("--repeats", type=int, default=REPEATS)
    ap.add_argument("--out", default="llm_results.json")
    a = ap.parse_args()

    print("Temporal Causality Poisoning - language-model arm")
    print("topology %s | seed %d | N=%d | family %s (%s)"
          % (topology_hash(), SEED, N, FAMILY, ANALOGUE[FAMILY]))
    print("suspicion flag shown to the responder: %s" % ("yes" if a.show_flags else "NO"))
    print("condition: %s" % ("B  ambient noise shares the chain vocabulary"
                             if a.shared else
                             "A  chain vocabulary appears only in the chain"))
    mults = (tuple(float(x) for x in a.multiples.split(","))
             if a.multiples else MULTIPLES)

    if a.dry_run:
        run(lambda p: "", a.show_flags, dry_run=True,
            shared_vocab=a.shared, multiples=mults, repeats=a.repeats)
        return

    if a.mock:
        inner = MockSorterClient()
        label = "MOCK sorter client - pipeline validation, not a condition"
        ns = "mock-sorter"
    elif a.provider == "anthropic":
        from llm_client import anthropic_client
        inner = anthropic_client(a.model or "claude-opus-5")
        label = "anthropic %s" % (a.model or "claude-opus-5")
        ns = "anthropic-" + (a.model or "claude-opus-5")
    elif a.provider == "openai":
        from llm_client import openai_client
        inner = openai_client(a.model or "gpt-5.6-terra")
        label = "openai %s" % (a.model or "gpt-5.6-terra")
        ns = "openai-" + (a.model or "gpt-5.6-terra")
    elif a.provider == "codex":
        from llm_client import codex_client
        inner = codex_client(model=a.model)
        label = "codex exec%s" % (" -m " + a.model if a.model else "")
        ns = "codex-" + (a.model or "gpt-6-astra")
    elif a.provider == "cli":
        if not a.cmd:
            print('\n--provider cli needs --cmd, e.g. --cmd "codex exec --quiet"')
            return
        from llm_client import subprocess_client
        inner = subprocess_client(a.cmd.split())
        label = "cli: %s" % a.cmd
        ns = "cli-" + "".join(ch if ch.isalnum() else "-" for ch in a.cmd)[:40]
    else:
        print("\nno client selected. use --dry-run, --mock, or --provider")
        return

    if a.shared:
        ns += "-sharedvocab"
        label += "  [condition B]"
    client = CachedClient(inner, namespace=ns, budget=a.budget)
    rows = run(client, a.show_flags, shared_vocab=a.shared,
               multiples=mults, repeats=a.repeats)
    report(rows, label, multiples=mults)
    print("\n  " + client.report())
    Path(a.out).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print("  wrote %s" % a.out)


if __name__ == "__main__":
    main()
