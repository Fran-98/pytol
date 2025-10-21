import json
from importlib import resources
from PIL import Image
from pathlib import Path

PACKAGE_NAME_WITH_RESOURCES = 'pytol.resources'
CITY_LAYOUT_DB = 'city_layouts_database.json'
GUID_TO_NAME_DB = 'guid_to_name.json'
PREFAB_DB = 'individual_prefabs_database.json'
VEHICLE_EQUIP_DB = 'vehicle_equip_database.json'
NOISE_IMAGE = 'noise.png'

def load_json_data(file_name: str = 'data.json') -> dict:
    """Loads a JSON file from the package data."""
    try:
        # Use read_text for text files (JSON)
        data = resources.read_text(PACKAGE_NAME_WITH_RESOURCES, file_name)
        return json.loads(data)
    except Exception as e:
        # Handle exceptions gracefully
        print(f"Warning: Could not load JSON data from {file_name}: {e}")
        return {}

def load_image_asset(file_name: str = 'noise.png'):
    """Loads a PNG image asset using Pillow."""
    try:
        # Use files() and .open() for binary files (PNG)
        resource_path = resources.files(PACKAGE_NAME_WITH_RESOURCES) / file_name
        with resource_path.open("rb") as f:
            img = Image.open(f)
            img.load()  # Ensure the image is fully loaded
            return img
    except FileNotFoundError:
        print(f"Warning: Image asset {file_name} not found.")
        return None

def get_city_layout_database():
    """Returns the city layout database as a dictionary."""
    return load_json_data(CITY_LAYOUT_DB)

def get_guid_to_name_database():
    """Returns the GUID to name database as a dictionary."""
    return load_json_data(GUID_TO_NAME_DB)

def get_prefab_database():
    """Returns the individual prefab database as a dictionary."""
    return load_json_data(PREFAB_DB)

def get_vehicle_equipment_database():
    """Returns the vehicle equipment prefab database as a dictionary."""
    return load_json_data(VEHICLE_EQUIP_DB)

def get_noise_image():
    """Returns the noise image asset."""
    return load_image_asset(NOISE_IMAGE)