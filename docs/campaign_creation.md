# Campaign Creation Guide

This guide explains how to create VTOL VR campaigns using Pytol. Campaigns allow you to group multiple missions together and are **the only way to create multiplayer missions** in VTOL VR.

## What is a Campaign?

A campaign in VTOL VR consists of:
- A `.vtc` file containing campaign metadata (name, description, equipment, multiplayer settings)
- Multiple mission folders, each containing a `.vts` mission file
- Shared map terrain data folders
- Optional Workshop metadata for Steam Workshop uploads

Campaigns can be:
- **Sequential**: Missions must be completed in order
- **All Available**: All missions accessible from the start
- **Single-player or Multiplayer**: Multiplayer is only available through campaigns

## Quick Start

```python
from pytol import Mission, Campaign

# 1. Create a campaign
campaign = Campaign(
    campaign_id="my_campaign",          # Unique ID (used in folder names)
    campaign_name="My First Campaign",   # Display name
    description="A training campaign",
    vehicle="F/A-26B",                   # Default aircraft
    multiplayer=True,                    # Enable multiplayer
    verbose=True
)

# 2. Set available equipment
campaign.set_equipment([
    "mk82x3", "gbu38x3",
    "sidewinderx2", "hellfirex4"
])

# 3. Create missions (normal mission creation)
mission1 = Mission(
    scenario_name="Training Mission 1",
    scenario_id="training_1",
    description="Learn basic flight controls",
    map_id="hMap2",
    vehicle="F/A-26B",
    vtol_directory="path/to/VTOL VR"  # Or use VTOL_VR_DIR env variable
)

# ... add units, objectives, etc to mission1 ...

# 4. Add missions to campaign
# Note: If campaign is multiplayer, missions are automatically configured for MP
campaign.add_mission(mission1)

# Create and add more missions...

# 5. Save the campaign
campaign.save("output/my_campaign", copy_map_folders=True)

# 6. Optionally save Workshop metadata
campaign.save_workshop_info(
    "output/my_campaign",
    published_file_id="0",  # Use "0" for new uploads
    tags=["Multiplayer Campaigns"]
)
```

## Campaign Class

### Constructor

```python
Campaign(
    campaign_id: str = "",
    campaign_name: str = "",
    description: str = "",
    vehicle: str = "F/A-26B",
    multiplayer: bool = False,
    verbose: bool = True
)
```

**Parameters:**
- `campaign_id`: Unique identifier used in folder/file names (e.g., "operation_desert_storm")
- `campaign_name`: Display name shown in-game (e.g., "Operation Desert Storm")
- `description`: Campaign briefing text (supports `\\n` for line breaks)
- `vehicle`: Default aircraft ("F/A-26B", "AV-42C", "F-45A", etc.)
- `multiplayer`: Enable multiplayer support (required for MP missions)
- `verbose`: Print progress messages during campaign creation

### Properties

```python
campaign.campaign_id = "custom_id"
campaign.campaign_name = "Custom Campaign"
campaign.description = "A custom campaign"
campaign.vehicle = "AV-42C"
campaign.multiplayer = True
campaign.availability = "All_Available"  # or "Sequential"
campaign.ws_upload_version = 2  # Workshop version
```

### Methods

#### add_mission(mission)
Add a mission to the campaign. The mission will automatically be configured with the campaign's settings.

```python
mission = Mission(...)
campaign.add_mission(mission)
```

The method automatically:
- Sets `mission.campaign_id` to match the campaign
- Sets `mission.campaign_order_idx` based on order added
- **If campaign is multiplayer**: Sets `mission.multiplayer = True` and configures default MP settings
  - Sets `mission.mp_player_count = 4` (if still at default)
  - Sets `mission.auto_player_count = True`

**Important:** You don't need to manually set `mission.multiplayer = True` when adding to a multiplayer campaign - it's done automatically!

#### set_equipment(equipment_list)
Set the available equipment for all missions in the campaign.

```python
campaign.set_equipment([
    "gau-8", "m230",                    # Guns
    "mk82x3", "gbu38x3", "gbu39x4u",   # Bombs
    "sidewinderx2", "hellfirex4",       # Missiles
    "maverickx3"
])
```

#### add_equipment(equipment_id)
Add a single equipment item to the available list.

