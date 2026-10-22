"""
Campaign (.vtc) file builder for VTOL VR.

This module provides the Campaign class for creating VTOL VR campaign files,
which group multiple missions together and enable multiplayer scenarios.
"""

from typing import List, Optional
import os
from pathlib import Path
from ..misc.logger import create_logger


class Campaign:
    """
    Represents a VTOL VR campaign (.vtc file).
    
    Campaigns group multiple missions together and are the only way to create
    multiplayer missions in VTOL VR. Each campaign can contain multiple scenarios
    (.vts files) that are played in sequence.
    
    Attributes:
        campaign_id (str): Unique identifier for the campaign (used in folder names)
        campaign_name (str): Display name shown in-game
        description (str): Campaign description/briefing
        vehicle (str): Default aircraft for the campaign (e.g., "F/A-26B", "AV-42C")
        starting_equips (List[str]): List of available equipment IDs
        multiplayer (bool): Whether this is a multiplayer campaign
        availability (str): Mission availability mode ("All_Available", "Sequential", etc.)
        ws_upload_version (int): Workshop upload version (for Steam Workshop)
        missions (List): List of Mission objects to include in campaign
        verbose (bool): Whether to print progress messages
    """
    
    def __init__(
        self,
        campaign_id: str = "",
        campaign_name: str = "",
        description: str = "",
        vehicle: str = "F/A-26B",
        multiplayer: bool = False,
        verbose: bool = True
    ):
        """
        Initialize a new Campaign.
        
        Args:
            campaign_id: Unique identifier (used in folder/file names)
            campaign_name: Display name in-game
            description: Campaign briefing/description
            vehicle: Default aircraft ("F/A-26B", "AV-42C", "F-45A", etc.)
            multiplayer: Enable multiplayer support
            verbose: Print progress messages
        """
        self.campaign_id = campaign_id
        self.campaign_name = campaign_name
        self.description = description
        self.vehicle = vehicle
        self.multiplayer = multiplayer
        self.verbose = verbose
        self.logger = create_logger(verbose=verbose, name="Campaign")
        
        # Equipment list - default to common equipment
        self.starting_equips: List[str] = []
        
        # Campaign settings
        self.availability = "All_Available"  # or "Sequential"
        self.ws_upload_version = 2
        
        # Missions in this campaign
        self.missions: List = []
    
    def _log(self, message: str):
        """Route messages through centralized logger with simple level detection."""
        msg = str(message).lstrip()
        lower = msg.lower()
        if lower.startswith("warning") or msg.startswith("⚠"):
            self.logger.warning(msg)
        elif lower.startswith("error") or lower.startswith("fatal"):
            self.logger.error(msg)
        else:
            self.logger.info(msg)
    
    def add_mission(self, mission):
        """
        Add a mission to this campaign.
        
        Args:
            mission: Mission object to add (from vts_builder.Mission)
        """
        # Set the mission's campaign properties
        mission.campaign_id = self.campaign_id
        mission.campaign_order_idx = len(self.missions)
        
        # If this is a multiplayer campaign, enable multiplayer on missions
        if self.multiplayer:
            mission.multiplayer = True
            # Set reasonable defaults for multiplayer if not already set
            if mission.mp_player_count == 2:  # Default value, user hasn't changed it
                mission.mp_player_count = 4
            if mission.auto_player_count is not True:
                mission.auto_player_count = True
        
        self.missions.append(mission)
        self._log(f"Added mission '{mission.scenario_name}' as mission #{len(self.missions)}")
    
    def set_equipment(self, equipment_list: List[str]):
        """
        Set the available equipment for this campaign.
        
        Args:
            equipment_list: List of equipment IDs (e.g., ["mk82x3", "sidewinderx2"])
        """
        self.starting_equips = equipment_list
        self._log(f"Set {len(equipment_list)} equipment options for campaign")
    
    def add_equipment(self, equipment_id: str):
        """
        Add a single equipment item to the available list.
        
        Args:
            equipment_id: Equipment ID (e.g., "mk82x3", "sidewinderx2")
        """
        if equipment_id not in self.starting_equips:
            self.starting_equips.append(equipment_id)
            self._log(f"Added equipment: {equipment_id}")
    
    def to_vtc_string(self) -> str:
        """
        Generate the .vtc file content as a string.
        
        Returns:
            String containing the complete .vtc file content
        """
        # Convert equipment list to semicolon-separated string; an empty list would leave the player unarmed
        equips = self.starting_equips
        if not equips:
            from pytol.resources.equipment import get_equipment_for_vehicle
            equips = get_equipment_for_vehicle(self.vehicle)
        equips_str = ";".join(equips)
        if equips_str:
            equips_str += ";"  # VTOL VR format ends with semicolon
        
        lines = [
            "CAMPAIGN",
            "{",
            f"\tcampaignID = {self.campaign_id}",
            f"\tcampaignName = {self.campaign_name}",
            f"\tdescription = {self.description}",
            f"\tvehicle = {self.vehicle}",
            f"\tstartingEquips = {equips_str}",
            f"\tmultiplayer = {str(self.multiplayer)}",
            f"\tavailability = {self.availability}",
            f"\twsUploadVersion = {self.ws_upload_version}",
            "}",
            ""
        ]
        
        return "\n".join(lines)
    
    def save(self, output_path: str, copy_map_folders: bool = True):
        """
        Save the campaign to a folder structure.
        
        Creates the proper campaign folder structure:
        - campaign_folder/
          - campaign_id.vtc (campaign file)
          - mission_1/
            - mission_1.vts
          - mission_2/
            - mission_2.vts
          - map_folder/ (shared map data)
        
        Args:
            output_path: Path to the campaign folder (will be created)
            copy_map_folders: Whether to copy map folders from missions
        """
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        
        self._log(f"\nCreating campaign: {self.campaign_name}")
        self._log(f"Campaign folder: {output_path}")
        
        # Save the .vtc file
        vtc_path = output_path / f"{self.campaign_id}.vtc"
        # LF only: the game splits lines on '\n' and keeps a CR in every value (campaignID would not match)
        with open(vtc_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(self.to_vtc_string())
        self._log(f"✓ Saved campaign file: {vtc_path.name}")
        
        # Each mission in its own folder (with its resources); one shared map copy at the campaign root.
        maps = {}
        for i, mission in enumerate(self.missions):
            mission.save_mission(str(output_path), copy_map=False)
            maps[mission.map_id] = mission.map_path
            self._log(f"✓ Saved mission {i + 1}/{len(self.missions)}: {mission.scenario_id}")
        if copy_map_folders:
            import shutil
            for map_id, map_path in maps.items():
                if os.path.isdir(map_path):
                    shutil.copytree(map_path, output_path / map_id, dirs_exist_ok=True)
                    self._log(f"✓ Copied map folder: {map_id}")
                else:
                    self._log(f"⚠ Warning: map folder not found: {map_path}")

        self._log(f"\n✓ Campaign '{self.campaign_name}' created successfully!")
        self._log(f"  Location: {output_path}")
        self._log(f"  Missions: {len(self.missions)}")
        self._log(f"  Multiplayer: {self.multiplayer}")
    
    def save_workshop_info(
        self,
        output_path: str,
        published_file_id: str = "0",
        tags: Optional[List[str]] = None
    ):
        """
        Save Steam Workshop metadata file (WorkshopItemInfo.xml).
        
        Args:
            output_path: Path to the campaign folder
            published_file_id: Steam Workshop file ID (use "0" for new uploads)
            tags: List of workshop tags (default: ["Multiplayer Campaigns"] if multiplayer)
        """
        if tags is None:
            if self.multiplayer:
                tags = ["Multiplayer Campaigns"]
            else:
                tags = ["Campaigns"]
        
        output_path = Path(output_path)
        workshop_file = output_path / "WorkshopItemInfo.xml"
        
        # Escape XML special characters in description
        description_escaped = (self.description
                              .replace("&", "&amp;")
                              .replace("<", "&lt;")
                              .replace(">", "&gt;")
                              .replace('"', "&quot;")
                              .replace("'", "&apos;"))
        
        xml_content = f'''<?xml version="1.0" encoding="utf-16"?>
<WorkshopItemInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <PublishedFileId>{published_file_id}</PublishedFileId>
  <Name>{self.campaign_name}</Name>
  <Description>{description_escaped}</Description>
  <Tags>
'''
        
        for tag in tags:
            xml_content += f'    <string>{tag}</string>\n'
        
        xml_content += '''  </Tags>
</WorkshopItemInfo>
'''
        
        with open(workshop_file, 'w', encoding='utf-16') as f:
            f.write(xml_content)
        
        self._log("✓ Saved Workshop metadata: WorkshopItemInfo.xml")
    
    def __repr__(self) -> str:
        return (f"Campaign(id='{self.campaign_id}', name='{self.campaign_name}', "
                f"missions={len(self.missions)}, multiplayer={self.multiplayer})")
