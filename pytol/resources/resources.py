import json
from importlib import resources
from PIL import Image
from pathlib import Path
from ..misc.logger import create_logger
import os

_logger = create_logger(verbose=False, name="Resources")

PACKAGE_NAME_WITH_RESOURCES = 'pytol.resources'
CITY_LAYOUT_DB = 'city_layouts_database.json'
GUID_TO_NAME_DB = 'guid_to_name.json'
PREFAB_DB = 'individual_prefabs_database.json'
VEHICLE_EQUIP_DB = 'vehicle_equip_database.json'
NOISE_IMAGE = 'noise.png'
STATIC_PREFABS_DB = 'static_prefabs_database.json'
_UNIT_PREFAB_DB_PATH = os.path.join(os.path.dirname(__file__), "unit_prefab_database.json")

def load_json_data(file_name: str = 'data.json') -> dict:
    """Loads a JSON file from the package data."""
    try:
        # Use read_text for text files (JSON)
        data = resources.read_text(PACKAGE_NAME_WITH_RESOURCES, file_name)
        return json.loads(data)
    except Exception as e:
        # Handle exceptions gracefully
        _logger.warning(f"Could not load JSON data from {file_name}: {e}")
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
        _logger.warning(f"Image asset {file_name} not found.")
        return None


def load_unit_prefab_database():
    """Load the unit prefab database (Allied/Enemy) from JSON."""
    with open(_UNIT_PREFAB_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

_unit_prefab_db = load_unit_prefab_database()

def get_all_unit_prefabs():
    """Return a sorted list of all unit prefab names (Allied + Enemy, unique)."""
    return sorted(set(_unit_prefab_db["Allied"]) | set(_unit_prefab_db["Enemy"]))

def get_allied_unit_prefabs():
    """Return a sorted list of Allied unit prefab names."""
    return sorted(_unit_prefab_db["Allied"])

def get_enemy_unit_prefabs():
    """Return a sorted list of Enemy unit prefab names."""
    return sorted(_unit_prefab_db["Enemy"])

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

def get_static_prefabs_database():
    """Returns the static prefabs database (built from Unity project)."""
    return load_json_data(STATIC_PREFABS_DB)

def list_static_prefabs(tags: list[str] | None = None) -> list[dict]:
    """List all static prefabs with optional tag filtering.

    Args:
        tags: Optional list of tags to filter by. When provided, only prefabs
              containing all specified tags will be returned.

    Returns:
        A list of prefab dicts as stored in the database (name, relative_path, tags).
    """
    db = get_static_prefabs_database() or {}
    prefabs: list[dict] = db.get("prefabs", []) or []
    if not tags:
        return prefabs
    wanted = {t.lower() for t in tags}
    out: list[dict] = []
    for p in prefabs:
        ptags = {t.lower() for t in (p.get("tags") or [])}
        if wanted.issubset(ptags):
            out.append(p)
    return out

def list_static_prefab_names(tags: list[str] | None = None) -> list[str]:
    """List prefab names, optionally filtered by tags.

    Args:
        tags: Optional list of tags. If provided, only names of prefabs matching
              all tags are returned.

    Returns:
        Sorted list of prefab names.
    """
    names = [p.get("name") for p in list_static_prefabs(tags=tags)]
    return sorted(n for n in names if isinstance(n, str))

def get_static_prefab(name: str) -> dict | None:
    """Get a static prefab entry by exact name (case-insensitive).

    Returns the prefab dict if found, else None.
    """
    if not name:
        return None
    key = name.lower()
    for p in list_static_prefabs():
        if (p.get("name") or "").lower() == key:
            return p
    return None

def get_noise_image():
    """Returns the noise image asset."""
    return load_image_asset(NOISE_IMAGE)