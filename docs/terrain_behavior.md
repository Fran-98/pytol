# Terrain Behavior in Pytol

`TerrainCalculator` reproduces what the game computes, following the decompiled game code.

## Height

- `get_terrain_height(x, z)` = `max(0, lerp(-80, 6000, R))`, with `R` the red channel of `height.png` sampled
  bilinearly at `uv * (size - 1)` (`VTMapGenerator.GetHeightmapAltitude`). `-80` / `6000` are the game's
  constants for every heightmap map; they are not stored in the `.vtm`.
- The image rows are flipped on load because Unity textures start at the bottom-left corner.
- Accepts scalars or NumPy arrays (vectorized sampling).

## Flattened areas

- Structure prefabs with `doFlatten` flatten the ground like `VTTModFlatRect`: flat at the prefab height inside
  their rectangle, then a linear blend back to the natural terrain over `flattenRadius` meters.
- Only `airbase1`, `airbase2`, `airbase3` and `dock1` flatten terrain. Their rectangles come from the prefab data
  (`FLATTEN_PREFABS` in `terrain_calculator.py`).
- Cities do not change the terrain: city meshes follow it.

## Cities

- A city block exists on every heightmap vertex whose 2x2 pixel quad has `G > 0.1` (`VTMapCities`).
- Level = `floor((G - 0.2) / 0.8 * 5)`, layout picked with the noise texture, yaw from the pixel parity
  (`CityBuilderPixel.SetRotation`).
- `world_position` of a block is its `RotationTf` pivot: vertex position + `(87.75, 0, 63.75)`
  (`CityBuilderPixel.pixelCenterPoint`). Layout surface bounds are relative to that pivot.

## Roads

- `road_segments`: `(start, end)` polylines sampled from the `.vtm` Bezier roads, plus approximate city streets.
- `get_road_route(start_xz, end_xz)`: shortest route over the Bezier network, linked by `ns`/`ps`,
  `Intersection` nodes and shared endpoints. A map can have several disconnected networks; the route is
  empty when the two points are on different ones.
- Bridge segments keep their deck height (`nearest_road(...)['is_bridge']`, `get_all_bridges()`).

## Accuracy

Measured with `tests/test_terrain_calculator.py` on 17 custom maps:

- Static prefabs (ground truth saved by the editor): median error 0-2 m on every map.
- Road control points: median error ~0 m on most maps. Roads are smoothed, so single points can be off by
  ~10 m on bumpy terrain.

## Not modelled

- Near the map edge, Coast and Hills maps blend toward the out-of-bounds terrain
  (`VTTHeightMap.GetBlendedHeight`). It only affects the outer ~5% of the map; Hills maps would need the
  game's out-of-bounds heightmap.
