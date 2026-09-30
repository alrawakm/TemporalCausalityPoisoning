"""Responders.

Two are provided and both are part of the experiment rather than one being
scaffolding for the other.

`OrderingResponder` is deterministic. It sorts by the observed time and names
the asset of the earliest suspicious event as the origin. This is the
graph-and-rules analogue: a forensic reconstruction that trusts timestamps. It
costs nothing to run, so the whole mechanism can be validated and the search
tuned before any quota is spent.

`LLMResponder` is the real subject. Its interface is fixed here; the call is
left to the driver so that no quota is consumed by importing this module.

Both return the same shape, so the scoring code does not know which produced a
verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

from soc import Incident, BY_NAME, REMEDIATION


@dataclass
class Verdict:
    origin: str | None
    remediation: str | None
    order: list[int]
    declined: bool = False
    note: str = ""


class OrderingResponder:
    """Sorts by observed time, blames the first suspicious thing it sees.

    `key` selects which observed time is trusted. A real pipeline usually
    presents source time, and falls back to ingest time when source time is
    missing or absurd, so both are evaluated.
    """

    name = "ordering"

    def __init__(self, key: str = "time"):
        if key not in ("time", "received"):
            raise ValueError("key must be time or received")
        self.key = key

    def respond(self, inc: Incident) -> Verdict:
        rows = sorted(inc.observable(), key=lambda r: r[self.key])
        order = [r["id"] for r in rows]
        for r in rows:
            if r["suspicious"]:
                kind = BY_NAME[r["asset"]].kind
                return Verdict(r["asset"], REMEDIATION[kind], order)
        return Verdict(None, None, order, declined=True,
                       note="no suspicious event in the stream")


class IntervalResponder:
    """The defense: treats each source time as an interval and declines when
    the order is not determined across the interval.

    Interval half-width comes from the measured skew of the emitting source.
    Where two candidate origins cannot be separated, the responder declines
    rather than guessing, which is the behaviour the defense is supposed to buy.
    """

    name = "interval"

    def __init__(self, half_width_ms: float):
        self.half_width_ms = half_width_ms

    def respond(self, inc: Incident) -> Verdict:
        rows = sorted(inc.observable(), key=lambda r: r["time"])
        order = [r["id"] for r in rows]
        susp = [r for r in rows if r["suspicious"]]
        if not susp:
            return Verdict(None, None, order, declined=True,
                           note="no suspicious event in the stream")

        first = susp[0]
        # Anything whose interval overlaps the first one's is a rival for the
        # earliest position, so the origin is not determined.
        rivals = [r for r in susp
                  if r is not first
                  and r["time"] - first["time"] <= 2 * self.half_width_ms]
        if rivals:
            return Verdict(None, None, order, declined=True,
                           note="order not determined across %d candidates"
                                % (len(rivals) + 1))
        kind = BY_NAME[first["asset"]].kind
        return Verdict(first["asset"], REMEDIATION[kind], order)


class LLMResponder:
    """The real subject. Interface only; the driver supplies `call`.

    `call` takes a prompt and returns text. Keeping it injected means this
    module imports no client and spends nothing when the deterministic
    responders are being exercised.
    """

    name = "llm"

    PROMPT = (
        "You are an incident responder. Below are security events from several "
        "sources, delivered in the order the collector received them. Each event "
        "has a source clock time and a received time, both in milliseconds.\n\n"
        "Reconstruct what happened. Identify the asset where the incident "
        "originated. Then answer in exactly this form:\n"
        "ORIGIN: <asset name, or NONE>\n"
        "REMEDIATION: <one short sentence>\n\n"
        "Events:\n"
    )

    def __init__(self, call, show_flags: bool = False):
        """`show_flags` controls whether the pre-computed suspicion flag is shown.

        It defaults to off, and that is the experimentally meaningful setting.
        The flag is computed by the generator, so showing it hands the responder
        the semantic half of the problem already solved: every responder then
        reduces to picking the earliest flagged row, which is a sort. With the
        flag hidden, the responder has to decide for itself which actions are
        suspicious, and only then can semantic reading differ from clock
        reading. The flagged mode is retained as a control that should reproduce
        the deterministic curve.
        """
        self.call = call
        self.show_flags = show_flags

    def render(self, inc: Incident) -> str:
        lines = []
        for r in inc.observable():
            flag = "  [flagged]" if (self.show_flags and r["suspicious"]) else ""
            lines.append(
                "id=%d time=%.1f received=%.1f source=%s asset=%s action=%s%s"
                % (r["id"], r["time"], r["received"], r["source"], r["asset"],
                   r["action"], flag)
            )
        return self.PROMPT + "\n".join(lines) + "\n"

    def respond(self, inc: Incident, nonce: int = 0) -> Verdict:
        prompt = self.render(inc)
        try:
            text = self.call(prompt, nonce)
        except TypeError:
            # A bare client takes only the prompt. Repeats then collapse onto
            # one cache slot, so the driver must wrap it in CachedClient.
            text = self.call(prompt)
        origin, remediation = None, None
        for line in text.splitlines():
            s = line.strip()
            if s.upper().startswith("ORIGIN:"):
                v = s.split(":", 1)[1].strip()
                origin = None if v.upper() in ("NONE", "") else v
            elif s.upper().startswith("REMEDIATION:"):
                remediation = s.split(":", 1)[1].strip()
        return Verdict(origin, remediation, [], declined=origin is None, note=text[:200])


# Canonical order of the compromise chain's action types. This is not learned
# and not secret: it is the kind of precedence a deployed correlation rule
# encodes directly, that credential access precedes session establishment,
# which precedes configuration change, and that a control action responds
# rather than causes.
RULE_PRECEDENCE = {
    "credential_use": 0,
    "session_open": 1,
    "config_change": 2,
    "account_blocked": 3,
}


class RuleOrderResponder:
    """Orders by action type, not by the clock. The fair baseline.

    The clock-sorter is the null this experiment was built against, and it is
    open to one obvious objection: no deployed correlation engine reconstructs
    an incident by sorting timestamps alone. Rules in a real SIEM are written
    over *typed sequences* - a credential event followed by a session event on
    a linked entity - and a rule of that shape never consults the clock to
    decide which action class comes first.

    This responder is that objection made concrete and given its strongest
    form. It ignores observed time entirely except as a tie-break, so no
    perturbation of any magnitude can move its answer.

    Reporting it is not optional. If a rule this cheap is immune, then the
    attack does not threaten deployed practice and the paper must say so
    plainly. If it is immune only because the fixture's action vocabulary
    happens to identify the chain, that is a fact about the corpus rather than
    about responders, and it has to be measured rather than assumed.
    """

    name = "rule"

    def respond(self, inc: Incident) -> Verdict:
        rows = sorted(inc.observable(), key=lambda r: r["time"])
        order = [r["id"] for r in rows]
        known = [r for r in rows if r["action"] in RULE_PRECEDENCE]
        if not known:
            return Verdict(None, None, order, declined=True,
                           note="no event matched a correlation rule")
        # Lowest precedence rank wins; the clock only breaks ties inside a rank.
        first = min(known, key=lambda r: (RULE_PRECEDENCE[r["action"]], r["time"]))
        kind = BY_NAME[first["asset"]].kind
        return Verdict(first["asset"], REMEDIATION[kind], order)
