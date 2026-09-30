"""Score whatever is in the cache, and say plainly what is missing.

The Codex run hit a subscription usage limit after 75 of 80 calls. Those 75 are
real responses and are worth scoring. The five that are absent are absent, and
this script reports them as such rather than quietly averaging over a smaller
denominator.

    python analyze_cache.py
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soc import corpus, topology_hash
from attack import perturb
from responder import LLMResponder, OrderingResponder
from search import minimum_perturbation

N = 20
SEED = 20260920
GAP = (4000.0, 25000.0)
FAMILY = "disagreement"
MULTIPLES = (0.0, 0.5, 1.0, 2.0)
CACHE = Path("cache") / "codex-gpt-6-astra"


def cached(prompt: str):
    f = CACHE / (hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:32] + ".json")
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))["response"]


def parse(text: str):
    origin = None
    for line in text.splitlines():
        if line.upper().startswith("ORIGIN:"):
            v = line.split(":", 1)[1].strip()
            origin = None if v.upper() in ("NONE", "") else v
    return origin


def main():
    responder = LLMResponder(lambda p: "", show_flags=False)
    incidents = corpus(N, SEED, gap_range_ms=GAP)

    rows = []
    for inc in incidents:
        pred, src = minimum_perturbation(inc, OrderingResponder("time"), FAMILY)
        if pred is None:
            continue
        base = None
        for mult in MULTIPLES:
            p = inc if mult == 0.0 else perturb(inc, FAMILY, pred * mult, target_source=src)
            text = cached(responder.render(p))
            origin = parse(text) if text is not None else "__MISSING__"
            if mult == 0.0:
                base = origin
            rows.append({"iid": inc.iid, "mult": mult, "origin": origin,
                         "base": base, "true": inc.origin, "text": text})

    print("Temporal Causality Poisoning - Codex arm, partial")
    print("topology %s | seed %d | family %s | model gpt-6-astra via codex exec"
          % (topology_hash(), SEED, FAMILY))
    missing = sum(1 for r in rows if r["origin"] == "__MISSING__")
    print("responses: %d of %d present, %d missing to a usage limit"
          % (len(rows) - missing, len(rows), missing))

    print()
    print("  %-8s %6s %10s %12s %10s %10s" %
          ("multiple", "n", "correct", "misattrib", "abstain", "missing"))
    print("  " + "-" * 62)
    for mult in MULTIPLES:
        sub = [r for r in rows if r["mult"] == mult]
        have = [r for r in sub if r["origin"] != "__MISSING__" and r["base"] != "__MISSING__"]
        miss = len(sub) - len(have)
        if not have:
            print("  %-8s %6d %10s %12s %10s %10d" % ("%.1fx" % mult, len(sub), "-", "-", "-", miss))
            continue
        correct = sum(1 for r in have if r["origin"] == r["true"])
        mis = sum(1 for r in have if r["origin"] is not None and r["origin"] != r["base"])
        abst = sum(1 for r in have if r["origin"] is None and r["base"] is not None)
        print("  %-8s %6d %9d%% %11d%% %9d%% %10d" % (
            "%.1fx" % mult, len(have),
            round(100 * correct / len(have)),
            round(100 * mis / len(have)),
            round(100 * abst / len(have)), miss))

    print()
    print("  a clock-sorter gives 100/0/0 at 0.5x and 0/100/0 at 1.0x")

    # Exploratory and post-hoc: flagged after seeing an interim response that
    # raised clock normalisation unprompted. Reported apart from the
    # pre-committed metrics above, never folded into them.
    print()
    print("  --- exploratory, post-hoc: does it mention the clocks? ---")
    words = ("clock", "skew", "normaliz", "timestamp", "time source", "synchron")
    for mult in MULTIPLES:
        have = [r for r in rows if r["mult"] == mult and r["text"]]
        if not have:
            continue
        hits = sum(1 for r in have if any(w in r["text"].lower() for w in words))
        print("  %-8s %d of %d responses mention timing" % ("%.1fx" % mult, hits, len(have)))

    Path("codex_partial.json").write_text(
        json.dumps([{k: v for k, v in r.items() if k != "text"} for r in rows], indent=1),
        encoding="utf-8")
    print("\n  wrote codex_partial.json")


if __name__ == "__main__":
    main()
