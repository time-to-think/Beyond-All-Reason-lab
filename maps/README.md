# Original BAR map fixtures

`build_maps.py` generates two original 16x16 (8192x8192 world-unit) maps from
deterministic height functions. No external map textures or map geometry are copied.
It writes native SMF/SMT data inside SDZ archives, a manifest with SHA-256 checksums,
and SVG overviews. Binary outputs live in the runtime directory, not in Git.

| Map | Geometry | Experiment question |
| --- | --- | --- |
| BAR Lab Ridge Pass v1 | A tall central ridge with one 960-unit-wide flat passage | Does army movement or concentration at a choke change combat? |
| BAR Lab Twin Crossings v1 | A river with two flat land crossings, each with a 720-unit-wide core | Does a ground detour change contact time or aircraft use? |

Both maps are rotationally symmetric and have equal, flat starting areas. The
palette textures are deliberately simple research fixtures. They have no metal
deposits or decorative reclaim, so use them with the lab's fixed-income duel mode;
they are not complete standard BAR economy maps. Terrain deformation is disabled.

Build: `python maps/build_maps.py /path/to/output`

Launch: `python launcher/start_duel.py --map ridge` or `--map river`.
The root `Start-Ridge-Duel.cmd` and `Start-River-Duel.cmd` are Windows shortcuts.
The existing desktop entry remains on its original default map.

`--swap-starts` exchanges explicit starting positions. Custom maps supply their
positions automatically; the baseline requires coordinates captured from its first
match. `launcher/map_pilot.py` performs that capture and checks the resulting swap.

## Pilot protocol

`python launcher/map_pilot.py --minutes 3` runs one seed (42), three maps, and two
physical starting-position assignments, sequentially. Each game has a three-minute
limit. Qwen's three-role council and GPT-OSS Cloud retain the same configuration.
Within-match scratchpads remain active, but no cross-match memory is loaded from
normal play or written by the pilot. The initial batch directory is fresh.

The pilot measures map compatibility and descriptive outcomes under fixed model
weights. It does not train a policy, demonstrate learned adaptation, isolate the
benefit of scratchpads, or estimate reliable win rates. The original baseline differs
in dimensions, natural terrain, and resource decoration, so comparisons with it are
not a controlled change of one terrain variable. The two generated maps share size,
start coordinates, resources, and palette but differ in geometry.

The current agent receives map name, dimensions, and unit observations, not a full
terrain grid or path graph. Native game pathfinding handles movement to chosen
targets. This limitation must accompany any interpretation of terrain adaptation.

Map format reference: https://github.com/beyond-all-reason/RecoilEngine/blob/master/rts/Map/SMF/SMFFormat.h
