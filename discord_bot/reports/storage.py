"""
Storage manager for report configurations.
Handles saving and loading report settings.
"""

import json
import os
from typing import Dict, Optional, Any
from datetime import datetime
from loguru import logger

from .models import ChannelReportConfig, ReportConfig, WeeklyReportConfig


class ReportStorage:
    """Storage manager for report configurations"""
    
    def __init__(self, file_path: str = "reports_config.json"):
        """
        Initialize report storage.
        
        Args:
            file_path: Path to the configuration file
        """
        self.file_path = file_path
        self.reports_config: Dict[str, ChannelReportConfig] = {}
        logger.debug(f"Initialized ReportStorage with file: {file_path}")
    
    def load(self) -> bool:
        """
        Load report configurations from file.
        
        Returns:
            Whether loading was successful
        """
        if not os.path.exists(self.file_path):
            logger.info("No reports configuration file found, using defaults")
            return False
            
        try:
            with open(self.file_path, "r") as f:
                data = json.load(f)
                
            # Convert raw data to configuration objects
            for channel_id_str, config in data.items():
                channel_id = int(channel_id_str)
                
                # Create daily config
                daily_config = ReportConfig(
                    channel_id=channel_id,
                    enabled=config["daily"]["enabled"],
                    hour=config["daily"]["hour"],
                    minute=config["daily"]["minute"]
                )
                
                # Create weekly config
                weekly_config = WeeklyReportConfig(
                    channel_id=channel_id,
                    enabled=config["weekly"]["enabled"],
                    hour=config["weekly"]["hour"],
                    minute=config["weekly"]["minute"],
                    day=config["weekly"]["day"]
                )
                
                # Create channel config
                self.reports_config[channel_id_str] = ChannelReportConfig(
                    channel_id=channel_id,
                    daily=daily_config,
                    weekly=weekly_config
                )
                
            logger.info(f"Loaded reports configuration for {len(self.reports_config)} channels")
            return True
            
        except Exception as e:
            logger.error(f"Error loading reports configuration: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save report configurations to file.
        
        Returns:
            Whether saving was successful
        """
        try:
            # Convert configuration objects to serializable format
            data = {}
            for channel_id_str, config in self.reports_config.items():
                data[channel_id_str] = {
                    "daily": {
                        "enabled": config.daily.enabled,
                        "hour": config.daily.hour,
                        "minute": config.daily.minute
                    },
                    "weekly": {
                        "enabled": config.weekly.enabled,
                        "hour": config.weekly.hour,
                        "minute": config.weekly.minute,
                        "day": config.weekly.day
                    }
                }
                
            # Save to file
            with open(self.file_path, "w") as f:
                json.dump(data, f)
                
            logger.info(f"Saved reports configuration for {len(self.reports_config)} channels")
            return True
            
        except Exception as e:
            logger.error(f"Error saving reports configuration: {e}")
            return False
    
    def get_channel_config(self, channel_id: int) -> Optional[ChannelReportConfig]:
        """
        Get configuration for a specific channel.
        
        Args:
            channel_id: Discord channel ID
            
        Returns:
            Channel configuration or None if not found
        """
        return self.reports_config.get(str(channel_id))
    
    def set_channel_config(self, config: ChannelReportConfig) -> None:
        """
        Set configuration for a channel.
        
        Args:
            config: Channel configuration to set
        """
        self.reports_config[str(config.channel_id)] = config
        self.save()
    
    def get_all_configs(self) -> Dict[str, ChannelReportConfig]:
        """
        Get all channel configurations.
        
        Returns:
            Dictionary of channel ID strings to configurations
        """
        return self.reports_config