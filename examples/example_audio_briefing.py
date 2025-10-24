"""
Example: Adding custom audio briefings to missions.

This example demonstrates how to add audio files to your mission.
The audio files are automatically copied to the mission directory when saved.
"""

from pytol import Mission

# Note: You'll need to provide your own .wav audio file for this to work
# For testing, you can create a dummy file or use any existing .wav file

def create_mission_with_audio():
    """Create a simple mission with a custom audio briefing."""
    
    # Create mission
    mission = Mission(
        scenario_name="Operation Briefing Test",
        scenario_id="briefing_test",
        description="A mission demonstrating custom audio briefings",
        map_id="hMap2",
        vehicle="FA-26B"
    )
    
    # Add a custom audio briefing
    # Replace this path with your actual audio file path
    audio_file = "path/to/your/briefing.wav"
    
    try:
        mission.add_resource(res_id=1, path=audio_file)
        print(f"✅ Added audio resource: {audio_file}")
    except FileNotFoundError:
        print(f"❌ Audio file not found: {audio_file}")
        print("Please update the audio_file path to point to a real .wav file")
        return
    
    # You can add multiple resources with different IDs
    # mission.add_resource(res_id=2, path="path/to/outro.wav")
    # mission.add_resource(res_id=3, path="path/to/warning.wav")
    
    # Add some basic mission content
    # (In a real mission, you'd add units, objectives, etc.)
    
    # Save mission - resources are automatically copied
    try:
        output_dir = "./output"
        mission_dir = mission.save_mission(output_dir)
        print(f"\n✅ Mission saved to: {mission_dir}")
        print(f"   Audio file copied to: {mission_dir}/audio/")
        print(f"   The .vts file contains: ResourceManifest {{ 1 = audio/briefing.wav }}")
    except Exception as e:
        print(f"❌ Error saving mission: {e}")

if __name__ == "__main__":
    print("Creating mission with custom audio briefing...")
    print("Note: Update the audio_file path in this script to point to a real .wav file\n")
    create_mission_with_audio()
