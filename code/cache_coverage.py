"""How many cells of a given design are already paid for?

Constructs the exact prompts a run would send, derives each cache key, and
counts which ones already exist on disk. Spends nothing, and answers the only
question that matters when quota is the binding constraint: where should the
next forty calls go.

    python cache_coverage.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soc import corpus
from attack import perturb
from responder import LLMResponder, OrderingResponder
from search import minimum_perturbation
from llm_client import CachedClient

N, SEED, GAP, FAMILY = 20, 20260920, (4000.0, 25000.0), "disagreement"
MULTIPLES = (0.0, 1.0, 2.0)
REPEATS = 3


def coverage(namespace: str, shared_vocab: bool):
    incidents = corpus(N, SEED, gap_range_ms=GAP, shared_vocab=shared_vocab)
    clock = OrderingResponder("time")
    responder = LLMResponder(lambda p, n=0: "", show_flags=False)
    cache = CachedClient(lambda p: "", namespace=namespace)

    have = need = 0
    for inc in incidents:
        pred, src = minimum_perturbation(inc, clock, FAMILY)
        if pred is None:
            continue
        for mult in MULTIPLES:
            for rep in range(REPEATS):
                p = inc if mult == 0.0 else perturb(inc, FAMILY, pred * mult,
                                                    target_source=src)
                key = cache.key(responder.render(p), rep)
                if (cache.dir / (key + ".json")).exists():
                    have += 1
                else:
                    need += 1
    return have, need


def main():
    print("  design: multiples %s, %d repeats, N=%d"
          % (", ".join(str(m) for m in MULTIPLES), REPEATS, N))
    print()
    print("  %-34s %8s %8s" % ("condition / namespace", "cached", "to buy"))
    print("  " + "-" * 52)
    total_need = 0
    for ns, shared, label in (
            ("codex-gpt-6-astra", False, "A  codex-gpt-6-astra"),
            ("codex-gpt-6-astra-sharedvocab", True, "B  codex-gpt-6-astra-sharedvocab"),
            ("anthropic-claude-opus-5", False, "A  anthropic-claude-opus-5"),
            ("anthropic-claude-opus-5-sharedvocab", True, "B  anthropic-claude-opus-5-sharedvocab")):
        have, need = coverage(ns, shared)
        print("  %-34s %8d %8d" % (label, have, need))
        if ns.startswith("codex"):
            total_need += need
    print()
    print("  Codex path still to buy: %d calls, about %d days at 43 a day."
          % (total_need, -(-total_need // 43)))


if __name__ == "__main__":
    main()
