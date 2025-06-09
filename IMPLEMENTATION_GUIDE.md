# SyncNet v5 Complete Implementation Guide
==========================================
**Target**: ~1,200 Lines of Code  
**Status**: Production-ready specifications with server management  
**Date**: 2024

## 🚀 QUICK START
================

### Immediate Steps:
1. **Create directory structure** (Phase 1)
2. **Implement configuration classes** (Fix import errors)
3. **Build core server logic** (Phase 2)
4. **Add server management scripts** (Phase 3)
5. **Test with individual server control** (Phase 4)

---

## 🧪 TESTING STRATEGY (CRITICAL!)
=================================

### **Why Step-by-Step Testing for Distributed Systems**

**❌ DON'T**: Build everything then test (leads to complex debugging)  
**✅ DO**: Test each component individually, then integrate

### **Benefits of Our Approach:**
- **Early Problem Detection**: Socket binding, port conflicts surface immediately
- **Isolated Debugging**: Database issues vs. networking issues vs. threading issues  
- **Complex Interactions**: Election + heartbeat + messaging = easier to debug separately
- **Our Track Record**: We've seen import errors that step-by-step would catch

### **Testing Philosophy:**
1. **Build** one module (~100 lines)
2. **Test** in isolation with simple commands
3. **Fix** any issues immediately  
4. **Integrate** with confidence
5. **Repeat** for next module

---

## 🏗️ DIRECTORY STRUCTURE (FINAL)
=================================

```
syncnet_v5/
├── common/
│   ├── __init__.py                    # Empty
│   ├── config/
│   │   ├── __init__.py               # DEFAULT_SERVER_CONFIGS (Fix import error)
│   │   ├── settings.py               # ServerConfig class (~60 lines)
│   │   └── constants.py              # Network constants (~20 lines)
│   └── messages/
│       ├── __init__.py               # Message classes (~50 lines)
│       └── protocol.py               # Serialization (~20 lines)
├── server/
│   ├── __init__.py                   # Empty
│   ├── main.py                       # Entry point with management (~80 lines)
│   ├── server.py                     # Main server logic (~300 lines)
│   ├── election.py                   # LCR algorithm (~120 lines)
│   ├── heartbeat.py                  # Health monitoring (~80 lines)
│   └── storage.py                    # Database operations (~100 lines)
├── client/
│   ├── __init__.py                   # Empty
│   ├── main.py                       # Entry point (~30 lines)
│   └── client.py                     # Client logic (~180 lines)
├── scripts/
│   ├── start_all_servers.bat         # Start cluster (~20 lines)
│   ├── start_server1.bat             # Individual server1 (~5 lines)
│   ├── start_server2.bat             # Individual server2 (~5 lines)
│   ├── start_server3.bat             # Individual server3 (~5 lines)
│   ├── status_check.py               # Cluster monitor (~60 lines)
│   └── demo_scenarios.py             # Testing scenarios (~80 lines)
├── requirements.txt                  # Dependencies (~10 lines)
└── README.md                         # Documentation (~50 lines)

Total: ~1,205 lines
```

---

## ⚡ CRITICAL FIXES (IMPLEMENT FIRST)
====================================

### 1. Fix Import Error: common/config/__init__.py
```python
"""Configuration module for SyncNet v5"""
from .settings import ServerConfig, NetworkConfig, DatabaseConfig
from .constants import PORT_OFFSETS, TIMEOUTS, NETWORK_CONSTANTS

# This fixes: cannot import name 'DEFAULT_SERVER_CONFIGS'
DEFAULT_SERVER_CONFIGS = [
    ServerConfig(
        server_id='server1',
        host='localhost',
        base_port=8000,
        ring_position=0
    ),
    ServerConfig(
        server_id='server2', 
        host='localhost',
        base_port=8001,
        ring_position=1
    ),
    ServerConfig(
        server_id='server3',
        host='localhost', 
        base_port=8002,
        ring_position=2
    )
]

__all__ = [
    'ServerConfig', 'NetworkConfig', 'DatabaseConfig',
    'DEFAULT_SERVER_CONFIGS', 'PORT_OFFSETS', 'TIMEOUTS', 'NETWORK_CONSTANTS'
]
```

