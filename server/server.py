"""Main SyncNet v5 Server Implementation"""
import asyncio
import threading
import time
import logging
import socket
import json
import signal
import sys
from typing import Dict, List, Optional, Any
from enum import Enum
import traceback

from common.config import DEFAULT_SERVER_CONFIGS, TIMEOUTS, NETWORK_CONSTANTS
from server.heartbeat import HeartbeatMonitor

class ServerState(Enum):
    """Server operational states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

class SyncNetServer:
    """Main SyncNet v5 distributed chat server with simplified election."""
    
    def __init__(self, server_id: str):
        self.server_id = server_id
        self.server_config = next(c for c in DEFAULT_SERVER_CONFIGS if c.server_id == server_id)
        
        self._state = ServerState.STOPPED
        self.start_time = None
        self.current_leader: Optional[str] = None
        self.is_leader = False
        
        self.heartbeat = HeartbeatMonitor(self.server_id)
        
        self.tcp_server_socket: Optional[socket.socket] = None
        self.udp_server_socket: Optional[socket.socket] = None
        self.client_connections: Dict[str, Any] = {}
        
        self._lock = threading.RLock()
        self._main_thread: Optional[threading.Thread] = None
        self._threads: List[threading.Thread] = []
        self._startup_event = threading.Event()
        
        self.logger = logging.getLogger(f'server.{server_id}')
        self.logger.info("SyncNet server initialized")
    
    @property
    def state(self) -> str:
        """Get the current server state."""
        return self._state.value

    @state.setter
    def state(self, new_state: ServerState):
        """Set the server state and log changes."""
        if not isinstance(new_state, ServerState):
            raise TypeError("State must be a ServerState enum member.")
        
        if hasattr(self, '_state') and self._state == new_state:
            return
            
        self._state = new_state
        self.logger.info(f"Server state changed to: {new_state.name}")

    def start(self):
        """Start the SyncNet server and wait for it to be running."""
        if self._state != ServerState.STOPPED:
            self.logger.warning("Server is not stopped, cannot start.")
            return

        self.state = ServerState.STARTING
        self._startup_event.clear()
        
        self._main_thread = threading.Thread(target=self._run, daemon=True)
        self._main_thread.start()
        
        # Wait for the _run loop to signal that it's ready
        started = self._startup_event.wait(timeout=5.0)
        if not started:
            self.logger.error("Server failed to start within the timeout.")
            self.stop()
            self.state = ServerState.ERROR
            
    def _run(self):
        """The main execution loop of the server, run in a separate thread."""
        try:
            self.start_time = time.time()
            self._running = True
            
            self._setup_sockets()
            
            self._start_thread(target=self._tcp_accept_loop)
            self._start_thread(target=self._udp_listen_loop)
            self._start_thread(target=self._monitor_cluster)

            self.heartbeat.start()
            
            self.state = ServerState.RUNNING
            self._startup_event.set() # Signal that startup is complete
            self.logger.info(f"Server started successfully on TCP:{self.server_config.tcp_port}")

            # Keep this thread alive as long as the server is running
            while self._running:
                time.sleep(0.5)
            
        except Exception as e:
            self.logger.error(f"Server runtime error: {e}\n{traceback.format_exc()}")
            self.state = ServerState.ERROR
            self._startup_event.set() # Ensure start() doesn't hang on failure
        finally:
            # When the loop exits, ensure a clean shutdown
            self._shutdown_components()

    def stop(self):
        """Stop the server gracefully."""
        if self._state == ServerState.STOPPING or self._state == ServerState.STOPPED:
            return
            
        self.state = ServerState.STOPPING
        self.logger.info("Stopping SyncNet server...")
        
        self._running = False
        
        # Wait for the main thread to finish
        if self._main_thread and self._main_thread.is_alive():
            self._main_thread.join(timeout=2.0)
        
        # The _shutdown_components logic is now called from the _run loop's finally block.
        
        self.state = ServerState.STOPPED
        uptime = time.time() - self.start_time if self.start_time else 0
        self.logger.info(f"SyncNet server stopped after {uptime:.1f}s")

    def _shutdown_components(self):
        """Internal method to shut down all running components."""
        self.heartbeat.stop()
        self._close_sockets()
        
        for thread in self._threads:
            if thread.is_alive():
                # Threads are daemons, so we don't strictly need to join
                # but it's good practice if they hold resources.
                thread.join(timeout=1.0)

    def _setup_sockets(self):
        """Initialize TCP and UDP sockets."""
        self.tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_server_socket.bind((self.server_config.host, self.server_config.tcp_port))
        self.tcp_server_socket.listen(NETWORK_CONSTANTS['max_connections'])
        self.tcp_server_socket.settimeout(1.0)
        
        self.udp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_server_socket.bind((self.server_config.host, self.server_config.heartbeat_port))
        self.udp_server_socket.settimeout(1.0)
        
        self.logger.info(f"TCP listening on {self.server_config.tcp_port}, UDP on {self.server_config.heartbeat_port}")

    def _close_sockets(self):
        """Close all network sockets."""
        if self.tcp_server_socket:
            self.tcp_server_socket.close()
        if self.udp_server_socket:
            self.udp_server_socket.close()
        self.logger.info("Network sockets closed.")

    def _start_thread(self, target, args=()):
        """Create, start, and store a daemon thread."""
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()
        self._threads.append(thread)

    def _tcp_accept_loop(self):
        """Accept incoming client TCP connections."""
        while self._running:
            try:
                client_socket, address = self.tcp_server_socket.accept()
                self.logger.info(f"New client connection from {address}")
                self._start_thread(target=self._handle_client, args=(client_socket,))
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    self.logger.error(f"TCP accept loop error: {e}")

    def _udp_listen_loop(self):
        """Listen for and handle incoming UDP messages."""
        while self._running:
            try:
                data, _ = self.udp_server_socket.recvfrom(NETWORK_CONSTANTS['buffer_size'])
                message = json.loads(data.decode())
                
                msg_type = message.get("type")
                if msg_type == "heartbeat":
                    self.heartbeat.receive_heartbeat(message)
                elif msg_type == "leader_announcement":
                    self._handle_leader_announcement(message)
                
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    self.logger.error(f"UDP listen loop error: {e}")
    
    def _monitor_cluster(self):
        """Periodically check leader status and run elections if needed."""
        time.sleep(5) # Initial delay to allow cluster to stabilize
        while self._running:
            leader_is_alive = self.current_leader and self.current_leader in self.heartbeat.get_active_servers()
            
            if not leader_is_alive:
                self.logger.warning("Leader is down or not established. Starting election.")
                self._run_election()
            
            time.sleep(TIMEOUTS['election_timeout'])

    def _run_election(self):
        """
        Run a simplified leader election. The active server with the highest
        ring position (or lowest server_id as a tie-breaker) becomes the leader.
        """
        with self._lock:
            # Get the single, definitive list of all active servers (including this one)
            active_servers = self.heartbeat.get_active_servers()
            
            if self.server_id not in active_servers:
                self.logger.warning("Cannot participate in election; this server is not considered active.")
                self.is_leader = False
                return

            # Find the server config for all active servers
            active_server_configs = [
                config for sid in active_servers
                for config in DEFAULT_SERVER_CONFIGS if config.server_id == sid
            ]
            
            if not active_server_configs:
                self.logger.error("Could not run election: no active servers found.")
                return

            # Determine winner by highest ring position, then lowest server_id
            winner = sorted(active_server_configs, key=lambda c: (-c.ring_position, c.server_id))[0]

            self.logger.info(f"Election result: {winner.server_id} is the new leader.")

            if winner.server_id == self.server_id:
                self._become_leader()
                self._broadcast_udp({
                    "type": "leader_announcement",
                    "leader_id": self.server_id
                })
            else:
                self.is_leader = False
                self.current_leader = winner.server_id

    def _handle_leader_announcement(self, message: Dict):
        """Handle a leader announcement from another server."""
        new_leader = message.get("leader_id")
        if new_leader and new_leader != self.current_leader:
            with self._lock:
                self.current_leader = new_leader
                self.is_leader = (self.server_id == new_leader)
                self.logger.info(f"New leader elected: {new_leader}. I am {'the leader' if self.is_leader else 'a follower'}.")

    def _become_leader(self):
        """Set this server as the leader."""
        with self._lock:
            if not self.is_leader:
                self.logger.info("I am now the leader!")
                self.is_leader = True
            self.current_leader = self.server_id
    
    def _handle_client(self, client_socket: socket.socket):
        """Handle an individual client connection."""
        # Simplified client handling
        try:
            while self._running:
                data = client_socket.recv(NETWORK_CONSTANTS['buffer_size'])
                if not data:
                    break
                
                message = json.loads(data.decode())
                if self.is_leader:
                    self.logger.info(f"Leader received message: {message}")
                    # In a full implementation, leader would process and distribute this.
                else:
                    # Forward to leader or reject
                    client_socket.send(json.dumps({"type": "error", "message": "Not the leader"}).encode())

        except (ConnectionResetError, BrokenPipeError):
            self.logger.info("Client disconnected.")
        except Exception as e:
            if self._running:
                self.logger.error(f"Client handling error: {e}")
        finally:
            client_socket.close()

    def _broadcast_udp(self, message: Dict):
        """Broadcast a UDP message to all other servers."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                encoded_message = json.dumps(message).encode()
                for config in DEFAULT_SERVER_CONFIGS:
                    # Broadcast to heartbeat port
                    sock.sendto(encoded_message, (config.host, config.heartbeat_port))
        except Exception as e:
            self.logger.error(f"Failed to broadcast UDP message: {e}")

    def get_server_status(self) -> Dict[str, Any]:
        """Get comprehensive server status."""
        return {
            'server_id': self.server_id,
            'state': self.state,
            'is_leader': self.is_leader,
            'current_leader': self.current_leader,
            'active_servers': self.heartbeat.get_active_servers(),
            'server_statuses': self.heartbeat.get_server_statuses()
        }

# Signal handler for graceful shutdown
_server_instance = None

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global _server_instance
    if _server_instance:
        print(f"\nReceived signal {signum}, shutting down gracefully...")
        _server_instance.stop()
        sys.exit(0)

def main(server_id: str):
    """Main server startup function"""
    global _server_instance
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start server
    _server_instance = SyncNetServer(server_id)
    
    try:
        if _server_instance.start():
            print(f"🚀 SyncNet server {server_id} is running!")
            print("Press Ctrl+C to stop")
            
            # Keep main thread alive
            while _server_instance.state == ServerState.RUNNING:
                time.sleep(1)
        else:
            print(f"❌ Failed to start server {server_id}")
            return 1
            
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        return 1
    finally:
        if _server_instance:
            _server_instance.stop()
    
    return 0

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python server.py <server_id>")
        print("Available server_ids: server1, server2, server3")
        sys.exit(1)
    
    server_id = sys.argv[1]
    sys.exit(main(server_id)) 