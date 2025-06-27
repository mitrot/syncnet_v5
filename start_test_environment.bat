@echo off
REM This script starts the full SyncNet v5 environment for testing.
REM It launches the server cluster and then opens two client windows.

ECHO =======================================
ECHO  Starting SyncNet v5 Server Cluster
ECHO =======================================
CALL start_all_servers.bat

ECHO.
ECHO =======================================
ECHO      Starting SyncNet v5 Clients
ECHO =======================================
ECHO.
timeout /t 3 /nobreak > nul

ECHO Starting Client 1...
start "SyncNet Client 1" cmd /c "python -m client.client"

ECHO Starting Client 2...
start "SyncNet Client 2" cmd /c "python -m client.client"

ECHO.
ECHO Test environment is up. 