### 2. Port Configuration: common/config/constants.py
```python
"""Network and timing constants - standardized for batch files"""

# Port offsets (matches existing batch files using 8000+ range)
PORT_OFFSETS = {
    'tcp_client': 0,        # 8000, 8001, 8002
    'server_discovery': 10,  # 8010, 8011, 8012
    'heartbeat': 20,        # 8020, 8021, 8022
    'election': 30,         # 8030, 8031, 8032
    'multicast_chat': 40    # 8040, 8041, 8042
}

# Timing configuration
TIMEOUTS = {
    'server_discovery': 3.0,
    'heartbeat_interval': 2.0,
    'leader_death_detection': 10.0,
    'election_timeout': 5.0,
    'tcp_connection': 3.0,
    'socket_timeout': 1.0
}

# Network constants
NETWORK_CONSTANTS = {
    'multicast_group': '239.0.0.1',
    'broadcast_address': '255.255.255.255',
    'buffer_size': 1024,
    'multicast_buffer_size': 10240,
    'multicast_ttl': 2
}
```

---

## 🏛️ CORE CLASSES (IMPLEMENT SECOND)
====================================

### common/config/settings.py
```python
"""Server and network configuration classes"""
from dataclasses import dataclass
import socket

@dataclass
class ServerConfig:
    """Configuration for individual server"""
    server_id: str
    host: str
    base_port: int
    ring_position: int
    
    @property
    def tcp_port(self) -> int:
        return self.base_port
    
    @property 
    def discovery_port(self) -> int:
        return self.base_port + 10
        
    @property
    def heartbeat_port(self) -> int:
        return self.base_port + 20
        
    @property
    def election_port(self) -> int:
        return self.base_port + 30
        
    @property
    def multicast_port(self) -> int:
        return self.base_port + 40

@dataclass 
class NetworkConfig:
    """Network-wide configuration"""
    multicast_group: str = '239.0.0.1'
    broadcast_address: str = '255.255.255.255'
    buffer_size: int = 1024

@dataclass
class DatabaseConfig:
    """Database configuration"""
    db_path: str = 'syncnet.db'
    connection_timeout: int = 30
```

### common/messages/__init__.py
```python
"""Message protocol for SyncNet v5"""
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any
import json
import time

class MessageType(Enum):
    """All message types"""
    # Server-to-server
    HEARTBEAT = "heartbeat"
    ELECTION = "election"
    SERVER_DISCOVERY = "server_discovery"
    DATA_REPLICATION = "data_replication"
    
    # Client-to-server
    CREATE_JOIN = "create_join"
    CHAT = "chat"
    LEAVE = "leave"
    CLIENT_DISCOVERY = "client_discovery"
    
    # Responses
    ACK = "ack"
    NACK = "nack"
    SERVER_LIST = "server_list"

@dataclass
class LamportClock:
    """Lamport logical clock"""
    timestamp: int = 0
    
    def tick(self) -> int:
        self.timestamp += 1
        return self.timestamp
        
    def update(self, received_timestamp: int) -> int:
        self.timestamp = max(self.timestamp, received_timestamp) + 1
        return self.timestamp

@dataclass
class Message:
    """Base message structure"""
    msg_type: MessageType
    sender_id: str
    data: Dict[str, Any]
    lamport_timestamp: int = 0
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
    
    def to_json(self) -> str:
        return json.dumps({
            'msg_type': self.msg_type.value,
            'sender_id': self.sender_id,
            'data': self.data,
            'lamport_timestamp': self.lamport_timestamp,
            'created_at': self.created_at
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        data = json.loads(json_str)
        return cls(
            msg_type=MessageType(data['msg_type']),
            sender_id=data['sender_id'],
            data=data['data'],
            lamport_timestamp=data['lamport_timestamp'],
            created_at=data['created_at']
        )
```

