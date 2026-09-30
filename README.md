# Temporal Causality Poisoning — reproducibility release

Code, raw decision records and run logs for *Rewriting the Attack Without
Changing the Logs: Temporal Causality Poisoning of Autonomous Incident
Responders*.

The paper measures what an autonomous incident responder gets wrong when the
apparent timing of events is shifted within the clock skew a real deployment
already tolerates, with nothing deleted and nothing injected. Three responder
designs are compared under an identical adversary: a deterministic
clock-sorter, a typed correlation rule, and a language-model responder run
against two vendors (Anthropic `claude-opus-5` and OpenAI `gpt-6-astra`
through Codex).

## What is actually in here

- **`code/`** — the incident generator, the perturbation transformations, the
  bisection driver for the deterministic sweep, the multiple-schedule driver
  for the language-model arm, the three responder implementations, the
  standing shortcut audit, and the final raw decision records:
  `llm_results.json` (Codex, condition A, 420 calls), `llm_B.json` (Codex,
  condition B, 180 calls), `llm_A_anthropic.json` and `llm_B_anthropic.json`
  (Claude, 180 calls each).
- **`code/cache/`** — every cached model response, namespaced by
  provider/model/condition so no run can be served another run's cached
  answer. This is what makes a rerun cost nothing and a crash lose nothing.
- **`logs/`** — the console output of every run that produced a result
  reported in the paper, each one printing the topology hash, the seed and
  the condition before generating a single incident.
- **`skew_measurement.md`** — the admissible perturbation range the paper's
  central bound depends on, with the documented protocol thresholds it is
  taken from and the local measurement kept only as context. This is the one
  input a reader is most entitled to check independently of anything else
  here.
- **`development-notes/`** — the partial-result writeups from earlier,
  incomplete runs during development, kept for the audit trail rather than
  deleted. **These are superseded by the JSON files in `code/` and should not
  be quoted as current results.** They record two corpus defects found and
  fixed (an order-free shortcut through the chain's own vocabulary, and a
  second one through a co-occurring event pair) and are referenced in the
  paper's own Methodology section for that reason.

## Reproducing a result

The incident generator is seeded (`soc.py`, seed `20260920`) and
deterministic. The same seed and the same generator and topology hashes,
printed at the top of every log in `logs/`, reproduce every event byte for
byte.

```bash
cd code
python run_deterministic.py        # the clock-sorter family matrix
python rule_baseline.py            # the typed correlation rule, both conditions
python shortcut_audit.py           # the standing order-free-shortcut check
```

The language-model arm needs a provider key set as an environment variable
(`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`) and reads from `code/cache/` before
making a live call, so rerunning it against the same corpus and the same
multiples costs nothing:

```bash
python run_llm.py --provider anthropic --model claude-opus-5 \
    --multiples 0,1,2 --repeats 3 --budget 200 --out llm_A_anthropic.json
python run_llm.py --provider anthropic --model claude-opus-5 --shared \
    --multiples 0,1,2 --repeats 3 --budget 200 --out llm_B_anthropic.json
```

`check_key.py` diagnoses a provider key that is set but not working, by
error class rather than by traceback.

## What this is not

This is not a claim that the responders tested are unusually weak. The
deterministic clock-sorter is a null model, not a claim about deployed
practice, and the typed correlation rule exists specifically to answer the
objection that no deployed system reconstructs an incident by sorting raw
timestamps. Neither language model is claimed to be representative of the
class. The comparison across three designs, not any single result, is the
paper's contribution.

## License

No license file is included. Contact the author before reuse.
