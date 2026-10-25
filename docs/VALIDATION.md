# Validation record

## Historical Windows validation: 2026-10-11

These recorded results describe the previous implementation, not a new cross-platform run.

- Thirty Python/Lua 5.1 tests and the personal Lua format check passed after air support.
- Team game revision: `8775483821cc96788f85ad755ebc5341a654e2aa`, with its nested Lua library initialized.
- Actual-model graphical run `20261011-105749-0d4598`: 30-game-second draw, two decisions applied per team, ground/air factories observed, engine exit zero.
- Actual-model run `20261011-093904-51fcbc`: cloud victory at frame 3294 (109.8 game seconds), five valid decisions per team, no model errors. Local latency 1.281-1.359 seconds; cloud 0.547-1.266 seconds. This does not establish general model superiority.
- Air-production mock run `20261011-100527-d9db88`: 210 game seconds; both teams produced fighter, bomber, gunship, air scout, and antiair units. Thirty-nine commands per team, successful engine exit. This validates command plumbing, not model strategy.
- Actual-model air-enabled run `20261011-100821-ea6eb3`: 30 game seconds; both models chose ground actions. Air availability is not evidence of model air strategy.

Earlier fixes covered multiplied production counts, malformed messages, stale/duplicate requests, result delivery retries, Lua reload state, exclusive loopback ports, and Windows process exit reporting.

Tests cover authentication, call limits, concurrency, HTTP failures, command legality, queue limits, factory routing, air observations/commands, enemy visibility, economy limits, victory/draw, and reload/result handling. The full upstream BAR suite and long-duration profiling were not run.

## Meeting-alignment migration

Launch behavior is now Python. PowerShell only forwards legacy arguments. Recoil binaries/data remain external. Native macOS/Linux engine execution is unverified until tested on a separate host. Current revision test results are appended after execution.

Historical development commits remain in the personal game fork and its archive branch. The lab starts from a clean source snapshot. The personal game fork is restored separately without force-pushing. No personal feature is added to the team game.


## Windows migration checks: 2026-10-21

- All 37 Python/Lua 5.1 tests passed, including preparation with spaces in paths, conflicting-link protection, owned-process cleanup, configuration injection rejection, and isolation of model warm-up timeouts from match timeouts.
- Recursive submodule initialization passed; the pinned team checkout remains clean.
- Mock engine run `20261021-113418-78c9c1` exited with code zero after 30 game seconds. Five snapshots and two applied commands per team passed the log auditor. This was a launch/command-path smoke test, not a completed-match result.
- Initial cold content run `20261021-113022-bc9882` exceeded the former loading deadline and was stopped. The new configurable loading allowance defaults to 300 seconds; the successful mock run took about 212 wall-clock seconds.
- First real-model attempt `20261021-113845-633d01` correctly refused to start a game because local model cold loading exceeded the old 60-second readiness limit. Cloud readiness succeeded. Readiness now has its own 180-second allowance, while in-match request limits are unchanged.
- Desktop shortcut target and the legacy BAR install's content junction were checked after the submodule move.
- Native macOS/Linux game runs are still unverified. The POSIX link branch has a mocked contract test only.

- Final actual-model graphical run `20261021-114103-6bf131`: draw at frame 900 (30 game seconds), five snapshots, two valid decisions and two applied commands per team, zero model errors, engine exit zero. The result-required auditor passed. The local model produced units; the cloud model attacked. Local measured latency was 1.078 seconds; cloud 0.640-1.000 seconds. These are short smoke-test observations, not a benchmark.
- The bridge port 18765 had no listener after the match. Both CMD and legacy PowerShell preparation entry points exited successfully.


## Local council validation (2026-10-22)

- 54 Python/Lua regression tests pass, including independent tactical scheduling,
  threat invalidation, commander retreat, three-role notes, next-match memory
  loading, mock isolation, test-run persistence exclusion, and cloud Choice parsing.
- The first real council smoke test (30 seconds) exercised all three roles and
  saved nine scratchpad entries, but the cloud controller rejected two outputs
  that did not exactly match the offered action objects.
- A subsequent 45-second test exposed conflicting legacy action-format instructions
  inside the new Choice request. These instructions were removed from role input;
  the adapter now builds a single unambiguous Choice contract and maps identifiers
  to the shared action objects. Both actual models then returned valid Choice outputs
  in isolated checks. Neither failed run establishes controller quality.
- JEV has not been authenticated or called live. Its adapter has contract tests only
  and is disabled in the default configuration. No TypeSafe purchase was made.

- Final engine integration run: `20261022-194133-7ae34d`, actual models, 45 game
  seconds, normal engine exit, 44 snapshots, 13 tactical decisions per side,
  zero model errors, and 17 scratchpad entries covering all three local roles.
  The configured time limit produced a draw; this is a plumbing check, not a
  win-rate result. The run auditor passed and test-run memory persistence was off.
- That run exposed excessive local holding. Afterwards the role prompt removed
  a hold-specific example and explicitly discouraged idling without visible threats.
  Replaying the same real initial observation produced valid attack suggestions
  from strategy/tactics in about 1.4 seconds. The economy advisor was then restricted
  to production/investment/hold, and its live replay selected production in 1.16 seconds.
  Unit-role descriptions explicitly distinguish anti-air fighters from ground attack.
  These final prompt refinements have replay/contract validation, not another full
  engine match. Longer matches and repeated performance comparisons remain pending.

## Native map pilot (2026-10-24)

- Added two original, deterministic native maps: Ridge Pass and Twin Crossings.
- 60 Python/Lua tests passed. Both maps completed actual-model games in both
  physical start assignments; all three baseline/new-map position swaps verified.
- Six games exited normally. Four audits passed; baseline/reversed had two cloud
  JSON parsing errors and river/reversed had one. These runs remain flagged.
- Strategy/economy consultations and saved scratchpads were present in every run.
  Source hashes stayed fixed and previous-match memory was excluded.
- This is a short compatibility/behavior pilot, not evidence of learned terrain
  adaptation or a reliable win rate. See [full results](MAP_PILOT_RESULTS.md).
