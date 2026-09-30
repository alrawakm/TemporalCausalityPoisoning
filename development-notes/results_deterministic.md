# Deterministic results — first data

**Run 2026-09-21.** Topology `91d855455d38f1bb`, seed 20260920, N=30 per cell,
no API quota spent. These are the graph-and-rules baseline, not the
language-model result. Every number below is reproducible from
`code/run_families.py` and `code/run_deterministic.py`.

---

## 1. Cost tracks the inter-event gap, one to one

Family `offset`, ordering by source time, N=30 per row.

| Chain gap | Median gap | Median minimum | Ratio | In tier 1 | Misattributed |
|---|---|---|---|---|---|
| 50–200 ms | 125 ms | **127 ms** | 1.02 | 53% | 30/30 |
| 1–5 s | 3,000 ms | **3,055 ms** | 1.02 | 0% | 30/30 |
| 4–25 s | 14,500 ms | **14,877 ms** | 1.03 | 0% | 30/30 |
| 30–120 s | 75,000 ms | **76,682 ms** | 1.02 | 0% | 30/30 |

The minimum effective perturbation is the distance the adversary must close
between two suspicious events. It is therefore a property of the incident's
pace, not of the responder.

**What this does to the paper's framing.** The original hope was a single number
below 128 ms. That holds only for chains whose events are 50–200 ms apart, where
53% of minima fall inside the NTP noise floor. For hands-on intrusion at seconds
of spacing the cost is seconds — still **1.7% to 5% of the 300 s Kerberos
budget**, and still far below anything that breaks authentication. The finding
is a law with a threshold inside it, which is stronger than one number.

---

## 2. The family matrix: neither clock is safe

Gap 4–25 s, N=30. "mis" is misattribution to a different wrong asset.
"abstain" is declining to name anything.

| Family | order by source time | order by ingest time | interval, 128 ms |
|---|---|---|---|
| offset | **mis 30/30**, 14,877 | none | **mis 30/30**, 15,133 |
| zone | **mis 30/30**, 14,877 | none | **mis 30/30**, 15,133 |
| delay | none | **mis 30/30**, 14,825 | none |
| duplicate | none | none | abstain 30 |
| tie | **mis 30/30**, 57,345 | none | abstain 30 |
| **disagreement** | **mis 30/30**, 14,877 | **mis 30/30**, 29,649 | **mis 30/30**, 15,133 |

**`disagreement` is the universal attack.** It is the only family that
misattributes against both single-clock orderings, because it moves source time
one way and ingest time the other. Whichever clock the responder trusts is the
wrong one.

**The two orderings are complementary and neither is sufficient.** Source-time
ordering falls to offset, zone, tie and disagreement. Ingest-time ordering falls
to delay and disagreement. There is no single clock to trust, which is Lamport's
point arriving as a measurement.

**Materiality is total.** Every misattribution in the table also changed the
recommended remediation, 30 of 30 in every cell. The origin moves from an
account to a service, so the recommendation moves from revoking a credential to
isolating a service. There is no cell where the attack changes the story without
changing the response.

---

## 3. The proposed defense does not work

Interval reasoning with a 128 ms half-width was the defense named in the problem
statement. The data refuses it.

- It misattributes **30/30** on offset, zone and disagreement, at **15,133 ms**
  against the undefended **14,877 ms**. The defense raises the adversary's cost
  by **1.7%**.
- Its only other effect is converting `tie` and `duplicate` from no effect into
  **30 abstentions**.

So it buys nothing against the attacks that work and loses availability against
two that previously did nothing. That is the outcome the problem statement said
must stay visible rather than be hidden, and it is visible.

**Why it fails.** The half-width was set from the NTP noise floor, 128 ms, while
the attack operates at the scale of the inter-event gap, which is seconds. An
interval sized for clock noise cannot express uncertainty about an ordering that
is being moved by four orders of magnitude more than that.

**What the data suggests instead, as the next experiment rather than a claim.**
`disagreement` succeeds precisely because nothing compares the two clocks against
each other. A responder that models the expected delivery profile of each source,
and flags events whose ingest-minus-source deviates from it, would have evidence
that something is wrong. That is testable with the harness already built.

---

## 4. Two errors of mine, recorded

**The first run returned a null across every cell, and the null was wrong.**
`perturb()` defaulted to the source carrying the last chain event, which is the
`account_blocked` event, which is not flagged suspicious. Moving a non-suspicious
event cannot change which suspicious event comes first. The fix is that the
adversary now chooses the cheapest source, because fixing one source in advance
measures the analyst's convenience rather than the attacker's cost.

**The scoring conflated abstention with misattribution.** Any change of origin
counted as a flip, including a change to nothing, which scored the defense
holding as the attack succeeding. `duplicate` appeared to defeat the interval
responder at magnitude zero on that basis. The two outcomes are now separate
throughout, and the search targets misattribution because that is the adversary's
objective.

Both are recorded because the corrected numbers are only meaningful next to the
reason the first ones were not.

---

## 5. What this is not

No language model has been run. Every result here is the deterministic
graph-and-rules responder, which is a baseline in the paper rather than a
stand-in for the subject. Whether a language-model responder is more or less
vulnerable is unmeasured and is the next experiment.

The abstention counts for the interval responder are a property of that
responder's rule, not of a deployed system.

N=30 per cell with a deterministic responder needs no repeats. The repeat
machinery exists for the stochastic case and is unexercised.

---

## Next

1. Wire `LLMResponder` to a single configuration and rerun the family matrix.
   The deterministic result predicts where the LLM should fail if it orders by
   the clock, and the interesting outcome is any place it does not.
2. Test the delivery-profile check from section 3 against `disagreement`.
3. Re-run the gap sweep for `disagreement`, which is the family that matters.
