"""
Storage functionality for price alerts.
Handles persistence of alerts to and from JSON files.
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from .alert_model import PriceAlert


class AlertStorage:
    """Storage management for price alerts"""
    
    def __init__(self, file_path: str = "stock_alerts.json"):
        """
        Initialize the alert storage.
        
        Args:
            file_path: Path to the alerts JSON file
        """
        self.file_path = file_path
        self.alerts_by_channel: Dict[int, List[PriceAlert]] = {}
        logger.debug(f"Initialized AlertStorage with file: {file_path}")
    
    def load(self) -> bool:
        """
        Load alerts from file.
        
        Returns:
            Whether loading was successful
        """
        if not os.path.exists(self.file_path):
            logger.info(f"No alerts file found at {self.file_path}")
            return False
            
        try:
            with open(self.file_path, "r") as f:
                data = json.load(f)
                
            # Convert raw data to PriceAlert objects
            self.alerts_by_channel = {}
            for channel_id_str, alerts_data in data.items():
                channel_id = int(channel_id_str)
                self.alerts_by_channel[channel_id] = [
                    PriceAlert.from_dict(alert_data) for alert_data in alerts_data
                ]
                
            alert_count = sum(len(alerts) for alerts in self.alerts_by_channel.values())
            logger.info(f"Loaded {alert_count} price alerts from {self.file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading stock alerts: {str(e)}")
            return False
    
    def save(self) -> bool:
        """
        Save alerts to file.
        
        Returns:
            Whether saving was successful
        """
        try:
            # Convert alerts to serializable format
            data = {}
            for channel_id, alerts in self.alerts_by_channel.items():
                data[str(channel_id)] = [alert.to_dict() for alert in alerts]
                
            with open(self.file_path, "w") as f:
                json.dump(data, f)
                
            alert_count = sum(len(alerts) for alerts in self.alerts_by_channel.values())
            logger.info(f"Saved {alert_count} price alerts to {self.file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving stock alerts: {str(e)}")
            return False
    
    def get_channel_alerts(self, channel_id: int) -> List[PriceAlert]:
        """Get all alerts for a specific channel"""
        return self.alerts_by_channel.get(channel_id, [])
    
    def get_all_alerts(self) -> Dict[int, List[PriceAlert]]:
        """Get all alerts for all channels"""
        return self.alerts_by_channel
    
    def add_alert(self, alert: PriceAlert) -> None:
        """Add a new alert"""
        if alert.channel_id not in self.alerts_by_channel:
            self.alerts_by_channel[alert.channel_id] = []
            
        self.alerts_by_channel[alert.channel_id].append(alert)
        self.save()
        
    def remove_alert(self, channel_id: int, index: int) -> Optional[PriceAlert]:
        """Remove an alert by index"""
        if channel_id not in self.alerts_by_channel:
            return None
            
        if 0 <= index < len(self.alerts_by_channel[channel_id]):
            alert = self.alerts_by_channel[channel_id].pop(index)
            if not self.alerts_by_channel[channel_id]:
                del self.alerts_by_channel[channel_id]
            self.save()
            return alert
            
        return None
    
    def remove_alerts(self, channel_id: int, indices: List[int]) -> int:
        """Remove multiple alerts by indices"""
        if channel_id not in self.alerts_by_channel:
            return 0
            
        # Sort indices in descending order to avoid index shifting
        indices = sorted(indices, reverse=True)
        removed = 0
        
        for index in indices:
            if 0 <= index < len(self.alerts_by_channel[channel_id]):
                self.alerts_by_channel[channel_id].pop(index)
                removed += 1
                
        if channel_id in self.alerts_by_channel and not self.alerts_by_channel[channel_id]:
            del self.alerts_by_channel[channel_id]
            
        if removed > 0:
            self.save()
            
        return removed