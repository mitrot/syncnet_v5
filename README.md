# SyncNet v5 - A Containerized, Fault-Tolerant Chat System

Welcome to SyncNet v5, a distributed chat server designed for stability, resilience, and ease of use. The entire server cluster runs within Docker, providing a self-contained, portable, and scalable environment.

## Core Architecture

- **Containerized Cluster**: The system is designed to run as a three-server cluster using Docker.
- **Deterministic Leader Election**: When a leader fails, the active server with the highest `ring_position` automatically becomes the new leader. This design is simple, robust, and prevents deadlocks.
- **State Replication**: The leader replicates critical state (like chat room creation and user identities) to all followers via UDP broadcasts, ensuring they are ready to take over if the leader fails.
- **Resilient Client**: The client application is designed to handle network failures gracefully. If it loses connection to the leader, it automatically searches for and connects to the new leader.

---

## How to Run the System

### Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop/)
- [Docker Compose](https://docs.docker.com/compose/install/) (for the simple local setup)
- [Python 3](https://www.python.org/downloads/) (for running the client)

---

## Deployment Scenarios

SyncNet can be deployed in several ways, from a simple local setup for development to a networked setup for multi-machine testing.

### Scenario 1: Local-Only Development (Easiest)

This method uses `docker-compose` to run all three servers on your local machine. The servers will only be accessible from your machine.

1.  **Configuration**: No changes needed. The default configuration uses Docker's internal networking.
2.  **Start the Cluster**:
    ```bash
    docker-compose up --build
    ```
3.  **Connect a Client**:
    ```bash
    python client/client.py --host localhost --port 8000
    ```

### Scenario 2: Networked Deployment (Single or Multi-Machine)

This method allows you to run the servers and make them accessible to other computers on your local area network (LAN). This is ideal for testing with collaborators.

#### Step 1: Configure Server IP Addresses

Before launching, you must configure the servers with the IP addresses they will run on.

1.  **Find the LAN IP Address** of the machine(s) you will run the servers on.
    *   On Windows, run `ipconfig`.
    *   On macOS/Linux, run `ip addr` or `ifconfig`.
    *   Look for the IPv4 address (e.g., `192.168.1.101`).

2.  **Edit the Configuration File**: Open `common/config/config.py`.

3.  **Update the `host` values** in `DEFAULT_SERVER_CONFIGS` with the real IP addresses.

    *   **If running all servers on one machine:** Use that machine's IP for all three server entries.
    *   **If running on three different machines:** Use the unique IP for each corresponding server.

    **Example for a single machine with IP `192.168.1.179`:**
    ```python
    DEFAULT_SERVER_CONFIGS = [
        ServerConfig(server_id='server1', host='192.168.1.179', tcp_port=8000, ...),
        ServerConfig(server_id='server2', host='192.168.1.179', tcp_port=8001, ...),
        ServerConfig(server_id='server3', host='192.168.1.179', tcp_port=8002, ...),
    ]
    ```

#### Step 2: Build the Docker Image

On each machine that will run a server, build the Docker image. This command only needs to be run once.

```bash
docker build -t syncnet-server .
```

#### Step 3: Launch the Servers

On each server machine, run the corresponding `docker run` command in a separate terminal.

*   **On Server Machine 1:**
    ```bash
    docker run -d --rm --name syncnet-server1 -p 8000:8000 -p 8020:8020/udp syncnet-server python -m server.main --server-id server1
    ```
*   **On Server Machine 2:**
    ```bash
    docker run -d --rm --name syncnet-server2 -p 8001:8001 -p 8021:8021/udp syncnet-server python -m server.main --server-id server2
    ```
*   **On Server Machine 3:**
    ```bash
    docker run -d --rm --name syncnet-server3 -p 8002:8002 -p 8022:8022/udp syncnet-server python -m server.main --server-id server3
    ```

To see the logs for a specific server, run `docker logs -f syncnet-server1`.
To stop the servers, run `docker stop syncnet-server1 syncnet-server2 syncnet-server3`.

#### Step 4: Connect a Networked Client

From any machine on the same network (including the server machines), run the client and point it to the IP address of any of the running servers.

```bash
# Example connecting to the server at 192.168.1.179 on its first port
python client/client.py --host 192.168.1.179 --port 8000
```
If you connect to a follower, the server will automatically redirect your client to the current leader.

---

## Codebase Overview

-   `server/server.py`: The main server class containing all logic for elections, state replication, and client handling.
-   `client/client.py`: The client application with robust reconnection and failover logic.
-   `server/heartbeat.py`: The module responsible for monitoring server health.
-   `common/config/config.py`: Contains all system configuration, including server network details.
-   `Dockerfile`: Defines the build steps for the server image.
-   `docker-compose.yml`: Defines the multi-container server cluster for local development.