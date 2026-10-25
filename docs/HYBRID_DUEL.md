# Local strategy + JEV versus cloud control

This optional, currently disabled configuration uses Qwen 3.5 4B for strategic guidance, JEV 1.13 for
team 0 action selection, and GPT-OSS 120B Cloud for team 1 action selection.
This is a prototype controller, not a demonstrated improvement in win rate.

## Execution

- Local strategy updates run independently every 20 wall-clock seconds, with at
  most 45 requests per match. The current prototype expresses a strategy as a
  cached action objective, not a detailed multi-step plan. It never executes a
  strategy response directly. JEV can act before the first strategy completes.
- Both tactical controllers normally run every 3 wall-clock seconds. New visible
  enemies, first commander damage, or a commander health-band transition permit
  another decision after a 1-second cooldown. Only one tactical call per team
  can be in flight; HTTP calls are not forcibly cancelled on new observations.
- The game publishes observations every game second. Transport polls every
  0.1 wall-clock seconds. These are sampling intervals, not guaranteed reaction
  times. Network delay, rendering, and game speed also affect response time.
- Both sides receive the same observation fields and generated action options:
  production, economy, attack base, defend base, retreat, and hold. Retreat moves
  the army and commander; attack/defend control the army only. Own units expose
  position, health, build progress, and current command ID. Enemy data remains
  line-of-sight restricted. Neither side gains automatic tactical defense.
- Tactical calls time out after 5 seconds and have a 360-call limit per team.
  Command expiry is configured by `command_max_age_frames`; the current shared configuration uses 300 frames (10 game seconds). Changed threat events
  invalidate outstanding tactical decisions. Factory availability and queue
  capacity are checked again before delivery and in the game.
- Model errors are logged without response bodies or credentials. There is no
  silent model substitution. Failed calls leave existing game orders in effect.
  This means network failure can lose a match and must be reported in evaluation.

## Credentials and starting

Obtain a key from the official TypeSafe console at https://console.typesafe.ai.
Ollama authentication cannot authenticate TypeSafe calls. The adapter only sends
keys to https://api.typesafe.ai/v1/systemone and rejects redirects.

First select `hybrid_enabled: true` and `local_council_enabled: false` in the configuration.
Run `Setup-JEV-and-Start.cmd` to enter a key privately and start a match. The key
is held in the launch process environment for that session, not saved to a file,
printed, or included in game scripts. Enter it again on the next launch. Users
who already provide `TYPESAFE_API_KEY` through their environment can continue
using `Start-LLM-Duel.cmd`. The launcher removes the key from the game process
environment; the bridge and readiness check need it.

Without a key, a real hybrid launch stops with setup instructions. `--mock`
tests the scheduler and engine without invoking any model, and `--prepare-only`
checks paths and creates launch files. Neither proves JEV authentication or skill.
Setting `hybrid_enabled` to false selects the previous direct-LLM bridge.

## Measurement and limitations

The event log distinguishes `strategy` from tactical `decision` events and
records model-reported token usage for JEV. The model ID is pinned for reproducibility.
The two sides share tactical call limits, but team 0 has extra local planning
calls. This is a system comparison, not an equal-total-compute model benchmark.

Compare repeated matches with swapped sides, then ablate local planning and JEV
separately before attributing any gain to the combination. Report response delay,
errors, wins, API tokens, and local resource use. Long games may exhaust the call
budget; the initial limit is deliberately bounded. This implementation does not
yet provide automated side swaps, ablation orchestration, learned memory, or
training. Per-unit micro and arbitrary attack destinations are outside the shared
candidate set in this first prototype.

Official references:
- https://docs.typesafe.ai/api/system-one
- https://docs.typesafe.ai/primitives/choice
- https://docs.typesafe.ai/models
