import re
from datetime import datetime, timezone
from typing import Optional
from croniter import croniter

# Regex to validate cron expressions
CRON_REGEX = re.compile(
    r'^(\*|[0-9]|[1-5][0-9]|\*\/[0-9]+)\s+'  # Minutes (0-59)
    r'(\*|[0-9]|1[0-9]|2[0-3]|\*\/[0-9]+)\s+'  # Hours (0-23)
    r'(\*|[1-9]|[12][0-9]|3[01]|\*\/[0-9]+)\s+'  # Day of month (1-31)
    r'(\*|[1-9]|1[0-2]|\*\/[0-9]+)\s+'  # Month (1-12)
    r'(\*|[0-6]|\*\/[0-9]+|mon|tue|wed|thu|fri|sat|sun)$'  # Day of week (0-6 or names)
    , re.IGNORECASE
)

def is_valid_cron(cron_string: str) -> bool:
    """Validate that a string is a valid cron expression.
    
    Args:
        cron_string: The cron expression to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not cron_string or not isinstance(cron_string, str):
        return False
    return bool(CRON_REGEX.match(cron_string))

def is_schedule_active(cron_string: Optional[str], reference_time: Optional[datetime] = None) -> bool:
    """Check if a cron schedule is currently active.
    
    Args:
        cron_string: The cron expression to check, or None for "always active"
        reference_time: Optional datetime to check against (defaults to now)
        
    Returns:
        bool: True if the schedule is active (or no schedule), False otherwise
    """
    # No schedule means "always active"
    if not cron_string:
        return True
        
    # Invalid cron strings are treated as "never active"
    if not is_valid_cron(cron_string):
        return False
    
    # Use provided time or current UTC time
    now = reference_time or datetime.now(timezone.utc)
    
    try:
        # Create a croniter instance with the schedule
        cron = croniter(cron_string, now)
        
        # Get the previous and next run times
        prev_run = cron.get_prev(datetime)
        next_run = cron.get_next(datetime)
        
        # Calculate the interval between runs
        interval = (next_run - prev_run).total_seconds()
        
        # Calculate how far we are from the last run
        time_since_prev = (now - prev_run).total_seconds()
        
        # The schedule is considered "active" if we're within the first 10% of
        # the interval since the last scheduled time. This prevents items from
        # being active for too long.
        #
        # For example:
        # - For hourly schedules (3600s interval), items are active for 6 minutes
        # - For daily schedules (86400s interval), items are active for 2.4 hours
        active_window = interval * 0.1
        
        return time_since_prev <= active_window
        
    except Exception:
        # Any parsing errors mean the schedule is invalid
        return False

def describe_schedule(cron_string: Optional[str]) -> str:
    """Return a human-readable description of a cron schedule.
    
    Args:
        cron_string: The cron expression to describe, or None
        
    Returns:
        str: Human-readable description
    """
    if not cron_string:
        return "Always active"
    if not is_valid_cron(cron_string):
        return "Invalid schedule"
    
    # Map of day names
    days = {
        '0': 'Sunday', '7': 'Sunday',
        '1': 'Monday', '2': 'Tuesday',
        '3': 'Wednesday', '4': 'Thursday',
        '5': 'Friday', '6': 'Saturday',
    }
    
    # Extract parts
    minute, hour, day, month, weekday = cron_string.lower().split()
    
    # Build description
    parts = []
    
    # Minutes
    if minute == '*':
        parts.append("every minute")
    elif '/' in minute:
        m = minute.split('/')
        parts.append(f"every {m[1]} minutes")
    else:
        parts.append(f"at minute {minute}")
    
    # Hours
    if hour != '*':
        if '/' in hour:
            h = hour.split('/')
            parts.append(f"every {h[1]} hours")
        else:
            parts.append(f"at {hour}:00")
    
    # Days
    if weekday != '*':
        if '-' in weekday:
            w1, w2 = weekday.split('-')
            parts.append(f"from {days[w1]} to {days[w2]}")
        elif ',' in weekday:
            w = [days[x] for x in weekday.split(',')]
            parts.append(f"on {', '.join(w[:-1])} and {w[-1]}")
        else:
            parts.append(f"on {days[weekday]}")
    
    if day != '*' and weekday == '*':
        if '/' in day:
            d = day.split('/')
            parts.append(f"every {d[1]} days")
        else:
            parts.append(f"on day {day}")
    
    if month != '*':
        if '/' in month:
            m = month.split('/')
            parts.append(f"every {m[1]} months")
        else:
            parts.append(f"in month {month}")
    
    return " ".join(parts).capitalize()