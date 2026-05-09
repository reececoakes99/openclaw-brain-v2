# Bot Activity Log

All bot actions timestamped and logged here.

## Log Format

```
[YYYY-MM-DD HH:MM] BOT | Action | Target | Result
```

## Rotation

- Log files rotate monthly
- Archive: `YYYY-MM.log` → `archive/YYYY-MM/`
- Last 90 days kept in active log
