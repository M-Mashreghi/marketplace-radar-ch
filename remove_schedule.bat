@echo off
rem Stop the running bot, then remove the scheduled task.
schtasks /End /TN "Anibis Alarm" >nul 2>&1
schtasks /Delete /TN "Anibis Alarm" /F
pause
