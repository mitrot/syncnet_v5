@echo off
title SyncNet v5 - 2-Server Election Test
echo ==========================================
echo  SyncNet v5 - Testing 2-Server Election
echo ==========================================
echo.
echo 🧪 This test validates the neighbor detection fix
echo 📝 Only server1 and server2 will be started
echo 🔧 server3 remains down to test failure handling
echo.

echo 🚀 Starting Server 1...
start "SyncNet Server 1" scripts\start_server1.bat
timeout /t 3 /nobreak >nul

echo 🚀 Starting Server 2...
start "SyncNet Server 2" scripts\start_server2.bat
timeout /t 3 /nobreak >nul

echo.
echo ✅ 2-server cluster is starting!
echo ⏱️  Wait 8-10 seconds for election to complete
echo.
echo 🔍 Expected behavior:
echo    - server3 detected as failed at t=6s
echo    - Elections should succeed with server1/server2
echo    - Next neighbor should correctly skip server3
echo.
echo 📊 Monitor with: python scripts\status_check.py
echo 🧹 Stop with: taskkill /f /im python.exe
echo.
pause 