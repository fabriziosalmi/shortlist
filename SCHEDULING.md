# 🕒 Time-Based Content Scheduling in Shortlist

Shortlist supports dynamic, time-based content scheduling at the individual item level. This feature allows you to create content that automatically updates based on time of day, day of week, or any other schedule you define.

## Usage

### Item Structure

Each item in your shortlist can now include a `schedule` field:

```json
{
  "items": [
    {
      "id": "morning_bulletin",
      "content": "Good morning! Here's your morning update.",
      "schedule": "0 8 * * *"  // Every day at 8:00 AM
    }
  ]
}
```

The `schedule` field is optional. Items without a schedule are considered "always active" and will be included in every rendering.

### Schedule Format

Schedules use the standard cron format with five fields:

```
minute  hour  day-of-month  month  day-of-week
```

| Field        | Allowed Values | Special Characters |
|--------------|----------------|-------------------|
| minute       | 0-59          | *, /, - |
| hour         | 0-23          | *, /, - |
| day of month | 1-31          | *, /, - |
| month        | 1-12          | *, /, - |
| day of week  | 0-7 (0=Sun)   | *, /, - |

### Common Schedule Examples

1. **Time of Day**
   ```json
   {
     "schedule": "0 9 * * *"     // Every day at 9:00 AM
     "schedule": "0 17 * * *"    // Every day at 5:00 PM
     "schedule": "*/30 * * * *"  // Every 30 minutes
   }
   ```

2. **Days of Week**
   ```json
   {
     "schedule": "0 9 * * 1-5"   // Weekdays at 9:00 AM
     "schedule": "0 12 * * 0,6"  // Weekends at noon
     "schedule": "0 8 * * mon"   // Mondays at 8:00 AM
   }
   ```

3. **Specific Dates/Times**
   ```json
   {
     "schedule": "0 12 1 * *"    // First day of every month at noon
     "schedule": "0 0 1 1 *"     // January 1st at midnight
   }
   ```

4. **Complex Schedules**
   ```json
   {
     "schedule": "*/15 9-17 * * 1-5"  // Every 15 minutes during business hours
     "schedule": "0 8,12,17 * * *"    // Three times a day
   }
   ```

You can use [crontab.guru](https://crontab.guru) to test and validate your cron expressions.

## How It Works

1. When a renderer starts up or reloads the shortlist, it reads the items from `shortlist.json`.

2. For each item, it checks:
   - If there's no schedule: the item is included
   - If there is a schedule: it compares the current time against the schedule

3. An item is considered "active" if:
   - It has no schedule, OR
   - Its schedule matches the current time (within a small window)

4. The renderer processes only the active items.

5. Each renderer logs schedule decisions:
   - When an item is skipped due to schedule
   - When a scheduled item becomes active
   - The human-readable description of schedules

## Best Practices

1. **Time Zones**: All schedules are evaluated in UTC. Plan your schedules accordingly.

2. **Active Windows**: Items remain active for a portion of their schedule interval:
   - Hourly schedules: 6 minutes
   - Daily schedules: 2.4 hours
   - Weekly schedules: 16.8 hours

3. **Organization**:
   - Give scheduled items clear IDs
   - Comment your schedules
   - Group items with similar schedules

4. **Testing**:
   - Test schedules across date boundaries
   - Verify holiday/weekend behavior
   - Consider all time zones

## Example Use Cases

### News & Updates
```json
{
  "items": [
    {
      "id": "morning_bulletin",
      "content": "Your morning news roundup",
      "schedule": "0 8 * * *"
    },
    {
      "id": "evening_update",
      "content": "Today's highlights",
      "schedule": "0 18 * * *"
    }
  ]
}
```

### Business Hours
```json
{
  "items": [
    {
      "id": "open_hours",
      "content": "We're open! Visit us today.",
      "schedule": "0 9-17 * * 1-5"
    },
    {
      "id": "closed",
      "content": "We're currently closed. Opening hours: 9 AM - 5 PM",
      "schedule": "0 0-8,18-23 * * 1-5"
    }
  ]
}
```

### Event Countdowns
```json
{
  "items": [
    {
      "id": "event_week_before",
      "content": "Our big event is next week!",
      "schedule": "0 12 15 12 *"
    },
    {
      "id": "event_day",
      "content": "The event is today!",
      "schedule": "* * 22 12 *"
    }
  ]
}
```