from pytol import Mission, WeatherPreset

# Configure a minimal mission with a custom weather preset
mission = Mission(
    scenario_name="Weather Demo",
    scenario_id="weather_demo",
    description="Demonstrate custom weather presets",
    vehicle="AV-42C",
    map_id="hMap2",
    vtol_directory=r"C:\\Program Files (x86)\\Steam\\steamapps\\common\\VTOL VR",
)

# Add a dramatic red fog preset (ids 0-7 are built-in; use 8+ for customs)
red_fog = WeatherPreset(
    id=8,
    preset_name="Red Fog",
    cloud_plane_altitude=1500,
    cloudiness=0.0,
    macro_cloudiness=0.0,
    cirrus=0.5,
    stratocumulus=0.0,
    precipitation=0.0,
    lightning_chance=0.0,
    fog_density=0.65,
    fog_color=(1, 0, 0, 1),
    fog_height=1.0,
    fog_falloff=1000.0,
    cloud_density=0.0,
)
mission.add_weather_preset(red_fog)
mission.set_default_weather(8)

# Save mission to ./out/weather_demo/
output_dir = mission.save_mission("./out")
print(f"Mission saved to: {output_dir}")
