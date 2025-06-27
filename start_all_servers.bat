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
