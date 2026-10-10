# Running the Anibis bot automatically (Windows)

The bot (`bot.py`, started by `main.py`) runs all the time in the background,
answers you in Telegram and searches Anibis every 2 hours.

## Start
Double-click **install_schedule.bat**. It creates a Task Scheduler job called
**Anibis Alarm** that:
- starts the bot when you log in to Windows, and
- checks every 15 minutes that it's still running, restarting it if it
  crashed (if it's already running, nothing happens).

The bot starts about a minute after you install. Running the installer again
just replaces the job.

## Check it's working
- Send the bot a message in Telegram; it should answer.
- Look at `anibis_alert.log` in this folder for what it's been doing and any errors.
- `schtasks /Query /TN "Anibis Alarm" /V /FO LIST` shows the task's status
  ("Running" while the bot is up).

## Pause
`schtasks /End /TN "Anibis Alarm"` stops the bot now, but the watchdog starts
it again within 15 minutes. To keep it off, also run
`schtasks /Change /TN "Anibis Alarm" /Disable` (`/Enable` to resume),
or right-click the task in Task Scheduler and choose End, then Disable.

## Stop for good
Double-click **remove_schedule.bat**. It stops the running bot and deletes the task.
If a copy you started by hand is still running, end `pythonw.exe` in Task Manager.

## Notes
- No window appears; everything goes to `anibis_alert.log`.
- The PC has to be on and you logged in for the bot to run.
