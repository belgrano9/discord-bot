"""
Scheduler for reports.
Determines when reports should be generated.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from .models import ChannelReportConfig, ReportTracker


class ReportScheduler:
    """Scheduler for report generation"""
    
    def __init__(self):
        """Initialize the report scheduler"""
        self.tracker = ReportTracker()
        logger.debug("Initialized ReportScheduler")
    
    def check_daily_reports(
        self, 
        configs: Dict[str, ChannelReportConfig]
    ) -> List[int]:
        """
        Check which daily reports should run now.
        
        Args:
            configs: Dictionary of channel report configurations
            
        Returns:
            List of channel IDs that should run daily reports
        """
        now = datetime.now()
        channels_to_run = []
        
        for channel_id_str, config in configs.items():
            daily_config = config.daily
            
            if not daily_config.enabled:
                continue
                
            # Check if it's time to run
            if daily_config.should_run(now):
                # Only run if we haven't run in the last 12 hours
                should_run = (
                    self.tracker.last_daily is None or
                    (now - self.tracker.last_daily).total_seconds() >= 12 * 3600
                )
                
                if should_run:
                    channels_to_run.append(config.channel_id)
        
        if channels_to_run:
            self.tracker.last_daily = now
            
        return channels_to_run
    
    def check_weekly_reports(
        self, 
        configs: Dict[str, ChannelReportConfig]
    ) -> List[int]:
        """
        Check which weekly reports should run now.
        
        Args:
            configs: Dictionary of channel report configurations
            
        Returns:
            List of channel IDs that should run weekly reports
        """
        now = datetime.now()
        channels_to_run = []
        
        for channel_id_str, config in configs.items():
            weekly_config = config.weekly
            
            if not weekly_config.enabled:
                continue
                
            # Check if it's time to run
            if weekly_config.should_run(now):
                # Only run if we haven't run in the last 24 hours
                should_run = (
                    self.tracker.last_weekly is None or
                    (now - self.tracker.last_weekly).total_seconds() >= 24 * 3600
                )
                
                if should_run:
                    channels_to_run.append(config.channel_id)
        
        if channels_to_run:
            self.tracker.last_weekly = now
            
        return channels_to_run
    
    def update_last_report(self, report_type: str) -> None:
        """
        Update the last report time.
        
        Args:
            report_type: Type of report ("daily" or "weekly")
        """
        now = datetime.now()
        
        if report_type.lower() == "daily":
            self.tracker.last_daily = now
        elif report_type.lower() == "weekly":
            self.tracker.last_weekly = now