---

## 🎯 IMPLEMENTATION PHASES (REVISED WITH TESTING)
=================================================

### Phase 1: Foundation (Days 1-2) ✅ COMPLETED
```bash
# Step 1: Create directory structure
mkdir -p common/config common/messages server client scripts

# Step 2: Create __init__.py files
touch common/__init__.py common/config/__init__.py common/messages/__init__.py
touch server/__init__.py client/__init__.py

# Step 3: Implement configuration classes
# Files: common/config/__init__.py, settings.py, constants.py

# Step 4: Implement message protocol  
# Files: common/messages/__init__.py, protocol.py

# ✅ PHASE 1 VALIDATION
python -c "from common.config import DEFAULT_SERVER_CONFIGS; print('✅ Config loaded:', len(DEFAULT_SERVER_CONFIGS), 'servers')"
python -c "from common.messages import MessageType; print('✅ Message protocol loaded')"
```

### Phase 2A: Database Storage (Day 3 Morning)
```bash
# Step 5: Build database operations
# File: server/storage.py (~100 lines)

# 🧪 ISOLATED TESTING
python -c "from server.storage import MessageStorage; storage = MessageStorage(); print('✅ Database connection works')"
python -c "from server.storage import MessageStorage; storage = MessageStorage(); storage.store_message('test', 'Hello'); print('✅ Message storage works')"
python -c "from server.storage import MessageStorage; storage = MessageStorage(); msgs = storage.get_recent_messages(); print('✅ Message retrieval works:', len(msgs))"

# 🔍 WHAT TO VERIFY:
# - SQLite database file created (syncnet.db)
# - Tables created successfully
# - Insert/select operations work
# - No connection errors or locks
```

### Phase 2B: Election Algorithm (Day 3 Afternoon)
```bash
# Step 6: Build LCR election algorithm
# File: server/election.py (~120 lines)

# 🧪 ISOLATED TESTING  
python -c "from server.election import LCRElection; election = LCRElection('server1', 0); print('✅ Election object created')"
python -c "from server.election import LCRElection; election = LCRElection('server1', 0); election.start_election(); print('✅ Election logic works')"
python -c "from server.election import LCRElection; election = LCRElection('server1', 0); neighbor = election.get_next_neighbor(); print('✅ Ring logic works:', neighbor)"

# 🔍 WHAT TO VERIFY:
# - Ring formation logic correct
# - Election message creation works
# - Neighbor calculation accurate
# - No infinite loops or logic errors
```

### Phase 2C: Heartbeat Monitor (Day 4 Morning)
```bash
# Step 7: Build heartbeat monitoring
# File: server/heartbeat.py (~80 lines)

# 🧪 ISOLATED TESTING
python -c "from server.heartbeat import HeartbeatMonitor; hb = HeartbeatMonitor('server1'); print('✅ Heartbeat created')"
python -c "from server.heartbeat import HeartbeatMonitor; hb = HeartbeatMonitor('server1'); hb.send_heartbeat('server2'); print('✅ Heartbeat sending works')"
python -c "from server.heartbeat import HeartbeatMonitor; hb = HeartbeatMonitor('server1'); status = hb.check_server_health('server2'); print('✅ Health check works:', status)"

# 🔍 WHAT TO VERIFY:
# - Timing logic correct (2-second intervals)
# - Death detection threshold works (10 seconds)
# - No threading issues or deadlocks
# - Socket operations don't block indefinitely
```

