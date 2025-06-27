@echo off
title SyncNet v5 - Server 3
echo ====================================
echo  SyncNet v5 - Server 3 (Port 8002)
echo ====================================
cd /d "%~dp0.."
set "PYTHONPATH=%CD%"
python -m server.main --server-id server3 --log-level INFO
pause 