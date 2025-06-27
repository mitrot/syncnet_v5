@echo off
title SyncNet v5 - Server 2
echo ====================================
echo  SyncNet v5 - Server 2 (Port 8001)
echo ====================================
cd /d "%~dp0.."
set "PYTHONPATH=%CD%"
python -m server.main --server-id server2 --log-level INFO
pause 