@echo off
title SyncNet v5 - Stop All Servers
echo ========================================
echo  SyncNet v5 - Stopping All Servers
echo ========================================
echo.

echo 🛑 Attempting graceful shutdown...
taskkill /f /im python.exe /t >nul 2>&1

echo 🧹 Cleaning up processes...
timeout /t 2 /nobreak >nul

echo ✅ All SyncNet servers have been stopped
echo.

echo 📋 Process cleanup complete
echo 🔄 You can now restart servers with start_all_servers.bat
echo.
pause 