### Phase 2D: Main Server Logic (Day 4 Afternoon)
```bash
# Step 8: Build main server logic
# File: server/server.py (~300 lines)

# 🧪 ISOLATED TESTING
python -c "from server.server import SyncNetServer; server = SyncNetServer('server1'); print('✅ Server object created')"
python -c "from server.server import SyncNetServer; server = SyncNetServer('server1'); server.initialize(); print('✅ Server initialization works')"

# 🔍 WHAT TO VERIFY:
# - All port bindings successful (8000, 8010, 8020, 8030, 8040)
# - No "Address already in use" errors
# - All threads start without crashes
# - Graceful shutdown works
```

### Phase 2E: Server Entry Point (Day 5 Morning)
```bash
# Step 9: Build server entry point
# File: server/main.py (~80 lines)

# 🧪 SINGLE SERVER TESTING
python -m server.main --server-id server1 --test-mode
# Should start and shut down cleanly within 10 seconds

# 🔍 WHAT TO VERIFY:
# - Command-line argument parsing works
# - Server starts on correct ports
# - Logging output shows proper startup sequence
# - Ctrl+C shutdown works gracefully
```

### Phase 3A: Client Implementation (Day 5 Afternoon)
```bash
# Step 10: Build client
# Files: client/client.py (~180 lines), client/main.py (~30 lines)

# 🧪 CLIENT TESTING
python -m client.main --server-host localhost --server-port 8000
# Test with server1 running

# 🔍 WHAT TO VERIFY:
# - Client connects to server successfully  
# - Can discover available servers
# - Can send/receive messages
# - Graceful disconnect works
```

### Phase 3B: Server Management Scripts (Day 6 Morning)
```bash
# Step 11: Build management scripts
# Files: scripts/start_server*.bat, scripts/status_check.py

# 🧪 SCRIPT TESTING
scripts/start_server1.bat  # Should start server1 cleanly
scripts/status_check.py    # Should show server1 as online

# 🔍 WHAT TO VERIFY:
# - Batch files execute without errors
# - Servers start on correct ports  
# - Status checker connects and reports accurately
# - Window titles and logging work properly
```

### Phase 4A: Cluster Formation (Day 6 Afternoon)
```bash
# Step 12: Multi-server testing
scripts/start_server1.bat
scripts/start_server2.bat  
scripts/start_server3.bat
# Wait 15 seconds
python scripts/status_check.py

# 🔍 WHAT TO VERIFY:
# - All 3 servers start successfully
# - Exactly 1 leader elected within 10 seconds
# - No port conflicts or binding errors
# - Status checker shows healthy cluster
```

### Phase 4B: Fault Tolerance Testing (Day 7)
```bash
# Step 13: Leader failure testing
# 1. Identify leader from status check
# 2. Close leader window (kill process)
# 3. Wait 15 seconds
# 4. Check status - should show new leader

# Step 14: Rolling restart testing  
# 1. Close server1, restart immediately
# 2. Close server2, restart immediately
# 3. Close server3, restart immediately
# 4. Verify all rejoin successfully

# Step 15: Client resilience testing
# 1. Start client connected to leader
# 2. Kill leader server
# 3. Verify client reconnects to new leader
# 4. Verify message history preserved

# 🔍 WHAT TO VERIFY:
# - Leader re-election within 15 seconds of failure
# - No data loss during leader transitions
# - Clients automatically reconnect
# - Message ordering preserved with Lamport clocks
```

## 🚨 TESTING FAILURE SCENARIOS & FIXES

### **Common Issues & Solutions:**

#### **Database Errors**
```bash
# Error: "database is locked"
# Fix: Ensure proper connection closing in storage.py
# Test: Run multiple database operations simultaneously

# Error: "no such table: messages"  
# Fix: Check table creation in storage initialization
# Test: Delete syncnet.db and restart
```

#### **Port Binding Errors**
```bash
# Error: "Address already in use"
# Fix: Check for running processes on ports 8000-8002
# Test: netstat -an | findstr 800  (Windows)

# Error: "Permission denied"
# Fix: Run as administrator or use ports > 1024
# Test: Try different port ranges
```

