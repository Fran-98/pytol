# Copilot Instructions for pytol

## Project Overview
- **pytol** is a Python library for procedural mission generation for VTOL VR, focusing on automation, terrain analysis, and scenario scripting.
- Major components: terrain analysis, object/asset placement, mission/campaign file generation, tactical queries, and visualization (2D/3D).
- Codebase is highly consolidated: use helpers in `pytol.misc.math_utils`, `pytol.procedural.position_scoring`, and `pytol.misc.validation_framework` instead of duplicating logic.

## Key Conventions & Patterns
- **Always use consolidated utilities** (see `pytol/misc/quick_reference.py`) for math, position, and validation tasks. Do not reimplement distance, angle, or formation logic.
- **Mission creation**: Use the `Mission` class (`from pytol import Mission`) for all mission/campaign generation. Add units, waypoints, objectives, and triggers via its methods.
- **Map support**: Only heightmap-based maps are supported (e.g., `hMap2`, `costaOeste`, `Archipielago_1`). Do not use Akutan.
- **Testing**: Systematic tests for all mission systems are in `test_missions/`. Each `test_*.py` file validates a specific VTOL VR system. Use these as reference for new features.
- **Visualization**: 2D (matplotlib) and 3D (PyVista) visualizations are optional. Use `Map2DVisualizer` and `save_mission_map` for static maps; see `pytol/visualization/README.md`.
- **Procedural generation**: Use high-level tactical queries and pathfinding helpers for scenario logic. Avoid hardcoding positions or logic that can be derived from terrain analysis.

## Developer Workflows
- **Install**: `pip install -e .` for local dev; use `[viz]` or `[viz-light]` for visualization features.
- **Run examples**: See `examples/` for campaign, mission, and visualization demos.
- **Test**: Run scripts in `test_missions/` to validate mission system output. Validate generated `.vts` files in-game.
- **Documentation**: See `docs/mission_creation.md` for mission scripting, and `pytol/misc/quick_reference.py` for API usage.

## Integration & Structure
- **External dependencies**: numpy, pillow, scipy, (see `pyproject.toml`). Visualization requires matplotlib or pyvista.
- **Directory structure**:
  - `pytol/` - main library (classes, misc, parsers, procedural, resources, terrain, visualization)
  - `examples/` - usage demos
  - `test_missions/` - system validation scripts
  - `docs/` - guides and reference

## Examples
- Mission creation: `examples/operation_pytol.py`, `docs/mission_creation.md`
- Math/position helpers: `pytol/misc/quick_reference.py`
- System tests: `test_missions/test_*.py`

## Special Notes
- Always check for existing helpers before adding new logic.
- Document new reusable helpers in `quick_reference.py`.
- For VTOL VR file paths, use raw strings (e.g., `r"F:\\SteamLibrary\\steamapps\\common\\VTOL VR"`).
- See `CONSOLIDATION_SUMMARY.md` for rationale behind framework structure.
- We have access to the unity project of the game, so for any complex behavior, we can refer to the original implementation for guidance. This is the path: `E:\VTOL VR UNITY\Assets`.