```python
campaign.add_equipment("mk82x3")
campaign.add_equipment("sidewinderx2")
```

#### save(output_path, copy_map_folders=True)
Save the campaign to a folder structure.

```python
campaign.save("output/my_campaign", copy_map_folders=False)
```

**Creates:**
```
output/my_campaign/
├── my_campaign.vtc              # Campaign file
├── mission_1/
│   └── mission_1.vts
├── mission_2/
│   └── mission_2.vts
└── hMap2/                       # Map data (if copy_map_folders=True)
    ├── hMap2.vtm
    └── ...
```

**Parameters:**
- `output_path`: Path to campaign folder (will be created)
- `copy_map_folders`: Whether to copy map terrain data folders

#### save_workshop_info(output_path, published_file_id="0", tags=None)
Generate Steam Workshop metadata file.

```python
campaign.save_workshop_info(
    "output/my_campaign",
    published_file_id="0",  # Use actual ID after first upload
    tags=["Multiplayer Campaigns", "Training"]
)
```

**Parameters:**
- `output_path`: Campaign folder path
- `published_file_id`: Steam Workshop ID ("0" for new uploads)
- `tags`: List of workshop tags (defaults to ["Multiplayer Campaigns"] if multiplayer)

## Multiplayer Configuration

### Campaign-Level Multiplayer

Enable multiplayer at the campaign level:

```python
campaign = Campaign(
    campaign_id="mp_campaign",
    campaign_name="Multiplayer Campaign",
    multiplayer=True  # Required for MP missions
)
```

When you add missions to a multiplayer campaign using `campaign.add_mission()`, the missions are **automatically configured** with:
- `mission.multiplayer = True`
- `mission.mp_player_count = 4` (default)
- `mission.auto_player_count = True`

You don't need to manually set these unless you want to override the defaults.

### Advanced: Customizing Multiplayer Properties

If you need to customize multiplayer settings beyond the defaults, you can set them **before** adding the mission to the campaign:

```python
mission = Mission(...)

# Customize multiplayer settings (optional)
mission.mp_player_count = 8           # More players
mission.auto_player_count = False     # Fixed player count

# Team settings
mission.override_allied_player_count = 4   # Fixed team sizes
mission.override_enemy_player_count = 4

# Scoring (for competitive modes)
mission.score_per_death_a = -10
mission.score_per_death_b = -10
mission.score_per_kill_a = 100
mission.score_per_kill_b = 100

# Budget mode
mission.mp_budget_mode = "Shared"     # or "Life"
mission.base_budget = 100000
mission.base_budget_b = 100000        # Team B budget

# Separate RTB/refuel points per team (optional)
mission.rtb_wpt_id = "rtb_team_a"
mission.rtb_wpt_id_b = "rtb_team_b"
mission.refuel_wpt_id = "refuel_a"
mission.refuel_wpt_id_b = "refuel_b"

# Separate briefings for PvP (optional)
mission.separate_briefings = True

# Now add to campaign (multiplayer=True will still be set automatically)
campaign.add_mission(mission)
```

**Note:** For most cooperative multiplayer campaigns, the default settings are sufficient and you don't need any of these customizations.

## Equipment System

### Equipment IDs

Common equipment IDs for campaigns:

**Guns:**
- `gau-8` - GAU-8 Avenger (30mm)
- `m230` - M230 Chain Gun

**Missiles (Air-to-Air):**
- `sidewinderx1`, `sidewinderx2`, `sidewinderx3` - AIM-9 Sidewinder
- `iris-t-x1`, `iris-t-x2`, `iris-t-x3` - IRIS-T

**Missiles (Air-to-Ground):**
- `hellfirex4` - AGM-114 Hellfire
- `maverickx1`, `maverickx3` - AGM-65 Maverick
- `sidearmx1`, `sidearmx2`, `sidearmx3` - AGM-122 Sidearm
- `marmx1` - AGM-88 HARM
- `cagm-6` - Cruise missiles

**Bombs:**
- `mk82x1`, `mk82x2`, `mk82x3` - Mk 82 500lb
- `mk82HDx1`, `mk82HDx2`, `mk82HDx3` - Mk 82 HD
- `gbu38x1`, `gbu38x2`, `gbu38x3` - GBU-38 JDAM
- `gbu39x3`, `gbu39x4u` - GBU-39 SDB
- `av42_gbu12x1`, `av42_gbu12x2`, `av42_gbu12x3` - GBU-12 (AV-42C)

