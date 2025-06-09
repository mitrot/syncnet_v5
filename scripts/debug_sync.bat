@echo off
title SyncNet v5 - Debug Sync Test
echo ========================================
echo  SyncNet v5 - Running Sync Debug Test
echo ========================================
echo.

echo 🔍 Running sync behavior debug test...
echo 📝 This will start server1 and server2 only
echo ⏱️  Test runs for 25 seconds to verify timing fixes
echo.

cd /d "%~dp0.."
python debug_sync.py

echo.
echo 🏁 Debug test completed
echo 📋 Check output above for sync behavior verification
echo.
pause 