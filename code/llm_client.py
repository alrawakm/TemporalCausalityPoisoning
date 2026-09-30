"""Clients for the language-model arm.

No provider library is imported here. A client is any callable that takes a
prompt and returns text, so the experiment does not depend on which vendor is
used and no quota is consumed by importing this module.

`CachedClient` is the important one. Responses are stored on disk keyed by the
hash of the prompt, so a rerun costs nothing, a crash loses nothing, and the
same prompt is never paid for twice. Every run of the experiment should wrap its
real client in it.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


class CachedClient:
    """Wraps any client with an on-disk cache and a hard call budget.

    The budget is not a convenience. An experiment that can silently spend more
    than intended is one that gets stopped halfway by a quota wall, and a
    half-finished sweep is worth nothing.
    """

    def __init__(self, inner, namespace: str, cache_dir: str = "cache",
                 budget: int = 200):
        """`namespace` identifies which client produced the responses.

        It is required, not optional. The cache key is a hash of the prompt and
        says nothing about which model answered, so a single shared directory
        lets one client's answers be served to another and reported as its own.
        That happened once here: a mock run drew 75 real Codex responses out of
        the shared directory and blended them into its own rates. A result
        published from that would have been wrong in a way no reader could see.
        """
        if not namespace:
            raise ValueError("a cache namespace is required; see the docstring")
        self.inner = inner
        self.dir = Path(cache_dir) / namespace
        self.dir.mkdir(parents=True, exist_ok=True)
        self.namespace = namespace
        self.budget = budget
        self.spent = 0
        self.hits = 0

    def key(self, prompt: str, nonce: int = 0) -> str:
        """The nonce separates repeats of an identical prompt.

        Repeats exist to measure the responder's own variance, so the prompt
        must be byte-identical across them. Keying the cache on the prompt
        alone would make every repeat a cache hit and report zero variance,
        which is worse than not measuring it. The nonce changes the cache slot
        and never reaches the model.
        """
        h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:32]
        return h if nonce == 0 else "%s_r%d" % (h, nonce)

    def __call__(self, prompt: str, nonce: int = 0) -> str:
        k = self.key(prompt, nonce)
        f = self.dir / (k + ".json")
        if f.exists():
            self.hits += 1
            return json.loads(f.read_text(encoding="utf-8"))["response"]
        if self.spent >= self.budget:
            raise RuntimeError(
                "call budget of %d exhausted after %d live calls and %d cache hits"
                % (self.budget, self.spent, self.hits))
        text = self.inner(prompt)
        self.spent += 1
        f.write_text(json.dumps({"prompt": prompt, "response": text}),
                     encoding="utf-8")
        return text

    def report(self) -> str:
        return "live calls %d, cache hits %d, budget %d" % (self.spent, self.hits, self.budget)


class MockSorterClient:
    """A client that behaves exactly like a clock-sorter.

    Its only purpose is to exercise the whole pipeline without spending
    anything: prompt rendering, response parsing, caching, scoring. If the
    experiment run against this client reproduces the deterministic result, the
    plumbing is correct and the only unknown left is the model.

    It is never reported as a condition. It is a test fixture.
    """

    def __init__(self, suspicious_actions=("credential_use", "session_open", "config_change")):
        self.suspicious = set(suspicious_actions)

    def __call__(self, prompt: str) -> str:
        rows = []
        for line in prompt.splitlines():
            if not line.startswith("id="):
                continue
            f = dict(p.split("=", 1) for p in line.split() if "=" in p)
            rows.append(f)
        rows.sort(key=lambda r: float(r["time"]))
        for r in rows:
            if r["action"] in self.suspicious:
                return "ORIGIN: %s\nREMEDIATION: contain %s" % (r["asset"], r["asset"])
        return "ORIGIN: NONE\nREMEDIATION: none"


def anthropic_client(model: str = "claude-opus-5", max_tokens: int = 300,
                     effort: str = "low"):
    """Real client. Imported lazily so this module stays dependency-free.

    Two configuration choices are experimental rather than stylistic.

    **Effort is low, to match the other arm.** The Codex run reported
    "reasoning effort: low". Running this arm at the default high effort would
    compare a model thinking hard against a model thinking little and attribute
    the difference to the vendor. Effort is the confound to control first.

    **No server-side refusal fallback, deliberately.** The general
    recommendation is to enable it, because a refused request otherwise just
    stops. Here the model identity is the independent variable: a fallback would
    let some responses in this arm come from a different model, with nothing in
    the output to show which. That is the cache-namespacing mistake in another
    form. A refusal is recorded as a refusal instead.
    """
    import anthropic
    c = anthropic.Anthropic()          # resolves the key from the environment

    def call(prompt: str) -> str:
        r = c.messages.create(
            model=model,
            max_tokens=max_tokens,
            output_config={"effort": effort},
            messages=[{"role": "user", "content": prompt}],
        )
        if r.stop_reason == "refusal":
            cat = getattr(getattr(r, "stop_details", None), "category", None)
            return "ORIGIN: NONE\nREMEDIATION: __REFUSED__ %s" % cat
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    return call


def openai_client(model: str = "gpt-5.6-terra", max_tokens: int = 300):
    """Real client for the configuration Five Bits used."""
    import openai
    c = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def call(prompt: str) -> str:
        r = c.chat.completions.create(model=model, max_tokens=max_tokens,
                                      messages=[{"role": "user", "content": prompt}])
        return r.choices[0].message.content or ""
    return call


def _find_codex_exe() -> str:
    """The Codex CLI reinstalls itself under a new content-hash directory on
    every auto-update, so a path pinned to one hash goes stale (as happened
    here: eab8377aebac6c07 no longer exists). Resolve the current one instead,
    picking the most recently modified copy if more than one is present."""
    import glob
    pattern = os.path.expandvars(r"%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe")
    candidates = glob.glob(pattern)
    if not candidates:
        return r"C:\Users\User\AppData\Local\OpenAI\Codex\bin\eab8377aebac6c07\codex.exe"
    return max(candidates, key=os.path.getmtime)


CODEX_EXE = _find_codex_exe()

CODEX_SCHEMA = {
    "type": "object",
    "properties": {
        "origin": {"type": "string",
                   "description": "the asset where the incident originated, or NONE"},
        "remediation": {"type": "string",
                        "description": "one short sentence"},
    },
    "required": ["origin", "remediation"],
    "additionalProperties": False,
}


def codex_client(exe: str = CODEX_EXE, model: str | None = None,
                 timeout_s: int = 300, retries: int = 3,
                 backoff_s: float = 4.0):
    """Drive the Codex CLI non-interactively. Spends subscription, not API credit.

    This is the path the Five Bits corpus used, and `--output-schema` is the
    reason: it constrains the final message to a JSON object, so the answer does
    not have to be recovered from prose. The schema arm has no chat-completions
    equivalent, which is why that paper's SCHEMA condition is Codex-only.

    Flags, each for a reason:
      exec                     non-interactive
      -                        prompt arrives on stdin
      --output-schema FILE     final message constrained to {origin, remediation}
      -o FILE                  final message only, without the agent's chrome
      -s read-only             the responder answers a question; it must not write
      --ephemeral              do not persist a session file per call, 80 of them
      --skip-git-repo-check    the code directory need not be a repository
      --color never            no escape codes in the captured text
    """
    import subprocess
    import tempfile
    import time

    schema_f = Path(tempfile.gettempdir()) / "tcp_origin_schema.json"
    schema_f.write_text(json.dumps(CODEX_SCHEMA), encoding="utf-8")

    def once(prompt: str) -> str:
        out_f = Path(tempfile.mkdtemp()) / "last.txt"
        argv = [exe, "exec",
                "--output-schema", str(schema_f),
                "-o", str(out_f),
                "-s", "read-only",
                "--ephemeral",
                "--skip-git-repo-check",
                "--color", "never"]
        if model:
            argv += ["-m", model]
        argv.append("-")
        p = subprocess.run(argv, input=prompt, capture_output=True,
                           text=True, timeout=timeout_s)
        if not out_f.exists():
            # Keep the whole of stderr. An earlier version truncated it to 400
            # characters and the one failure in eighty was undiagnosable as a
            # result, which cost a rerun rather than a fix.
            raise RuntimeError("codex exit %d, no output file.\n--- stderr ---\n%s"
                               % (p.returncode, p.stderr or "(empty)"))
        return out_f.read_text(encoding="utf-8", errors="replace").strip()

    def call(prompt: str) -> str:
        # A single agent invocation fails occasionally. One failure must not
        # discard a sweep that is otherwise complete, so retry with backoff and
        # only give up when the failure looks deterministic.
        last = None
        for attempt in range(retries):
            try:
                raw = once(prompt)
                break
            except Exception as e:                       # noqa: BLE001
                last = e
                if attempt < retries - 1:
                    time.sleep(backoff_s * (2 ** attempt))
        else:
            raise RuntimeError("codex failed %d times. last error:\n%s" % (retries, last))

        # The schema makes this JSON. Fall back to the plain form if a future
        # version stops honouring it, rather than failing the whole sweep.
        try:
            d = json.loads(raw)
            return "ORIGIN: %s\nREMEDIATION: %s" % (d.get("origin", "NONE"),
                                                    d.get("remediation", ""))
        except json.JSONDecodeError:
            return raw
    return call


def subprocess_client(argv: list[str], prompt_on_stdin: bool = True,
                      timeout_s: int = 180):
    """Drive any CLI that reads a prompt and writes an answer.

    This is the path that spends no new money when a coding-agent CLI is already
    subscribed, and it is how the Five Bits corpus was produced. The exact
    invocation is left to the caller because CLI surfaces change: check
    `<tool> --help` for the non-interactive form before wiring it, rather than
    trusting an argv written here.

    Example, once the correct form is confirmed:
        subprocess_client(["codex", "exec", "--quiet"])
    """
    import subprocess

    def call(prompt: str) -> str:
        if prompt_on_stdin:
            p = subprocess.run(argv, input=prompt, capture_output=True,
                               text=True, timeout=timeout_s)
        else:
            p = subprocess.run(argv + [prompt], capture_output=True,
                               text=True, timeout=timeout_s)
        if p.returncode != 0:
            raise RuntimeError("client exited %d: %s" % (p.returncode, p.stderr[:400]))
        return p.stdout
    return call
