# Reports Module

## Overview

The `reports` module provides functionality for generating and scheduling regular portfolio reports. It allows users to configure daily and weekly portfolio summaries that are automatically sent to specified Discord channels at designated times.

## Architecture

The reports module is organized as follows:

```
reports/
├── __init__.py         # Package exports
├── models.py           # Data models for report configuration
├── storage.py          # Persistence of report settings
├── scheduler.py        # Timing logic for report generation
├── report_generator.py # Creates formatted portfolio reports
├── commands.py         # Command handlers for report configuration
└── cog.py              # Discord cog for command registration
```

## Key Components

### Data Models

The module defines several configuration models:

* `ReportConfig`: Base class for report configuration with timing details
* `WeeklyReportConfig`: Extends ReportConfig with day-of-week settings
* `ChannelReportConfig`: Contains configurations for both daily and weekly reports in a channel
* `ReportTracker`: Tracks when reports were last generated

### Report Storage

The `ReportStorage` class handles:

* Saving report configurations to JSON files
* Loading configurations on startup
* Managing report settings by channel ID

### Report Scheduler

The `ReportScheduler` determines:

* Which reports should run at the current time
* Whether sufficient time has passed since the last report
* Which channels should receive reports

### Report Generator

The `ReportGenerator` creates reports by:

* Retrieving portfolio data from the portfolio tracker
* Storing daily snapshots for historical comparison
* Formatting data into daily and weekly reports
* Calculating period-over-period changes

## Commands

The module provides several Discord commands:

* `!report setup [report_type] [time] [day]` - Configure scheduled reports
* `!report status` - Check current report configuration
* `!report daily [on/off/toggle]` - Enable/disable daily reports
* `!report weekly [on/off/toggle]` - Enable/disable weekly reports
* `!report now [report_type]` - Generate a report immediately

## Example Usage

```
# Setup daily reports at 5:00 PM
!report setup daily 17:00

# Setup weekly reports on Friday at 5:00 PM
!report setup weekly 17:00 Friday

# Check the current report configuration
!report status

# Generate a report immediately
!report now
```

## Integration Points

The reports module integrates with:

* `portfolio` module to retrieve portfolio data
* Discord's scheduling system for timed reports
* File system for persistent configuration storage

## Configuration Format

Report configurations are stored in JSON format:

```json
{
  "123456789": {
    "daily": {
      "enabled": true,
      "hour": 17,
      "minute": 0
    },
    "weekly": {
      "enabled": true,
      "hour": 17,
      "minute": 0,
      "day": 4
    }
  }
}
```
