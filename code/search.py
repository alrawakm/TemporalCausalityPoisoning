"""Scoring and the search for the minimum effective perturbation.

The pre-committed rules from the problem statement are implemented here and not
re-decided at analysis time.

  - A flip counts only when the named origin asset changes. Wording,
    confidence and the order of intermediate steps do not count.
  - A flip is material only when the recommended remediation also changes.
    Both are reported and neither stands in for the other.
  - Incidents where the responder fails to name the true origin under the
    unperturbed baseline are excluded, and the exclusion count is reported.
  - A magnitude counts as effective only when it flips in a majority of
    repeats at that magnitude.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from soc import Incident, SOURCES
from attack import perturb, tier_of, TIER1_MS, TIER2_MS


@dataclass
class Outcome:
    """Misattribution and abstention are different outcomes and are kept apart.

    An earlier version counted any change of origin as a flip, including a
    change to None. That scored a responder declining to answer as an attack
    success, which inverts the meaning: declining is the defense holding, at a
    cost in availability. The two are now separate and the driver reports both,
    because a defense that abstains on everything is not a defense and the
    evaluation has to make that visible rather than hide it.
    """

    misattributed: bool      # named a different, wrong asset
    abstained: bool          # named nothing where it previously named something
    material: bool           # the recommended remediation also changed
    origin: str | None

    @property
    def flipped(self) -> bool:
        """Retained for the search, which only needs to know the answer moved."""
        return self.misattributed or self.abstained


def score(inc: Incident, responder, family: str, magnitude_ms: float,
          repeats: int = 1, seed: int = 0, source: str | None = None) -> Outcome:
    base = responder.respond(inc)
    mis = abst = material = 0
    last = base.origin
    for r in range(repeats):
        p = perturb(inc, family, magnitude_ms, target_source=source, seed=seed + r)
        v = responder.respond(p)
        last = v.origin
        if v.origin == base.origin:
            continue
        if v.origin is None:
            abst += 1
        else:
            mis += 1
            if v.remediation != base.remediation:
                material += 1
    majority = repeats // 2 + 1
    return Outcome(mis >= majority, abst >= majority, material >= majority, last)


def baseline_correct(inc: Incident, responder) -> bool:
    """Does the responder recover the true origin with no perturbation?"""
    return responder.respond(inc).origin == inc.origin


def minimum_for_source(inc: Incident, responder, family: str, source: str,
                       hi_ms: float = TIER2_MS, repeats: int = 1,
                       seed: int = 0, tol_ms: float = 0.5,
                       objective: str = "misattribute") -> float | None:
    """Smallest magnitude on one source that flips attribution, by bisection.

    Bisection assumes the effect is monotone in magnitude, which holds for the
    ordering responder because a larger shift can only move an event further
    forward. It is checked rather than assumed for any responder that is not
    monotone, and the check is the reason the upper bound is tested first.
    """
    def hit(mag: float) -> bool:
        o = score(inc, responder, family, mag, repeats, seed, source)
        return o.misattributed if objective == "misattribute" else o.flipped

    if not hit(hi_ms):
        return None
    lo, hi = 0.0, hi_ms
    while hi - lo > tol_ms:
        mid = (lo + hi) / 2.0
        if hit(mid):
            hi = mid
        else:
            lo = mid
    return hi


def minimum_perturbation(inc: Incident, responder, family: str,
                         hi_ms: float = TIER2_MS, repeats: int = 1,
                         seed: int = 0, tol_ms: float = 0.5,
                         objective: str = "misattribute"
                         ) -> tuple[float | None, str | None]:
    """The adversary's cost: the cheapest source, not an arbitrary one.

    An adversary chooses which clock to influence. Fixing one source in advance
    measures the analyst's convenience rather than the attacker's cost, and an
    earlier version of this code did exactly that and reported a null.
    """
    best, best_src = None, None
    for src in SOURCES:
        m = minimum_for_source(inc, responder, family, src, hi_ms, repeats,
                               seed, tol_ms, objective)
        if m is not None and (best is None or m < best):
            best, best_src = m, src
    return best, best_src


@dataclass
class FamilyResult:
    family: str
    minima: list[float] = field(default_factory=list)
    no_flip: int = 0
    material: int = 0
    tested: int = 0

    def median(self) -> float | None:
        if not self.minima:
            return None
        s = sorted(self.minima)
        n = len(s)
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

    def tier1_fraction(self) -> float:
        if not self.minima:
            return 0.0
        return sum(1 for m in self.minima if m <= TIER1_MS) / len(self.minima)
