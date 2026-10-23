# Changelog

## 0.7.0

- `Mission` event helpers: `on_enter`, `on_condition`, `timer`, `sequence`, `random_choice`, `when`, `next_objective_id`.
  `sequence` fires a step after its condition (the game waits the delay first).
- `pytol.logic`: condition algebra (`&`, `|`, `~`), counters, flags, `Players`/`Unit`/`Units` conditions, phase machine.
- `pytol.patterns`: conditional and counter objectives, `tally`, `contingency` (plan B), `capture_base`.
- `vts_validator` checks every `SCCUnit` / `SCCUnitList` / `SCCUnitGroup` / `SCCStaticObject` condition against
  `vt_conditions.json` (the game's condition methods per class); `save_mission` logs the loader check.
- `pytol.parsers.vts_analyzer` (logic-graph analysis) and `pytol.analysis.simulate` (duration and intensity estimate).
- `MissionTerrainHelper`: `find_open_land`, `find_land_in_band`, `find_open_water`, `water_loop`, `point_along`, `is_land`,
  `is_water`, `in_map`.
- `pytol.classes.unit_catalog`: stationary classes, footprints, SAM systems, `can_join_group`, `team_of`.

## 0.6.0

- `ConditionalAction` now writes the game's full IF / ELSE IF / ELSE statement: `else_if`, `else_actions` and `nested`
  blocks (`ConditionalBlock`). Block ids are unique across the file, as the game requires.
- `TerrainCalculator.is_area_clear` for ground placement among buildings and static prefabs.
- Audio resources, carrier spawns, objectives on moving units, campaign saving with LF line endings.
- `import pytol` no longer fails when an optional visualization backend is installed but broken.
- `mission_creation.md` rewritten against the real API (objectives, conditionals, if/else, global values, sequences).
- Requires Python 3.8 or newer.

## 0.5.0

Initial public release.
