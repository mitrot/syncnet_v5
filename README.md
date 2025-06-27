# SyncNet v5 - A Lean & Robust Distributed Chat System

Welcome to SyncNet v5, a distributed, fault-tolerant chat server designed for stability and simplicity. After a significant refactoring, the system has been streamlined to focus on a robust core, removing unnecessary complexity to create a solid foundation for a distributed chat application.

## Core Architecture

The SyncNet architecture is built on a few simple, powerful ideas. A central `Server` class manages all core logic, from handling client connections to coordinating with other servers.

Server health is monitored by a lean `Heartbeat` module, which uses UDP broadcasts to check the status of other servers in the cluster. This allows the system to quickly detect when a server fails.

Leader election is now deterministic and incredibly reliable. The previous complex algorithm was replaced with a straightforward approach: when the current leader fails, the active server with the highest `ring_position` automatically and immediately becomes the new leader. This design completely prevents the deadlocks and timeout loops that affected the previous version. All inter-server communication, including heartbeats and leader announcements, happens over a single UDP port, further simplifying the network layout.

## Getting Started

The easiest way to get the server cluster running is to use the provided scripts.

### 1. Launch the Cluster
First, open a terminal in the project root and run the startup script. This will launch all three servers in separate terminal windows.

```bash
scripts\start_all_servers.bat
```

After a few moments, the servers will initialize, and you will see `server3` (the server with the highest ring position) announce itself as the leader.

### 2. Test Fault Tolerance
To see the system's resilience in action, simply find the terminal window for the current leader (`server3`) and close it. Within seconds, the remaining servers will detect the failure, and you will see a new leader (`server2`) elected to take its place.

### 3. Stop the Cluster
When you are finished, you can shut down all running server processes with a single command:
```bash
scripts\stop_all_servers.bat
```

## Project Status & Next Steps

The core distributed architecture of SyncNet is **complete and stable**. The system can reliably detect server failures and elect a new leader without interruption.

The immediate next step is to build the chat application logic on top of this solid foundation. This will involve implementing the client-side application, handling message forwarding between clients and the leader, and broadcasting messages from the leader out to all servers and their connected clients.

## System Configuration

### Server Network Details
Each server listens on two ports: a TCP port for client connections and a UDP port for all inter-server communication (like heartbeats).

| Server ID | Client Port (TCP) | Server Port (UDP) | Ring Position |
|:----------|:------------------|:------------------|:--------------|
| `server1` | `8000`            | `8020`            | `0`           |
| `server2` | `8001`            | `8021`            | `1`           |
| `server3` | `8002`            | `8022`            | `2`           |

### Timing Configuration
- **Heartbeat Interval**: `2.0 seconds`
- **Failure Detection Time**: `5.0 seconds`

## Codebase Overview

The project has been simplified to a few key components:

-   `server/main.py`: The entry point for starting a server instance via the command line.
-   `server/server.py`: The main server class containing all logic for elections, communication, and state.
-   `server/heartbeat.py`: The module responsible for monitoring server health.
-   `common/config/`: Contains all system configuration, including network ports and timing constants.
-   `scripts/`: Holds the batch scripts for easy cluster management.

## Troubleshooting

If you run into an "address already in use" error, it means another process is occupying a port needed by the servers. You can stop any lingering Python processes to free them up:

```powershell
taskkill /f /im python.exe
```