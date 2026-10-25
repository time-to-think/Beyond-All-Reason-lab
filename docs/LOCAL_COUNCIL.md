# Local specialist council and scratchpad

The default controller is now a three-agent local council against GPT-OSS 120B
Cloud. JEV is disabled and no TypeSafe account or payment is needed.

All three local agents currently use the installed Qwen 3.5 4B weights, with
separate role prompts and requests. This is role-specialized collaboration using
one resident model, not three different trained models or three copies in VRAM.

| Role | Responsibility | Execution authority |
| --- | --- | --- |
| Strategy | Recommend a force-building or attack objective | Advisory only |
| Economy | Recommend resource investment and unit composition | Advisory only |
| Tactical coordinator | Read both specialists' notes and current threats, choose an action | Issues the final command |

The two advisors run in a background cycle every 20 seconds. They are consulted
sequentially to limit contention on a small GPU. Tactical decisions have a separate
worker and normally start every 3 seconds, with a 1-second cooldown for new threat
events. The tactical worker does not wait for the advisors to finish. The Ollama
server may still queue requests internally; this design does not guarantee parallel
GPU execution or faster responses. Measure actual latency before increasing call rates.

The final coordinator is allowed to disagree with advisors. This is advisory
collaboration, not majority voting. Each role returns a bounded action suggestion
and a short English note containing evidence and a recommendation. The Python
bridge validates the selection against currently offered actions. Both teams use
the same observed game fields, action options, tactical timeout, and execution code.
The local team has extra advisory calls and memory; this is intentionally a comparison
of complete systems, not an equal-compute benchmark.

## Scratchpad

Each run directory contains:

- `scratchpad.json`: up to 60 recent entries with role, game frame, recommendation,
  short model note, and observed resources, unit count, commander health, and enemy count.
- `scratchpad.md`: a readable view of those entries and the final result.

The most recent two entries per role are supplied to subsequent decisions so
tactical updates do not immediately crowd out advisory notes. Completed real
matches also save bounded history in `memory/local-council.json` under the runtime
root. Five completed matches are retained; the latest two are supplied to future
roles. Outcomes, model identities, map, and the latest note per role travel together.
The memory file is outside the Git checkout and is not uploaded.

Mock runs neither read nor update real history. Runs started with `--test-seconds`
can read history but never add their artificial time-limit result to it. Interrupted runs retain their
own scratchpad but do not become completed-match experience. Corrupt history
produces a visible `load_warning` in the new scratchpad and starts with empty history.
Notes are fallible model hypotheses. Saving a note next to a win or loss does not
prove causality, update model weights, or implement reinforcement learning. The
prototype does not yet perform automatic post-match model critique or memory retrieval
by scenario similarity. Use an isolated `--runtime-root` for independent experiments.

## Launch and limits

Use the existing desktop shortcut or `Start-LLM-Duel.cmd`. The default configuration
requires only the existing Ollama local model and Ollama Cloud authentication.
No JEV request is made while `hybrid_enabled` is false.

The default permits 360 tactical calls per side and 45 advisory cycles (up to 90
local advisor calls). Tactical timeout and command expiry are 10 seconds. Old
commands are rejected after a new threat event, and failed requests do not silently
switch models. Orders already running remain active. The shared game mode still
uses bounded macro actions rather than full BAR control.

Keep `local_council_enabled` and `hybrid_enabled` mutually exclusive. The optional
JEV prototype is documented in `HYBRID_DUEL.md`; it is not the current launch mode.
