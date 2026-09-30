# Skew measurement — the admissible perturbation range

**Measured 2026-09-20. This closes the gate on paper 13.** The problem statement
records that "operationally plausible" must be a measured quantity and not a
judgement, because the central claim is that the perturbation hides below the
detection floor. A floor fixed by assertion would make the claim circular. This
file fixes it from documented thresholds and one local measurement, and the
range derived here is not revised after results are seen.

---

## 1. The reasoning, corrected

An earlier framing in this project treated the bound as a question of **typical
drift**: how far do clocks in a real pipeline usually diverge? That is the wrong
quantity.

The claim concerns **detectability**. A perturbation is undetectable when it
falls below what a consistency checker is configured to react to, and that
threshold is set by configuration rather than by what typically occurs. A rare
offset that still sits under every configured tolerance is invisible; a common
one above a tolerance is not. The bound therefore comes from documented
thresholds, and typical drift enters only as context.

---

## 2. Documented thresholds

These are published, citable, and deployed by default across the estate that a
security pipeline draws from.

| Threshold | Value | Effect below the threshold |
|---|---|---|
| **NTP step threshold** | **128 ms** | The offset spike is **discarded** by the protocol as noise |
| NTP stepout threshold | 300 s | A persistent spike is not stepped until this elapses |
| NTP panic threshold (PANICT) | 1000 s | The daemon accepts the offset rather than refusing it |
| **Kerberos maximum clock skew** | **300 s (5 min)** | Authentication succeeds; nothing in the auth stack reacts |
| W32Time `MaxAllowedPhaseOffset` | 300 s default | The clock is slewed rather than stepped |

The first and fourth rows carry the paper.

**The 128 ms step threshold is the strongest single fact available here.** An
offset below it is not merely unnoticed. The time protocol is specified to
throw it away as noise. No argument about operator attention is required.

**The 300 s Kerberos tolerance is the widest one.** Every Windows enterprise
runs it. Inside five minutes of inter-host skew, authentication continues to
work, which is the condition under which nobody investigates a clock.

### Sources

- MIT Kerberos V5 System Administrator's Guide, Clock Skew —
  <https://web.mit.edu/kerberos/krb5-1.5/krb5-1.5.4/doc/krb5-admin/Clock-Skew.html>
- Microsoft Learn, Maximum tolerance for computer clock synchronization —
  <https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2012-r2-and-2012/jj852172(v=ws.11)>
- Microsoft Learn, Configure W32Time against huge time offset —
  <https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/configure-w32ime-against-huge-time-offset>
- NTP clock state machine, step and stepout thresholds —
  <https://www.ntp.org/documentation/4.2.8-series/clock/>
- NTP miscellaneous options, panic threshold —
  <https://www.ntp.org/documentation/4.2.2-series/miscopt/>

---

## 3. Local measurement

One endpoint, measured with `w32tm` on 2026-09-20.

**Sync state.** The machine is **not synchronised**. Leap indicator 3, stratum
0, source `Local CMOS Clock`, last successful sync time unspecified. It free-runs
on the hardware clock. That is itself relevant: an unmanaged endpoint feeding
telemetry has no discipline applied to it at all.

**Offset against three independent servers**, `time.windows.com`,
`pool.ntp.org` and `time.google.com`, four samples each.

| Statistic | Value |
|---|---|
| Samples | 12 |
| Median offset | **72.16 ms** |
| Mean | 75.12 ms |
| Standard deviation | 11.34 ms |
| Range | 68.19 to 110.40 ms |

**Local W32Time configuration**, read from the registry:

| Setting | Value |
|---|---|
| `MaxAllowedPhaseOffset` | 1 s (tighter than the 300 s default) |
| `MaxPosPhaseCorrection` | 54000 s |
| `MaxNegPhaseCorrection` | 54000 s |
| Kerberos `SkewTime` | not set, so the 300 s default applies |

The measured median sits at **0.56 of the NTP step threshold**. An undisciplined
endpoint is already drifting far enough that half the protocol's noise budget is
consumed before any adversary acts.

---

## 4. The admissible range, fixed

Two tiers, and the experiment reports against both.

**Tier 1 — below 128 ms.** Discarded as noise by the time protocol itself. The
strongest claim available, because undetectability follows from a specification
rather than from an argument about practice.

**Tier 2 — below 300 s.** Below Kerberos tolerance and below the W32Time default
phase offset. Nothing in the authentication or synchronisation stack reacts.
This is the operational budget an adversary actually holds.

**The consequence for the paper is the gap between tier 2 and the timescale of
an incident.** Five minutes is not a small budget for reordering security
events. Intrusion chains commonly unfold over seconds to a few minutes, so a
300 s budget is wide enough to reorder most of a chain end to end. The adversary
is not working at the margin. The adversary has more budget than the phenomenon
needs.

The bisection search runs within tier 1 first. If the minimum effective
perturbation falls inside 128 ms, the result is far stronger than the paper
originally assumed, because it means the attack operates entirely inside what
the protocol defines as noise.

---

## 5. Limitations of this measurement

One endpoint, one operating system, twelve samples, one day. It establishes that
an undisciplined Windows workstation sits tens of milliseconds off, and nothing
more general.

**The paper does not rest on it.** The admissible range comes from the
documented thresholds in Section 2, which are properties of the protocols and
are citable. The local measurement is context showing that real endpoints drift
within the range rather than sitting at zero.

If a stronger empirical claim is wanted later, the measurement to make is
inter-source skew across several hosts feeding one collector, which is the
quantity the threat model actually concerns. A single client-to-server offset is
not that quantity, and this file does not claim it is.

---

## Change log

- 2026-09-20 — measured and fixed. Not revised after results.
