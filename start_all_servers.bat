@echo off
title SyncNet v5 - Cluster Manager
echo ========================================
echo  SyncNet v5 - Starting Distributed Cluster
echo ========================================
echo.

echo 🚀 Starting Server 1...
start "SyncNet Server 1" scripts\start_server1.bat
timeout /t 3 /nobreak >nul

echo 🚀 Starting Server 2...
start "SyncNet Server 2" scripts\start_server2.bat  
timeout /t 3 /nobreak >nul

echo 🚀 Starting Server 3...
start "SyncNet Server 3" scripts\start_server3.bat
timeout /t 3 /nobreak >nul

echo.
echo ✅ All servers are starting up!
echo ⏱️  Please wait 8-10 seconds for cluster formation...
echo 🔧 Recent fixes: Improved election timing and neighbor detection
echo.
echo 📊 Monitor cluster status with:
echo    python scripts\status_check.py
echo.
echo 💬 Connect clients with:
echo    python client\syncnet_client.py
echo.
echo 🧪 Test 2-server elections (with server3 down):
echo    Start only server1 and server2 to test fixed neighbor detection
echo.
pause 