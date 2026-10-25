# Map pilot: 2026-10-24

Two original native BAR maps were generated and exercised against the existing baseline. This is a six-game compatibility and behavior pilot, not a win-rate benchmark.

## Protocol

- Local: Qwen3.5 4B, strategy/economy/tactical roles sharing one resident model and a scratchpad.
- Opponent: GPT-OSS 120B Cloud via Ollama, solo controller.
- Three maps, one normal and one physically reversed start assignment per map; seed 42; 180 game-second limit.
- Sequential games; identical controller source/configuration; fresh batch with within-match notes only.
- Model calls remain stochastic. Position swaps were verified from engine observations.
- Win: commander destruction; draw: time limit. Initial army: six ground tanks per side.
- Generated maps: 8192 x 8192 world units, flat symmetric starts, no metal deposits or reclaim, fixed-income duel mode.
- Baseline: Comet Catcher Remake, 6144 x 8192. Baseline comparisons also change size, start distance, and decoration.

## Results

| Map | Starts | Result | Duration (s) | First sight L/C (s) | Max ready air L/C | Model errors | Audit |
| --- | --- | --- | ---: | --- | --- | ---: | --- |
| baseline | Normal | Draw | 180.0 | 51.0/51.0 | 0/0 | 0 | Pass |
| ridge | Normal | Local council | 79.5 | 32.0/32.0 | 0/0 | 0 | Pass |
| river | Normal | Cloud | 165.9 | 56.0/55.0 | 0/0 | 0 | Pass |
| baseline | Reversed | Draw | 180.0 | 59.0/59.0 | 0/2 | 2 | Flagged |
| ridge | Reversed | Cloud | 113.1 | 34.0/34.0 | 0/0 | 0 | Pass |
| river | Reversed | Local council | 72.0 | 57.0/58.0 | 0/0 | 1 | Flagged |

## Interpretation and limits

- Both new native maps loaded and completed real-model matches in both start assignments.
- In river/normal at 30 seconds, opposing tank groups used different crossings (approximately z=5300 and z=2900). By 60 seconds they had reached opposite bases. This confirms actual ground detours, not a blocked route.
- The normal ridge game had first contact at 32 seconds, versus 55-56 seconds on the river. This describes these runs; it does not isolate a causal terrain effect.
- The local coordinator frequently chose attack despite economy advice. Role separation and saved notes do not guarantee balanced production or useful coordination.
- Ready aircraft were observed in the baseline/reversed game. No aircraft counterfactual was forced, so aircraft availability is distinct from strategic terrain exploitation.
- Cloud JSON parsing errors in baseline/reversed (two) and river/reversed (one) are retained and flagged, not hidden by rerunning until clean. An error affects controller availability and weakens comparisons. Four of six run audits passed.
- Ridge winners started on the west in both games; river winners started on the east in both games. With one run per assignment and stochastic outputs, this cannot establish a physical-side advantage.
- The agent receives map identity, dimensions, and unit observations, not a terrain grid or passability graph. Native engine pathfinding chooses routes. These games do not demonstrate learned map adaptation.
- No fine-tuning, new-unit experiment, scratchpad ablation, or repeated-seed performance study was performed.
- Next experiment: expose terrain/crossing information, compare council versus solo with and without notes, and repeat paired seeds with longer time limits.

## Validation

- 60 Python/Lua tests passed, covering map binary structure, geometry, launcher configuration, packed-game caching, and report edge cases.
- All six games exited normally. Audit flags are listed above; a completed game is not automatically an error-free game.
- All three physical start swaps verified. Controller and map-generator SHA-256 hashes remained unchanged throughout the pilot.
- Team submodule stayed clean at `8775483821cc96788f85ad755ebc5341a654e2aa`; no team repository upload was performed.
- Generated binary archives and raw logs remain outside versioned source. The generator is the reproducible source artifact.

## Per-game detail

### baseline / normal

Run ID: `20261024-195702-b7c3d9`. Advisor results: {"strategy": 9, "economy": 9}. Scratchpad saved: yes.
Audit issues: [].
Tactical selections local/cloud: {"attack": 55} / {"economy": 2, "attack": 37, "produce": 11, "defend": 3}.
Stale decisions rejected local/cloud: 6/0.
Decision latency p50 local/cloud: 1.329/0.781 s; p95: 2.219/1.297 s.
Selection counts include stale decisions; they are not counts of successfully applied commands.

### ridge / normal

Run ID: `20261024-200132-95a29f`. Advisor results: {"strategy": 4, "economy": 4}. Scratchpad saved: yes.
Audit issues: [].
Tactical selections local/cloud: {"produce": 1, "attack": 26} / {"attack": 17, "produce": 5, "defend": 4, "economy": 1}.
Stale decisions rejected local/cloud: 6/3.
Decision latency p50 local/cloud: 1.469/0.891 s; p95: 2.703/1.375 s.
Selection counts include stale decisions; they are not counts of successfully applied commands.

### river / normal

Run ID: `20261024-200328-4553e5`. Advisor results: {"strategy": 8, "economy": 8}. Scratchpad saved: yes.
Audit issues: [].
Tactical selections local/cloud: {"attack": 43, "produce": 7} / {"attack": 39, "produce": 15, "economy": 1}.
Stale decisions rejected local/cloud: 7/0.
Decision latency p50 local/cloud: 1.368/0.719 s; p95: 2.469/1.157 s.
Selection counts include stale decisions; they are not counts of successfully applied commands.

### baseline / reversed

Run ID: `20261024-200650-48ab00`. Advisor results: {"strategy": 9, "economy": 9}. Scratchpad saved: yes.
Audit issues: ["Model request errors occurred"].
Tactical selections local/cloud: {"attack": 53} / {"produce": 28, "attack": 22, "economy": 2, "defend": 1}.
Stale decisions rejected local/cloud: 4/0.
Decision latency p50 local/cloud: 1.438/0.844 s; p95: 2.391/1.265 s.
Selection counts include stale decisions; they are not counts of successfully applied commands.

### ridge / reversed

Run ID: `20261024-201025-4fd461`. Advisor results: {"strategy": 6, "economy": 6}. Scratchpad saved: yes.
Audit issues: [].
Tactical selections local/cloud: {"attack": 37, "produce": 1} / {"economy": 1, "produce": 11, "attack": 22, "defend": 3}.
Stale decisions rejected local/cloud: 5/1.
Decision latency p50 local/cloud: 1.398/0.719 s; p95: 2.625/1.250 s.
Selection counts include stale decisions; they are not counts of successfully applied commands.

### river / reversed

Run ID: `20261024-201254-ea661f`. Advisor results: {"strategy": 4, "economy": 4}. Scratchpad saved: yes.
Audit issues: ["Model request errors occurred"].
Tactical selections local/cloud: {"attack": 22} / {"attack": 15, "produce": 6, "economy": 1}.
Stale decisions rejected local/cloud: 6/0.
Decision latency p50 local/cloud: 1.446/0.735 s; p95: 2.640/0.953 s.
Selection counts include stale decisions; they are not counts of successfully applied commands.
