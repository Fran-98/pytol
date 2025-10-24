# Terrain Deformation Behavior in Pytol

Pytol aims to mirror VTOL VR's terrain and city behavior as implemented in the game's Unity code.

## Summary

- Bases (airbases, carriers, FOBs) flatten the terrain within their footprint polygons.
  - Pytol detects base footprints from the map data and returns the flattened height when querying inside these zones.
- Procedural cities do not modify the terrain heightmap.
  - In VTOL VR, city meshes are conformed to the terrain via mesh deformation (per-vertex downward raycasts). The underlying terrain height remains unchanged.
  - Pytol mirrors this: city areas use natural terrain height. Buildings and roads are placed on the surface, and city roofs provide spawnable flat surfaces where defined.

## Details

- "Flattening" is applied only for base areas. Pytol uses the base's footprint polygon and a constant height derived from the base's placement to return a flat height inside the footprint.
- City blocks are inferred from the heightmap's G-channel (procedural city density) and a per-block layout database. Pytol computes block metadata (position, yaw, level) and bounding boxes for spawnable surfaces but does not override terrain height.

## Practical implications

- Use `get_terrain_height(x, z)`:
  - Inside a base footprint: you will get the flat base height.
  - Elsewhere (including cities): you will get height derived from the R-channel heightmap.
- Use `get_smart_placement(x, z, yaw)` to automatically snap placements to:
  - static prefab roofs (if a spawnable surface under the query point exists),
  - road surfaces,
  - or fall back to terrain.

## Notes

- If you observe a base that appears unflattened in Pytol, it may be due to a missing or unusual footprint in the map data. Please share the map and base name in an issue.
- If you need flat areas in city zones, prefer using static prefabs with spawnable rooftop surfaces; cities themselves are intentionally slope-following.

## Height Sampling Accuracy

### Expected Precision

Pytol uses **bilinear interpolation** on the heightmap texture to calculate terrain heights. Unity's engine uses a **terrain mesh with physics colliders** and raycasts. This fundamental difference leads to small discrepancies:

**Typical Accuracy (compared to in-game placement):**
- Roads on flat terrain: < 0.01 m error
- City roofs on flat terrain: < 0.1 m error
- Terrain on moderate slopes: ~1-3 m error
- City roofs on steep slopes: ~2-5 m error

### Why the Difference?

1. **Bilinear vs Mesh Interpolation**
   - Pytol: Pure mathematical bilinear interpolation between 4 nearest heightmap pixels
   - Unity: Terrain mesh with vertex-based interpolation, LOD, and smoothing

2. **Mathematical Sampling vs Physics**
   - Pytol: Direct heightmap texture sampling (`scipy.ndimage.map_coordinates`)
   - Unity: `Physics.Raycast()` or `Terrain.SampleHeight()` hitting actual mesh geometry with colliders

3. **Floating Point Precision**
   - Different computation paths (Python/NumPy vs C#/Unity)
   - GPU vs CPU terrain generation differences

### Practical Impact

For mission generation purposes, these sub-meter to few-meter differences are **negligible**:
- Units spawn correctly on terrain without falling through or floating significantly
- Waypoint placement is accurate enough for navigation
- The discrepancies are smaller than typical unit placement tolerances

### Known Map Issues

**hm_mtnLake:** This map exhibits a systematic height bias (~150–240 m negative, varying with elevation) compared to in-game placements.

What we found:
- The map's `hm_mtnLake.vtm` contains a `TerrainSettings { }` block that is present but empty (no stored `hm_minHeight`/`hm_maxHeight`).
- Regression on multiple reference points shows a linear mismatch between computed height and in-game placements:
  - y_calc ≈ 18.606 + 0.679617 × GivenY (fit on 10 samples)
  - Interpreting this as a save/load normalization mismatch implies the map was authored with approximate terrain bounds hm_min ≈ −145 m and hm_max ≈ 8801 m, while the game loads HeightMap maps with defaults hm_min = −80 m, hm_max = 6000 m. This yields both a scale and offset error.
- Other HeightMap maps (e.g., `hMap2`, `Archipielago_1`) carry the standard encoding and match within sub-meter to few-meter error.

Unity code context shows a known inconsistency in save vs load formulas for heightmaps:
- Save (VTMapCustom.cs): r = height / hm_maxHeight (assumes [0, max])
- Load (VTCustomMapManager.cs): height = Lerp(hm_minHeight, hm_maxHeight, r) (uses [min, max])

This means the encoding is only self-consistent when hm_minHeight = 0 and the same min/max pair is used at both stages. If a map was created with a different pair and that info isn't preserved, a linear bias occurs. We chose not to implement per-map workarounds to keep behavior aligned with the documented standard.

### Height Correction Parameters

`TerrainCalculator` accepts optional `height_scale` and `height_offset` parameters for experimental height corrections:

```python
from pytol import TerrainCalculator

# Optional height correction for maps with encoding issues
tc = TerrainCalculator(
    map_name="hm_mtnLake",
    vtol_directory=r"C:\Program Files (x86)\Steam\steamapps\common\VTOL VR",
    height_scale=1.21,      # Multiply all heights by this factor (default: 1.0)
    height_offset=58.7      # Add this offset in meters after scaling (default: 0.0)
)

# Normal usage (no corrections needed for most maps)
tc = TerrainCalculator(map_name="akutan", vtol_directory=vtol_path)
```

**Formula:** `corrected_height = (sampled_height × height_scale) + height_offset`

**Important:** Testing shows that **no simple linear correction reliably fixes hm_mtnLake**. While a linear fit (scale≈1.21, offset≈58.7) reduces average error, residuals remain large (40–125 m) across different terrain types and elevations. The discrepancy appears more complex than a simple scale/offset issue, possibly involving non-linear encoding, terrain generation differences, or compression artifacts.

These parameters are provided for experimentation but **should not be relied upon** for accurate height placement on problematic maps.

### Current Implementation

**Hardcoded behavior** in `terrain_calculator.py`:

- **Heightmap channel:** R channel for height data
- **Heightmap orientation:** Vertical flip applied (FlipUD=1)
- **Coordinate transform:** Auto-detected from map data (modes 0-7)
- **City block offset:** X=+10m, Z=−10m (constants `MANUAL_OFFSET_X` and `MANUAL_OFFSET_Z`)

No environment variable overrides are currently supported. All configuration is done via constructor parameters.
