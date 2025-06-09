@echo off
title SyncNet v5 - Server 1
echo ====================================
echo  SyncNet v5 - Server 1 (Port 8000)
echo ====================================
cd /d "%~dp0.."
python -m server.main --server-id server1 --log-level INFO
pause 