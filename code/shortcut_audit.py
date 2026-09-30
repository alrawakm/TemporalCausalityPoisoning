"""Can the origin be found without using order at all?

The first corpus flaw was found by asking that question and measuring the
answer. This script keeps asking it, so the same class of mistake cannot come
back unnoticed when the fixture changes.

Three order-free shortcuts a reader might exploit:

  S1  the only asset carrying any chain action type
  S2  the only asset carrying account_blocked
  S3  the only asset carrying BOTH credential_use and account_blocked

A shortcut at 100% solves every incident with no ordering evidence whatever, so
no temporal perturbation can touch a reader that finds it, and the condition
cannot measure reasoning about order.

    python shortcut_audit.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from soc import corpus, CHAIN_ACTIONS

N, SEED = 20, 20260920


def shortcut_rates(shared: bool):
    cs = corpus(N, SEED, shared_vocab=shared)
    hits = [0, 0, 0]
    for inc in cs:
        by = {}
        for e in inc.events:
            by.setdefault(e.asset, set()).add(e.action)
        chain_assets = [a for a, acts in by.items() if acts & set(CHAIN_ACTIONS)]
        blocked = [a for a, acts in by.items() if "account_blocked" in acts]
        both = [a for a, acts in by.items()
                if "credential_use" in acts and "account_blocked" in acts]
        hits[0] += (len(chain_assets) == 1 and chain_assets[0] == inc.origin)
        hits[1] += (len(blocked) == 1 and blocked[0] == inc.origin)
        hits[2] += (len(both) == 1 and both[0] == inc.origin)
    return hits


def main():
    a = shortcut_rates(False)
    b = shortcut_rates(True)
    names = ["S1  only asset with any chain action",
             "S2  only asset with account_blocked",
             "S3  only asset with credential_use AND account_blocked"]
    print("  shortcut                                            A disjoint  B shared")
    print("  " + "-" * 70)
    for i, nm in enumerate(names):
        print("  %-50s %8d%% %8d%%" % (nm, 100 * a[i] // N, 100 * b[i] // N))
    print()
    worst_b = max(b)
    if worst_b == N:
        print("  A shortcut still solves every incident in condition B without using")
        print("  order. B is not yet a valid test and must be tightened before it is")
        print("  paid for.")
    else:
        print("  Best order-free shortcut in B solves %d of %d. Ordering evidence is"
              % (worst_b, N))
        print("  required for the rest, so the condition can measure what it claims.")


if __name__ == "__main__":
    main()
