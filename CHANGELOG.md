# Changelog

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
