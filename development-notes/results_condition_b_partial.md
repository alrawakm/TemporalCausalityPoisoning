# Condition B, first signal — 2026-09-23

`gpt-6-astra` through `codex exec`, effort low, suspicion flag hidden.
N=20, **one repeat**, multiples 0.0 and 1.0 only. 40 live calls.

## The result

| Multiple | Condition A | Condition B |
|---|---|---|
| 0.0 baseline correct | **79%** | **45%** |
| 1.0 correct | 95% | 65% |
| 1.0 misattributed | 16% | 15% |
| 1.0 abstained | 0% | 10% |

**Removing the lexical giveaway nearly halves unperturbed accuracy, 79% to 45%.**

That is the result the redesign was built to expose. In condition A the chain's
action vocabulary appeared nowhere else, so naming the origin required only
recognising `credential_use`. With benign events carrying the same vocabulary
and decoy accounts blocked before they authenticate, the same model gets fewer
than half of the *unattacked* incidents right.

So a substantial part of what looked like competence at reconstructing an
incident was recall of a template, not reasoning about order. That is the
paper's claim and this is the first direct evidence for it.

## What is not trustworthy here

**One repeat.** The pre-committed design calls for three. These are single-shot
cells and carry the decision noise that repeats exist to remove. The same
mistake was made in the condition-A run and recorded there; it is repeated here
only because a day's quota buys 40 calls and a first signal was worth more than
waiting a week for a clean one.

**Twenty incidents.** 45% is 9 of 20. The gap to 79% is large enough to survive
that, but the exact value should not be quoted until the repeats are in.

**Accuracy rises from 0.0 to 1.0 in both conditions**, 79 to 95 in A and 45 to
65 in B. A perturbation designed to mislead should not improve accuracy. Two
independent conditions showing the same inversion makes chance a weaker
explanation than it was when only A showed it.

One hypothesis worth testing rather than asserting: the `disagreement` family
works by putting event time and collection time in conflict, and a reader that
notices the conflict may discount the manipulated clock and fall back on ingest
order, which is correct. If so the attack is partly self-defeating against a
reader that checks for that conflict, and that is a finding rather than a bug.
The exploratory count in the condition-A run is consistent with it: the
responder mentioned clocks or synchronisation in 2 of 18 responses at 2.0 and
in none at all below it.

**Do not write any of this up until the repeats are in.**

## Next

Three repeats at multiples 0, 1, 2 for both conditions on one model, 360 calls.
Resume instructions at the foot of `STATUS.md`.
