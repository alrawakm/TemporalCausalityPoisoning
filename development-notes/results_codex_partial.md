# Codex arm — first language-model data, partial

**Run 2026-09-21.** Model `gpt-6-astra` through `codex exec`, reasoning effort
low, sandbox read-only, final message constrained by `--output-schema` to
`{origin, remediation}`. Topology `91d855455d38f1bb`, seed 20260920, N=20,
family `disagreement`, gap 4–25 s. The suspicion flag was **hidden**, so the
responder had to decide for itself which actions were suspicious.

**75 of 80 responses.** The run stopped on a Codex subscription usage limit,
the same wall that blocked the Five Bits second-agent replication. The five
absent responses are reported as absent and are not averaged away.

---

## 1. The result

| Multiple of the sorter's minimum | n | Correct | Misattributed | Abstained | Missing |
|---|---|---|---|---|---|
| 0.0 — baseline | 19 | 79% | 0% | 0% | 1 |
| 0.5 | 19 | 89% | 16% | 5% | 1 |
| **1.0** | 19 | **95%** | **16%** | 0% | 1 |
| 2.0 | 18 | 61% | 33% | 0% | 2 |

The clock-sorter null is 100% correct and 0% misattributed at 0.5, and 0%
correct and 100% misattributed at 1.0.

**At 1.0 the sorter is fully defeated and this responder is barely touched.**
Sixteen per cent against a predicted hundred is not a gap noise can produce at
this sample size. The language-model responder is not reading the clock alone.

The likely reason is in the event names. A responder reading meaning can see
that `credential_use` on an account is the kind of thing that causes, and that
`account_blocked` is the kind of thing that responds, whatever order the
timestamps put them in. The deterministic responder has no access to that and
cannot recover from a reordering.

**The attack is not defeated, only repriced.** Misattribution doubles to 33% at
2.0, so a threshold exists. It sits somewhere above twice the sorter's cost, and
this run does not locate it.

---

## 2. What is not trustworthy here

**The baseline is 79%, not 100%.** Unperturbed, the responder names the wrong
origin about one incident in five. That noise floor limits every row above it
and it is the first thing a reviewer will ask about.

**1.0 scoring above the baseline is almost certainly noise.** Ninety-five
against seventy-nine is eighteen incidents against fifteen, out of nineteen. No
story should be read into it.

**One repeat per cell.** The pre-committed analysis calls for repeats and this
run has none, because the deterministic responder needed none and the same
driver was reused. That was an error. Five Bits established the shape of the
problem already: individual decisions flip about a fifth of the time while
aggregate rates reproduce, so single-shot cells carry decision noise that rates
over repeats would remove.

**One model, one configuration, one effort setting.** No claim transfers beyond
`gpt-6-astra` at low effort.

The headline survives all four. The fine structure does not.

---

## 3. Exploratory, post-hoc — kept apart

Flagged after reading an interim response that raised clock normalisation
without being asked. It is reported here and is **not** folded into the
pre-committed metrics, because it was chosen after seeing data.

| Multiple | Responses mentioning clocks, skew, timestamps or synchronisation |
|---|---|
| 0.0 | 0 of 19 |
| 0.5 | 0 of 19 |
| 1.0 | 0 of 19 |
| 2.0 | **2 of 18** |

The responder remarks on timing only when the distortion is gross. At the
magnitude that defeats a sorter it says nothing about clocks at all, and is
nonetheless mostly right. Whatever is protecting it is not an explicit check on
the timestamps.

---

## 4. Errors in the run itself

**The first attempt died at call 76 and the cause was hidden by my own error
handling**, which truncated the client's stderr to 400 characters. The retry
showed the real message: a usage limit with a reset time. Full stderr is now
captured, and a retry with backoff was added so that one transient failure
cannot discard a sweep that is otherwise complete.

**Seventy-five responses survived the crash** because every response is cached
on disk by prompt hash. The rerun cost five calls rather than eighty. That
design decision paid for itself on its first use.

**The cache was not namespaced by client, and that is the dangerous one.** The
key is a hash of the prompt and records nothing about which model answered. A
validation run against the mock sorter therefore wrote 345 of its own answers
into the same directory as the 75 real ones, and drew those 75 back out and
blended them into its reported rates. The mock figures from that run were
discarded.

The numbers in section 1 were produced before the contamination and are
unaffected, which was confirmed by rebuilding the namespaces and rerunning the
analysis to the same values. The exposure was still real: a later run against a
different provider would have been served Codex's cached answers and would have
reported them as its own, and nothing in the output would have shown it.

The cache is now `cache/<client>/`, the namespace is a required constructor
argument rather than an optional one, and the 345 mock responses were moved to
their own namespace rather than deleted. A result published from the blended
directory would have been wrong in a way no reader or reviewer could detect.

---

## 5. What the next run needs

Quota resets 22 September 01:04.

1. The five missing responses.
2. **Three repeats per cell**, which is the fix for section 2.
3. Multiples between 1.0 and 2.0 to locate the threshold that section 1 shows
   exists but does not find.

That is roughly 240 calls. It exceeds a day of Codex allowance and costs about
sixty cents on the API, which is the argument for paying rather than waiting.

---

## 6. What this does to the paper

The deterministic arm was arithmetic. This arm is not, and it inverts the
paper's expected story.

The original claim was that a responder can be made to build a confident wrong
account of an incident for less than the cost of ordinary clock drift. Against a
timestamp sorter that is true and trivial. Against a language-model responder it
is false at the sorter's price and true at somewhere above twice it.

So the contribution is a **comparison**, not an attack: reading meaning rather
than order raises the cost of temporal reattribution by a factor this experiment
can bound but has not yet measured. The defense recommendation follows from it
and is not the interval reasoning the problem statement proposed, which the
deterministic arm already refused.