**Rockets:**
- `h70-x7`, `h70-4x4`, `h70-x19` - Hydra 70

### Equipment Presets

You can use equipment presets from the equipment system:

```python
from pytol.resources.equipment import EquipmentBuilder

# Get all available equipment for a vehicle
all_equip = EquipmentBuilder.get_available_equipment("F/A-26B")
campaign.set_equipment([e.id for e in all_equip])

# Or use specific loadout presets
from pytol.resources.equipment import LoadoutPresets

strike_loadout = LoadoutPresets.get_strike_loadout("F/A-26B")
campaign.set_equipment([e.id for e in strike_loadout.equipment])
```

## Campaign Folder Structure

After saving, your campaign will have this structure:

```
my_campaign/
├── my_campaign.vtc              # Campaign metadata
├── WorkshopItemInfo.xml         # Steam Workshop info (optional)
├── mission_1/
│   └── mission_1.vts            # Mission file (no map folder here!)
├── mission_2/
│   └── mission_2.vts            # Mission file (no map folder here!)
├── mission_3/
│   └── mission_3.vts            # Mission file (no map folder here!)
├── hMap2/                       # Map data at campaign root (shared by all missions)
│   ├── hMap2.vtm
│   ├── heightmap.png
│   └── ...
└── costaOeste/                  # Another map if missions use different maps
    └── ...
```

**Important:** Unlike single missions where the map folder goes inside the mission folder, campaigns have **map folders at the root level**, shared by all missions. This avoids duplicating large map data files.

## Complete Example

See `examples/example_campaign_creation.py` for a complete working example of a 3-mission campaign with multiplayer support.

## Deployment

### Local Testing

1. Copy your campaign folder to:
   ```
   <VTOL VR Install>/CustomScenarios/Campaigns/
   ```

2. Launch VTOL VR

3. Select "Campaigns" from the main menu

4. Find your campaign in the list

### Steam Workshop Upload

1. Generate Workshop metadata:
   ```python
   campaign.save_workshop_info(
       "output/my_campaign",
       published_file_id="0"
   )
   ```

2. Use VTOL VR's built-in Workshop upload tool:
   - In-game: Settings → Workshop → Upload Campaign
   - Select your campaign folder
   - Fill in description and tags
   - Publish

3. After first upload, update `published_file_id` for future updates

## Tips & Best Practices

### Mission Order
- Set missions in logical progression (training → easy → hard)
- Use `campaign.availability = "Sequential"` for story-driven campaigns
- Use `campaign.availability = "All_Available"` for mission packs

### Multiplayer Balance
- Test with different player counts
- Use `auto_player_count = True` for flexible lobbies
- Balance objectives for cooperative play
- Consider separate objectives for PvP missions

### Equipment
- Don't overwhelm players with too many options
- Match equipment to mission type (strike, CAP, CAS)
- Use `allowed_equips` to restrict choices per mission

### Performance
- Keep missions under 200 units for multiplayer
- Use terrain-aware placement to avoid spawn issues
- Test on the target map before deploying

### Verbose Mode
- Use `verbose=True` during development for detailed logs
- Use `verbose=False` for production/batch generation

## Troubleshooting

### Campaign doesn't appear in-game
- Check that the `.vtc` file name matches the folder name
- Verify `campaign_id` matches the folder/file naming
- Ensure the campaign folder is in `CustomScenarios/Campaigns/`

### Missions won't load
- Verify each mission has a unique `scenario_id`
- Check that `map_id` matches an installed map
- Ensure map folders are copied or available

### Multiplayer issues
- Campaign must have `multiplayer = True` (missions are configured automatically)
- Check that `mp_player_count` is reasonable (2-16)
- Verify team spawn points exist for both sides
- Test in single-player first to verify mission logic

### Equipment not available
- Check equipment IDs match VTOL VR's format
- Verify equipment is valid for the selected vehicle
- Equipment list should end with semicolon (handled automatically)

## See Also

- [Mission Creation Guide](mission_creation.md) - Creating individual missions
- [Equipment System](../README.md#equipment-system) - Managing loadouts
- [Examples](../examples/) - Sample scripts and campaigns