#### **Threading Issues**
```bash
# Error: Deadlocks or hanging
# Fix: Review thread synchronization in heartbeat.py
# Test: Start/stop servers rapidly multiple times

# Error: "Thread already started"
# Fix: Ensure proper thread lifecycle management
# Test: Graceful shutdown and restart sequences
```

#### **Election Problems**
```bash
# Error: Multiple leaders or no leader
# Fix: Review LCR algorithm implementation
# Test: Kill servers in different orders

# Error: Election never completes
# Fix: Check network timeouts and ring formation
# Test: Monitor election messages with logging
```

## ⚡ VALIDATION COMMANDS

### **Quick Health Check:**
```bash
# Test all imports work
python -c "from common.config import DEFAULT_SERVER_CONFIGS; from common.messages import MessageType; from server.storage import MessageStorage; print('✅ All imports successful')"

# Test database operations
python -c "from server.storage import MessageStorage; s = MessageStorage(); s.store_message('test', 'hello'); print('✅ Database operations work')"

# Test server startup
timeout 10 python -m server.main --server-id server1 --test-mode

# Test cluster formation
scripts/start_all_servers.bat && timeout 15 && python scripts/status_check.py
```

### **Success Criteria Checklist:**
- [ ] ✅ All modules import without errors
- [ ] ✅ Database operations work in isolation  
- [ ] ✅ Single server starts and stops cleanly
- [ ] ✅ Multiple servers form cluster with single leader
- [ ] ✅ Leader failure triggers re-election within 15 seconds
- [ ] ✅ Clients can connect and send messages
- [ ] ✅ Message persistence survives server restarts
- [ ] ✅ Status monitor shows accurate real-time information
- [ ] ✅ All management scripts work without errors

---

## 🛠️ SERVER MANAGEMENT SCRIPTS
==============================

### scripts/start_server1.bat
```batch
@echo off
title SyncNet v5 - Server 1
echo ====================================
echo  SyncNet v5 - Server 1 (Port 8000)
echo ====================================
python -m server.main --server-id server1 --log-level INFO
pause
```

### scripts/start_server2.bat  
```batch
@echo off
title SyncNet v5 - Server 2
echo ====================================
echo  SyncNet v5 - Server 2 (Port 8001)
echo ====================================
python -m server.main --server-id server2 --log-level INFO
pause
```

### scripts/start_server3.bat
```batch
@echo off
title SyncNet v5 - Server 3
echo ====================================
echo  SyncNet v5 - Server 3 (Port 8002)
echo ====================================
python -m server.main --server-id server3 --log-level INFO
pause
```

### scripts/start_all_servers.bat
```batch
@echo off
echo Starting SyncNet v5 Distributed Cluster...

start "Server 1" scripts/start_server1.bat
timeout /t 3 /nobreak >nul

start "Server 2" scripts/start_server2.bat
timeout /t 3 /nobreak >nul

start "Server 3" scripts/start_server3.bat
timeout /t 3 /nobreak >nul

echo All servers starting...
echo Use 'python scripts/status_check.py' to monitor
pause
```

---

## 📊 CLUSTER MONITORING
======================

