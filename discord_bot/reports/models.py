"""
Data models for scheduled reports.
Defines the structure of report configurations and settings.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Dict, List, Any, Optional


@dataclass
class ReportConfig:
    """Configuration for a scheduled report"""
    channel_id: int
    enabled: bool = True
    hour: int = 22  # Default to 10 PM
    minute: int = 0
    
    def format_time(self) -> str:
        """Format the report time as HH:MM"""
        return f"{self.hour:02d}:{self.minute:02d}"
    
    def should_run(self, current_time: datetime) -> bool:
        """Check if report should run at the given time"""
        return (
            self.enabled and
            current_time.hour == self.hour and
            current_time.minute == self.minute
        )


@dataclass
class WeeklyReportConfig(ReportConfig):
    """Configuration for a weekly report"""
    day: int = 4  # Default to Friday (0=Monday, 4=Friday)
    
    def should_run(self, current_time: datetime) -> bool:
        """Check if weekly report should run at the given time"""
        return (
            super().should_run(current_time) and
            current_time.weekday() == self.day
        )


@dataclass
class ChannelReportConfig:
    """All report configurations for a channel"""
    channel_id: int
    daily: ReportConfig = field(default_factory=lambda: ReportConfig(channel_id=0))
    weekly: WeeklyReportConfig = field(default_factory=lambda: WeeklyReportConfig(channel_id=0))
    
    def __post_init__(self):
        """Ensure channel IDs are set properly"""
        self.daily.channel_id = self.channel_id
        self.weekly.channel_id = self.channel_id


@dataclass
class ReportTracker:
    """Tracks when reports were last sent"""
    last_daily: Optional[datetime] = None
    last_weekly: Optional[datetime] = None