@echo off
ECHO Starting SyncNet v5 Cluster in separate windows...

REM Change to the script's directory to ensure relative paths work
cd /d "%~dp0"

REM Start each server in its own window. The 'start' command does not wait.
start "SyncNet Server 1" start_server1.bat
start "SyncNet Server 2" start_server2.bat
start "SyncNet Server 3" start_server3.bat

ECHO All servers have been launched. The main script will now exit. 