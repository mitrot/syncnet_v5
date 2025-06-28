# SyncNet v5 - A Containerized, Fault-Tolerant Chat System

Welcome to SyncNet v5, a distributed chat server designed for stability, resilience, and ease of use. The entire server cluster runs within Docker, providing a self-contained, portable, and scalable environment right out of the box.

## Core Architecture

- **Containerized Cluster**: The system runs as a three-server cluster using Docker and Docker Compose. This simplifies deployment and ensures a consistent environment.
- **Deterministic Leader Election**: When a leader fails, the active server with the highest `ring_position` automatically becomes the new leader. This design is simple, robust, and prevents deadlocks.
- **State Replication**: The leader replicates critical state (like chat room creation and user identities) to all followers via UDP broadcasts, ensuring they are ready to take over if the leader fails.
- **Resilient Client**: The client application is designed to handle network failures gracefully. If it loses connection to the leader, it automatically searches for and connects to the new leader once one is elected.

---

## How to Run the System

### Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop/)
- [Docker Compose](https://docs.docker.com/compose/install/) (comes included with Docker Desktop)
- [Python 3](https://www.python.org/downloads/) (for running the client)

### Step 1: Start the Server Cluster

The entire three-server cluster is managed by Docker Compose. To start it, navigate to the project's root directory in your terminal and run a single command:

```bash
docker-compose up --build
```

This command will:
1.  Build the Docker image for the servers.
2.  Create and start three containers, one for each server.
3.  Display the combined logs for all three servers in your terminal.

After a few seconds, you will see the servers start up, perform an election, and select `server3` as the initial leader.

To run the servers in the background (detached mode), use:
```bash
docker-compose up --build -d
```

To stop the cluster, press `Ctrl+C` in the terminal where it's running, or run `docker-compose down` from the project directory.

### Step 2: Connect a Client

Once the server cluster is running, you can connect clients. The client is a Python script designed to run on your local machine.

1.  **Open a new terminal window.**
2.  **Navigate to the project root directory.**
3.  **Run the client script:**
    ```bash
    python client/client.py --host localhost --port 8000
    ```
    - You can connect to any of the server ports (`8000`, `8001`, or `8002`). If you connect to a follower, the server will automatically redirect your client to the current leader.

You can start multiple clients in separate terminal windows to test the chat functionality.

### Step 3: Test Fault Tolerance

This is where SyncNet shines. To test the system's resilience:

1.  Connect at least two clients (e.g., "Tom" and "Lena"). Have them join the same room.
2.  In the terminal where Docker Compose is running, find the current leader (initially `server3`).
3.  Kill the leader container by pressing `Ctrl+C` in the Docker terminal, or by running `docker-compose stop server3`.
4.  **Observe the server logs**: You will see the other servers detect the failure and elect a new leader (`server2`).
5.  **Observe the client terminals**: Both clients will briefly lose connection and then automatically reconnect to the new leader. They will be able to continue chatting seamlessly, with their state (username and current room) preserved.

---

## System Configuration

### Server Network Details

| Server ID | Hostname (in Docker) | Exposed Port (TCP) | Heartbeat Port (UDP) |
|:----------|:---------------------|:-------------------|:---------------------|
| `server1` | `server1`            | `8000`             | `8020`               |
| `server2` | `server2`            | `8001`             | `8021`               |
| `server3` | `server3`            | `8002`             | `8022`               |

### Codebase Overview

-   `server/server.py`: The main server class containing all logic for elections, state replication, and client handling.
-   `client/client.py`: The client application with robust reconnection and failover logic.
-   `server/heartbeat.py`: The module responsible for monitoring server health.
-   `common/config/`: Contains all system configuration.
-   `Dockerfile`: Defines the build steps for the server image.
-   `docker-compose.yml`: Defines the multi-container server cluster.