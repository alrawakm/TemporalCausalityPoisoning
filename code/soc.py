"""The world: assets, clocks, events and incidents.

Fixed 2026-09-20 from `environment_spec.md` and `skew_measurement.md`. The
topology and the clock constants are inputs, not parameters. Nothing here is
adjusted after a result is seen.

An event carries three times. The responder observes the source time and the
ingest time. It never observes the true time or the cause, both of which live in
the ground-truth record and are the scoring key.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field, asdict
from typing import Iterable

# --- measured constants, from skew_measurement.md ------------------------

NTP_STEP_THRESHOLD_MS = 128.0     # offsets below this are discarded as noise
KERBEROS_SKEW_S = 300.0           # below this, authentication keeps working
MEASURED_MEDIAN_OFFSET_MS = 72.16  # one undisciplined endpoint, n=12
MEASURED_SD_OFFSET_MS = 11.34

# Absolute epoch base. Incidents used to start at zero, which let a backward
# clock shift produce negative timestamps. A negative time is an obvious tell
# and would defeat the plausibility bound the whole study rests on, so times
# are absolute as real telemetry is.
EPOCH_BASE_MS = 1789981200000   # 2026-09-21T09:00:00Z


@dataclass(frozen=True)
class Asset:
    name: str
    kind: str          # service datastore identity account host monitor
    source: str        # which telemetry source reports on it


# A three-tier application behind one identity provider, with monitoring
# dependent on everything. Seventeen nodes. Ordinary shape, not chosen to
# amplify anything.
ASSETS: tuple[Asset, ...] = (
    Asset("web-01", "service", "firewall"),
    Asset("app-01", "service", "endpoint"),
    Asset("worker-01", "service", "endpoint"),
    Asset("build-01", "service", "endpoint"),
    Asset("db-primary", "datastore", "cloud"),
    Asset("cache-01", "datastore", "cloud"),
    Asset("idp", "identity", "identity"),
    Asset("svc-deploy", "account", "identity"),
    Asset("svc-backup", "account", "identity"),
    Asset("u-alice", "account", "identity"),
    Asset("u-bob", "account", "identity"),
    Asset("u-carol", "account", "identity"),
    Asset("u-dave", "account", "identity"),
    Asset("host-a", "host", "endpoint"),
    Asset("host-b", "host", "endpoint"),
    Asset("host-c", "host", "endpoint"),
    Asset("collector", "monitor", "collector"),
)

BY_NAME = {a.name: a for a in ASSETS}

# Dependency edges: (dependent, requires)
DEPENDS: tuple[tuple[str, str], ...] = (
    ("web-01", "app-01"), ("app-01", "db-primary"), ("app-01", "cache-01"),
    ("worker-01", "db-primary"), ("build-01", "svc-deploy"),
    ("app-01", "idp"), ("web-01", "idp"), ("worker-01", "idp"),
    ("svc-deploy", "idp"), ("svc-backup", "idp"),
    ("u-alice", "idp"), ("u-bob", "idp"), ("u-carol", "idp"), ("u-dave", "idp"),
    ("app-01", "host-a"), ("worker-01", "host-b"), ("build-01", "host-c"),
    ("collector", "host-a"), ("collector", "host-b"), ("collector", "host-c"),
)

SOURCES: tuple[str, ...] = ("firewall", "endpoint", "identity", "cloud", "collector")


def dependents(asset: str) -> list[str]:
    return [d for d, r in DEPENDS if r == asset]


def topology_hash() -> str:
    body = json.dumps({"assets": [asdict(a) for a in ASSETS], "depends": list(DEPENDS)},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()[:16]


# --- clocks --------------------------------------------------------------

@dataclass
class ClockModel:
    """Per-source offset, jitter and delivery delay, in milliseconds.

    The offset distribution is centred on the measured median rather than on
    zero, because the endpoint measured on 2026-09-20 was running undisciplined
    and sat 72 ms ahead. A model centred on zero would understate the baseline
    disorder a responder already faces.
    """

    offsets_ms: dict[str, float]
    jitter_sd_ms: float = MEASURED_SD_OFFSET_MS
    delivery_ms: float = 250.0

    @classmethod
    def sample(cls, rng: random.Random) -> "ClockModel":
        return cls(offsets_ms={
            s: rng.gauss(MEASURED_MEDIAN_OFFSET_MS, MEASURED_SD_OFFSET_MS)
            for s in SOURCES
        })

    def observe(self, t_true_ms: float, source: str, rng: random.Random) -> tuple[float, float]:
        """Return (t_source, t_ingest) in milliseconds."""
        t_source = t_true_ms + self.offsets_ms.get(source, 0.0) + rng.gauss(0, self.jitter_sd_ms)
        t_ingest = t_true_ms + abs(rng.gauss(self.delivery_ms, self.delivery_ms / 4))
        return t_source, t_ingest


# --- events --------------------------------------------------------------

@dataclass
class Event:
    eid: int
    t_true_ms: float        # ground truth, never shown to a responder
    t_source_ms: float
    t_ingest_ms: float
    source: str
    asset: str
    action: str
    suspicious: bool
    cause: str              # ground truth: adversary | defender | ambient

    def observable(self) -> dict:
        """Exactly what a responder sees. The hidden fields are not present."""
        return {
            "id": self.eid,
            "time": round(self.t_source_ms, 1),
            "received": round(self.t_ingest_ms, 1),
            "source": self.source,
            "asset": self.asset,
            "action": self.action,
            "suspicious": self.suspicious,
        }


@dataclass
class Incident:
    iid: int
    events: list[Event]
    origin: str                 # ground truth origin asset
    chain: list[int]            # ground truth ordered event ids
    remediation: str            # what a correct reading supports
    seed: int

    def observable(self) -> list[dict]:
        """Delivered in ingest order, as a collector would present them."""
        return [e.observable() for e in sorted(self.events, key=lambda e: e.t_ingest_ms)]


# --- incident generation -------------------------------------------------

# A compromise chain: an account is taken, a session opens, a change is made,
# a control reacts. The control acting last is what makes reordering
# interesting, because a reader that puts it first sees a cause rather than a
# response.
CHAIN_TEMPLATE = (
    ("credential_use", "identity", True),
    ("session_open", "cloud", True),
    ("config_change", "cloud", True),
    ("account_blocked", "endpoint", False),
)

# The chain's action types, and the ambient ones. Whether these two sets
# overlap turns out to decide the whole experiment.
#
# With them disjoint, recognising the word "credential_use" identifies the
# origin outright and no ordering evidence is needed at all. A correlation rule
# over action types is then immune to any temporal perturbation, and so is any
# reader that knows the template. Measured, not assumed: see rule_baseline.py.
#
# With them shared, most credential events are benign, so "the earliest
# credential_use" needs the clock again and the attack can reach a reader that
# understands the words. That is also the realistic case: a real operation sees
# far more benign authentication than malicious.
CHAIN_ACTIONS = tuple(a for a, _, _ in CHAIN_TEMPLATE)
BENIGN_ACTIONS = ("login", "read", "heartbeat", "scan")

REMEDIATION = {
    "account": "revoke the account and rotate its credentials",
    "service": "isolate the service and review its configuration",
    "datastore": "restrict access and audit recent writes",
    "identity": "force reauthentication across the tenant",
    "host": "isolate the host and image it",
}


def make_incident(iid: int, seed: int, ambient: int = 6,
                  gap_range_ms: tuple[float, float] = (4000.0, 25000.0),
                  shared_vocab: bool = False, decoys: int = 2) -> Incident:
    """One incident with a known causal chain, plus ambient noise.

    `gap_range_ms` is the spacing between adjacent chain events. It is a
    controlled variable rather than a fixed constant, because the minimum
    effective perturbation is bounded below by the gap an adversary has to
    close. Fast automated intrusions produce small gaps; slow hands-on ones
    produce large gaps.
    """
    rng = random.Random(seed)
    clocks = ClockModel.sample(rng)

    accounts = [a.name for a in ASSETS if a.kind == "account"]
    origin = rng.choice(accounts)
    target = rng.choice([a.name for a in ASSETS if a.kind in ("service", "datastore")])

    events: list[Event] = []
    chain: list[int] = []
    t = float(EPOCH_BASE_MS)
    eid = 0

    for action, source, susp in CHAIN_TEMPLATE:
        t += rng.uniform(*gap_range_ms)
        asset = origin if action in ("credential_use", "account_blocked") else target
        ts, ti = clocks.observe(t, source, rng)
        events.append(Event(eid, t, ts, ti, source, asset, action, susp, "adversary"))
        chain.append(eid)
        eid += 1

    # Ambient activity spread across the same window, from other assets.
    span_lo, span_hi = float(EPOCH_BASE_MS), t
    others = [a for a in ASSETS if a.name not in (origin, target) and a.kind != "monitor"]
    for _ in range(ambient):
        a = rng.choice(others)
        tt = rng.uniform(span_lo, span_hi)
        ts, ti = clocks.observe(tt, a.source, rng)
        pool = (BENIGN_ACTIONS + CHAIN_ACTIONS) if shared_vocab else BENIGN_ACTIONS
        events.append(Event(eid, tt, ts, ti, a.source, a.name,
                            rng.choice(pool),
                            False, "ambient"))
        eid += 1

    # Decoy account pairs. Without these the origin is the only asset carrying
    # both a credential_use and an account_blocked, which locates it with no
    # ordering evidence at all - the same class of giveaway that made the
    # action vocabularies matter. Measured by shortcut_audit.py, not assumed.
    #
    # A decoy is deliberately the *reverse* pattern: the account is blocked
    # first and authenticates afterwards. That is a routine benign sequence, it
    # is not a compromise chain, and the only thing separating it from the real
    # origin is the order of the two events. A reader that ignores order cannot
    # tell them apart; a reader that respects order can.
    if shared_vocab and decoys:
        pool_accounts = [a for a in ASSETS
                         if a.kind == "account" and a.name != origin]
        rng.shuffle(pool_accounts)
        for a in pool_accounts[:decoys]:
            t_block = rng.uniform(span_lo, span_hi)
            t_use = t_block + rng.uniform(*gap_range_ms)
            for tt, action, src in ((t_block, "account_blocked", "endpoint"),
                                    (t_use, "credential_use", "identity")):
                ts, ti = clocks.observe(tt, src, rng)
                events.append(Event(eid, tt, ts, ti, src, a.name,
                                    action, False, "ambient"))
                eid += 1

    return Incident(iid, events, origin, chain,
                    REMEDIATION[BY_NAME[origin].kind], seed)


def corpus(n: int, base_seed: int = 20260920,
           gap_range_ms: tuple[float, float] = (4000.0, 25000.0),
           shared_vocab: bool = False, decoys: int = 2) -> list[Incident]:
    """`shared_vocab` selects the experimental condition.

    False reproduces the original corpus, where the chain's action types never
    appear in the noise. True lets ambient events use the same action types, so
    that knowing the vocabulary is no longer sufficient to locate the origin.
    """
    return [make_incident(i, base_seed + i, gap_range_ms=gap_range_ms,
                          shared_vocab=shared_vocab, decoys=decoys)
            for i in range(n)]
