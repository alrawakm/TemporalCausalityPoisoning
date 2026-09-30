# The correlation-rule baseline, and the corpus flaw it exposed

**Run 2026-09-22.** Deterministic only; no model calls, no quota.

## 1. Why this was run

The language-model arm is measured against a clock-sorter. The obvious
reviewer objection is that no deployed correlation engine reconstructs an
incident by sorting timestamps, so the null is a straw man. `RuleOrderResponder`
is that objection built and measured: it orders by action type using a fixed
precedence over the chain's vocabulary and consults the clock only to break
ties within a rank.

## 2. The result, and it is not the one that was wanted

| Multiple | Clock-sorter | Rule, condition A | Rule, condition B |
|---|---|---|---|
| 0.0 | 100% | 100% | 80% |
| 0.5 | 100% | 100% | 80% |
| **1.0** | **0%** | **100%** | **80%** |
| 1.25 | 0% | 100% | 80% |
| 1.5 | 0% | 100% | 80% |
| 1.75 | 0% | 100% | 70% |
| 2.0 | 0% | 100% | 70% |

**In the corpus as originally built, a typed correlation rule is immune at every
magnitude.** It never reads the clock in any way the attack can reach.

## 3. The cause is in the fixture, not in the rule

The chain uses `credential_use, session_open, config_change, account_blocked`.
The ambient noise used `heartbeat, login, read, scan`. **The two sets were
disjoint: 0 of 120 ambient events carried a chain action type.**

So recognising the word `credential_use` identified the origin asset outright,
with no ordering evidence of any kind. Any reader that knows the template wins
for free.

**This changes how the Codex result must be read.** At 1.0x the sorter scores 0%
and `gpt-6-astra` scored 95%. That was interpreted as the model reading meaning
where the sorter reads only order. It is equally consistent with the model
recognising a template whose vocabulary gives the answer away. The corpus cannot
separate those two explanations, which is an internal-validity limit on the
headline result, not a property of language models.

## 4. The fix

`corpus(..., shared_vocab=True)` lets ambient events draw from the chain's
action types as well. In the fixed corpus 53 of 120 ambient events carry a chain
action type, so most credential events are benign and "the earliest
`credential_use`" needs the clock again.

This is also the more realistic case. A real operation sees far more benign
authentication than malicious.

Under that condition the rule is no longer immune. It starts at 80% rather than
100%, because a benign credential event sometimes genuinely precedes the real
one, and the perturbation drags it to 70% by 2.0x.

### 4a. The first fix was not enough, and an audit caught it

Sharing the vocabulary removed one giveaway and left another. The origin was
still **the only asset carrying both a `credential_use` and an
`account_blocked`**, so a reader could locate it by that pair alone with no
ordering evidence. `shortcut_audit.py` measures three such order-free routes and
found this one solving **100% of incidents in both conditions**.

The fix is a planted **decoy pair**: two other accounts are blocked and then
authenticate afterwards. That is a routine benign sequence rather than a
compromise chain, and the only thing separating a decoy from the real origin is
the order of its two events. After it, all three shortcuts fall to **0%** in
condition B, so ordering evidence is genuinely required.

The lesson is procedural and it is the reason `shortcut_audit.py` exists as a
standing script rather than a one-off: every time the fixture changes, ask again
whether the answer can be reached without using order, and measure it rather
than reasoning about it. The first flaw was found that way and so was the
second.

## 5. What this does to the paper

The contribution is now a **cost ordering over responder designs**, which is a
better paper than a single attack:

- a responder that reads only the clock is destroyed at 1.0x
- a typed correlation rule is untouched when types identify the chain, and
  degrades only above 1.5x when they do not
- where a language model sits is the open question, and it is now a question
  about reasoning rather than about recall

Condition A is retained rather than discarded. The A-versus-B difference is the
measurement: **how much of a responder's resistance to temporal poisoning is
lexical recall rather than reasoning about order.** If a model's robustness
collapses from A to B, an adversary who renames events defeats it, and that is
worth more than the original claim.

## 6. State of the model arm

Condition A, `gpt-6-astra` through `codex exec`: **118 of 420 cells cached.**
The sweep stopped on the Codex usage limit after 43 new calls, resetting
23 September 00:18. The daily allowance is roughly 40-50 calls of this size, so
the full design is about eight days of waiting on that path.

Both conditions must run on the same model or condition is confounded with
vendor. Nothing is decided until that runs.