### scripts/status_check.py (Essential for Testing)
```python
#!/usr/bin/env python3
"""SyncNet v5 Cluster Status Monitor"""
import socket
import json
import time

SERVER_CONFIGS = [
    {'id': 'server1', 'host': 'localhost', 'port': 8000},
    {'id': 'server2', 'host': 'localhost', 'port': 8001},
    {'id': 'server3', 'host': 'localhost', 'port': 8002}
]

def check_server_status(server_config):
    """Check individual server status"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        result = sock.connect_ex((server_config['host'], server_config['port']))
        
        if result == 0:
            sock.send(b'STATUS_REQUEST\n')
            response = sock.recv(1024).decode().strip()
            sock.close()
            return {
                'server_id': server_config['id'],
                'status': 'online',
                'is_leader': 'leader' in response.lower()
            }
        else:
            return {
                'server_id': server_config['id'],
                'status': 'offline',
                'is_leader': False
            }
    except Exception:
        return {
            'server_id': server_config['id'],
            'status': 'offline',
            'is_leader': False
        }

def print_cluster_status():
    """Print cluster status table"""
    print("=" * 50)
    print("SyncNet v5 Cluster Status")
    print("=" * 50)
    
    statuses = [check_server_status(config) for config in SERVER_CONFIGS]
    
    print(f"{'Server':<10} {'Status':<10} {'Leader':<8}")
    print("-" * 50)
    
    online_count = 0
    leader_count = 0
    
    for status in statuses:
        leader_str = "YES" if status['is_leader'] else "NO"
        status_str = "✅ ONLINE" if status['status'] == 'online' else "❌ OFFLINE"
        
        print(f"{status['server_id']:<10} {status_str:<15} {leader_str:<8}")
        
        if status['status'] == 'online':
            online_count += 1
        if status['is_leader']:
            leader_count += 1
    
    print("-" * 50)
    print(f"Summary: {online_count}/3 online, {leader_count} leader(s)")
    
    # Health check
    if online_count == 3 and leader_count == 1:
        print("✅ Cluster is healthy!")
    elif leader_count == 0:
        print("⚠️  No leader detected")
    elif leader_count > 1:
        print("🚨 Multiple leaders detected!")
    
    print("=" * 50)

if __name__ == '__main__':
    print_cluster_status()
```

---

## 🧪 TESTING SCENARIOS
======================

### Manual Testing Commands
```bash
# Test individual server startup
scripts/start_server1.bat
# (wait, then close)

scripts/start_server2.bat
# (wait, then close)

scripts/start_server3.bat
# (wait, then close)

# Test cluster formation
scripts/start_all_servers.bat
# (wait 10 seconds)
python scripts/status_check.py

# Test leader failure
# 1. Identify leader from status
# 2. Close leader window
# 3. Wait 15 seconds
# 4. Check status again

# Test rolling restart
# 1. Close server1, restart immediately
# 2. Close server2, restart immediately  
# 3. Close server3, restart immediately
# 4. Verify all rejoin successfully
```

### Success Criteria Checklist
- [ ] Import error `'DEFAULT_SERVER_CONFIGS'` resolved
- [ ] Individual servers start on ports 8000, 8001, 8002
- [ ] Cluster elects single leader within 10 seconds
- [ ] Leader failure triggers re-election within 15 seconds
- [ ] Status monitor shows accurate real-time information
- [ ] Rolling restart maintains service availability
- [ ] All scripts work without errors

---

## 📋 IMPLEMENTATION ORDER
========================

**Follow this exact sequence:**

1. **Create all directories and `__init__.py` files**
2. **Implement `common/config/constants.py`** (no dependencies)
3. **Implement `common/config/settings.py`** (imports constants)
4. **Implement `common/config/__init__.py`** (fixes import error)
5. **Implement `common/messages/__init__.py`** (message protocol)
6. **Implement `server/storage.py`** (database operations)
7. **Implement `server/election.py`** (LCR algorithm)
8. **Implement `server/heartbeat.py`** (health monitoring)
9. **Implement `server/server.py`** (main server logic)
10. **Implement `server/main.py`** (entry point)
11. **Create all batch scripts** (server management)
12. **Implement `scripts/status_check.py`** (monitoring)
13. **Test individual servers**
14. **Test cluster formation**
15. **Test fault tolerance scenarios**

---

## 🎯 FINAL DELIVERABLES
======================

When complete, you'll have:

✅ **Working distributed chat system** with 3 servers  
✅ **Individual server control** via batch scripts  
✅ **Real-time cluster monitoring** via status checker  
✅ **Fault tolerance testing** with guided scenarios  
✅ **Clean 1,200-line codebase** following distributed systems principles  
✅ **Complete documentation** for operation and testing  

**Ready to start implementation!** 🚀 