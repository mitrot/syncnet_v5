"""Main SyncNet v5 Server Implementation"""
import asyncio
import threading
import time
import logging
import socket
import json
import signal
import sys
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from common.config import DEFAULT_SERVER_CONFIGS, TIMEOUTS, NETWORK_CONSTANTS
from common.messages import Message, MessageType, LamportClock
from server.storage import MessageStorage
from server.election import LCRElection, ElectionState, ElectionMessage
from server.heartbeat import HeartbeatMonitor, ServerStatus

class ServerState(Enum):
    """Server operational states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class ClientConnection:
    """Information about connected clients"""
    client_id: str
    socket: socket.socket
    last_seen: float
    username: Optional[str] = None

class SyncNetServer:
    """Main SyncNet v5 distributed chat server"""
    
    def __init__(self, server_id: str):
        # Validate server_id
        valid_servers = {config.server_id for config in DEFAULT_SERVER_CONFIGS}
        if server_id not in valid_servers:
            raise ValueError(f"Invalid server_id: {server_id}. Must be one of: {valid_servers}")
        
        self.server_id = server_id
        self.server_config = next(config for config in DEFAULT_SERVER_CONFIGS if config.server_id == server_id)
        
        # Server state
        self.state = ServerState.STOPPED
        self.start_time = None
        self.lamport_clock = LamportClock()
        
        # Core components
        self.storage = MessageStorage(server_id)
        self.election = LCRElection(server_id, self.server_config.ring_position)
        self.heartbeat = HeartbeatMonitor(self.server_id)
        
        # Network components
        self.tcp_server_socket = None
        self.udp_heartbeat_socket = None
        self.udp_election_socket = None  # New socket for election messages
        self.client_connections: Dict[str, ClientConnection] = {}
        
        # Threading
        self._lock = threading.RLock()
        self._running = False
        self._tcp_thread = None
        self._udp_thread = None
        self._udp_election_thread = None
        self._client_handler_threads = []
        
        # Message queues and handlers
        self.message_queue = asyncio.Queue()
        self.pending_elections = {}
        
        # Statistics
        self.messages_processed = 0
        self.clients_served = 0
        self.elections_participated = 0
        
        # Logging
        self.logger = logging.getLogger(f'server.{server_id}')
        
        # Setup heartbeat integration with election
        self.heartbeat.add_failure_callback(self._on_server_failure)
        self.heartbeat.add_recovery_callback(self._on_server_recovery)
        
        self.logger.info(f"SyncNet server {server_id} initialized")
    
    def start(self) -> bool:
        """Start the SyncNet server"""
        try:
            self.state = ServerState.STARTING
            self.start_time = time.time()
            
            self.logger.info(f"Starting SyncNet server {self.server_id}")
            
            # Initialize components
            self.storage = MessageStorage(f'data/{self.server_id}_messages.db')
            self.election = LCRElection(self.server_id, self.server_config.ring_position)
            self.heartbeat = HeartbeatMonitor(self.server_id)
            
            # Add heartbeat callbacks
            self.heartbeat.add_failure_callback(self._on_server_failure)
            self.heartbeat.add_recovery_callback(self._on_server_recovery)
            
            # Setup network
            self._setup_tcp_server()
            self._setup_udp_server()
            
            # Set state to RUNNING before starting threads
            self.state = ServerState.RUNNING
            
            # Start network services
            self._start_network_threads()
            
            # Start heartbeat monitoring
            self.heartbeat.start_monitoring()
            
            # Auto-start election after a brief delay to allow other servers to start
            def delayed_election():
                time.sleep(8)  # Wait 8 seconds for other servers to come online and establish heartbeats
                if self.state == ServerState.RUNNING:
                    self.logger.info("Starting automatic leader election")
                    self.start_election_process()
            
            election_thread = threading.Thread(target=delayed_election, daemon=True)
            election_thread.start()
            
            self.logger.info(f"Server {self.server_id} started successfully on TCP:{self.server_config.tcp_port}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start server: {e}")
            self.state = ServerState.ERROR
            self._cleanup()
            return False
    
    def stop(self) -> bool:
        """Stop the server gracefully"""
        with self._lock:
            if self.state not in [ServerState.RUNNING, ServerState.ERROR]:
                return True
            
            self.state = ServerState.STOPPING
            self.logger.info(f"Stopping SyncNet server {self.server_id}...")
            
            try:
                # Stop accepting new connections
                self._running = False
                
                # Stop heartbeat monitoring
                self.heartbeat.stop_monitoring()
                
                # Close all client connections
                self._close_all_clients()
                
                # Stop network threads
                self._stop_network_threads()
                
                # Close sockets
                self._close_sockets()
                
                # Close storage
                self.storage.close()
                
                self.state = ServerState.STOPPED
                
                uptime = time.time() - self.start_time if self.start_time else 0
                self.logger.info(f"✋ SyncNet server {self.server_id} stopped after {uptime:.1f}s")
                return True
                
            except Exception as e:
                self.logger.error(f"Error during server shutdown: {e}")
                self.state = ServerState.ERROR
                return False
    
    def _setup_tcp_server(self):
        """Setup TCP server socket for client connections"""
        self.tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_server_socket.bind((self.server_config.host, self.server_config.tcp_port))
        self.tcp_server_socket.listen(NETWORK_CONSTANTS['max_connections'])
        self.tcp_server_socket.settimeout(1.0)  # Non-blocking with timeout
        
        self.logger.info(f"TCP server listening on {self.server_config.host}:{self.server_config.tcp_port}")
    
    def _setup_udp_server(self):
        """Setup UDP server sockets for heartbeats and elections"""
        # Heartbeat socket
        self.udp_heartbeat_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_heartbeat_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_heartbeat_socket.bind((self.server_config.host, self.server_config.heartbeat_port))
        self.udp_heartbeat_socket.settimeout(1.0)  # Non-blocking with timeout
        
        # Election socket
        self.udp_election_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_election_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_election_socket.bind((self.server_config.host, self.server_config.election_port))
        self.udp_election_socket.settimeout(1.0)  # Non-blocking with timeout
        
        self.logger.info(f"UDP heartbeat listening on {self.server_config.host}:{self.server_config.heartbeat_port}")
        self.logger.info(f"UDP election listening on {self.server_config.host}:{self.server_config.election_port}")
    
    def _start_network_threads(self):
        """Start network handling threads"""
        # TCP connection handler
        self._tcp_thread = threading.Thread(
            target=self._tcp_server_loop,
            name=f"tcp-server-{self.server_id}",
            daemon=True
        )
        self._tcp_thread.start()
        
        # UDP heartbeat handler
        self._udp_thread = threading.Thread(
            target=self._udp_server_loop,
            name=f"udp-server-{self.server_id}",
            daemon=True
        )
        self._udp_thread.start()
        
        # UDP election handler
        self._udp_election_thread = threading.Thread(
            target=self._udp_election_loop,
            name=f"udp-election-{self.server_id}",
            daemon=True
        )
        self._udp_election_thread.start()
    
    def _tcp_server_loop(self):
        """Main TCP server loop"""
        self.logger.info(f"TCP server listening on {self.server_config.host}:{self.server_config.tcp_port}")
        
        try: 
            while self.state == ServerState.RUNNING:
                try:
                    client_socket, address = self.tcp_server_socket.accept()
                    
                    # Handle status check connections (quick connect/disconnect)
                    # If it's a status check, send status immediately
                    client_socket.settimeout(1.0)
                    try:
                        data = client_socket.recv(1024)
                        if data:
                            try:
                                request = json.loads(data.decode())
                                if request.get('type') == 'status':
                                    # Send status response immediately
                                    status = self.get_server_status()
                                    response = json.dumps(status).encode()
                                    client_socket.send(response)
                                    client_socket.close()
                                    continue
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                pass
                    except socket.timeout:
                        pass
                    
                    # Regular client connection
                    client_socket.settimeout(None)  # Remove timeout for regular clients
                    client_id = f"client_{int(time.time())}_{address[1]}"
                    
                    with self._lock:
                        self.client_connections[client_id] = ClientConnection(
                            client_id=client_id,
                            socket=client_socket,
                            last_seen=time.time()
                        )
                    
                    # Start client handler thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_id, client_socket),
                        daemon=True
                    )
                    client_thread.start()
                    self._client_handler_threads.append(client_thread)
                    
                    self.logger.info(f"New client connection: {client_id} from {address}")
                    
                except socket.timeout:
                    # Normal timeout - don't log this as it's expected behavior
                    continue
                except socket.error as e:
                    if self.state == ServerState.RUNNING:
                        self.logger.error(f"TCP server error: {e}")
                        
        except Exception as e:
            if self.state == ServerState.RUNNING:
                self.logger.error(f"TCP server loop error: {e}")
        finally:
            self.logger.info("TCP server loop ended")
    
    def _udp_server_loop(self):
        """Main UDP server loop for heartbeats and inter-server communication"""
        self.logger.info("UDP server thread started")
        
        while self.state == ServerState.RUNNING:
            try:
                data, address = self.udp_heartbeat_socket.recvfrom(NETWORK_CONSTANTS['max_message_size'])
                
                try:
                    message = json.loads(data.decode())
                    self._handle_udp_message(message, address)
                except json.JSONDecodeError:
                    self.logger.warning(f"Invalid JSON from {address}: {data[:100]}")
                
            except socket.timeout:
                continue  # Normal timeout, check if still running
            except Exception as e:
                if self.state == ServerState.RUNNING:
                    self.logger.error(f"Error in UDP server loop: {e}")
                    time.sleep(0.1)
        
        self.logger.info("UDP server thread stopped")
    
    def _handle_client(self, client_id: str, client_socket: socket.socket):
        """Handle individual client connection"""
        self.logger.debug(f"Client handler started for {client_id}")
        
        try:
            client_socket.settimeout(TIMEOUTS['socket_timeout'])
            
            while self.state == ServerState.RUNNING and client_id in self.client_connections:
                try:
                    # Receive message from client
                    data = client_socket.recv(NETWORK_CONSTANTS['max_message_size'])
                    if not data:
                        break  # Client disconnected
                    
                    try:
                        message_data = json.loads(data.decode())
                        self._handle_client_message(client_id, message_data)
                        
                        # Update last seen time
                        with self._lock:
                            if client_id in self.client_connections:
                                self.client_connections[client_id].last_seen = time.time()
                        
                    except json.JSONDecodeError:
                        self.logger.warning(f"Invalid JSON from client {client_id}")
                        
                except socket.timeout:
                    continue  # Normal timeout
                except ConnectionResetError:
                    break  # Client disconnected
                    
        except Exception as e:
            self.logger.error(f"Error handling client {client_id}: {e}")
        finally:
            self._disconnect_client(client_id)
        
        self.logger.debug(f"Client handler stopped for {client_id}")
    
    def _handle_client_message(self, client_id: str, message_data: Dict):
        """Handle incoming message from client"""
        try:
            message_type = message_data.get('type')
            
            if message_type == 'chat':
                self._handle_chat_message(client_id, message_data)
            elif message_type == 'join':
                self._handle_join_message(client_id, message_data)
            elif message_type == 'status':
                self._handle_status_request(client_id)
            elif message_type == 'ping':
                # Respond to ping with pong
                pong_msg = {'type': 'pong', 'timestamp': time.time()}
                self._send_to_client(client_id, pong_msg)
            else:
                self.logger.warning(f"Unknown message type from {client_id}: {message_type}")
                
        except Exception as e:
            self.logger.error(f"Error handling client message: {e}")
    
    def _handle_chat_message(self, client_id: str, message_data: Dict):
        """Handle chat message from client"""
        content = message_data.get('content', '')
        username = message_data.get('username', 'Anonymous')
        
        # Create message with Lamport timestamp
        timestamp = self.lamport_clock.tick()
        
        message = Message(
            msg_type=MessageType.CHAT,
            sender_id=self.server_id,
            data={
                'content': content,
                'client_id': client_id,
                'username': username,
                'server_timestamp': time.time()
            },
            lamport_timestamp=timestamp
        )
        
        # Store in database
        message_id = self.storage.store_message(message)
        
        # Broadcast to all connected clients
        self._broadcast_to_clients({
            'type': 'chat',
            'message_id': message_id,
            'content': content,
            'username': username,
            'timestamp': timestamp,
            'server_id': self.server_id
        })
        
        self.messages_processed += 1
        self.logger.debug(f"Processed chat message from {username} via {client_id}")
    
    def _handle_join_message(self, client_id: str, message_data: Dict):
        """Handle client join message"""
        username = message_data.get('username', 'Anonymous')
        
        with self._lock:
            if client_id in self.client_connections:
                self.client_connections[client_id].username = username
        
        # Send welcome message
        welcome_data = {
            'type': 'welcome',
            'server_id': self.server_id,
            'is_leader': self.election.is_leader(),
            'timestamp': self.lamport_clock.tick()
        }
        
        self._send_to_client(client_id, welcome_data)
        
        # Broadcast join notification
        self._broadcast_to_clients({
            'type': 'user_joined',
            'username': username,
            'server_id': self.server_id,
            'timestamp': self.lamport_clock.tick()
        })
        
        self.logger.info(f"User {username} joined via {client_id}")
    
    def _handle_status_request(self, client_id: str):
        """Handle status request from client or monitoring"""
        try:
            status = self.get_server_status()
            status_message = {
                'type': 'status_response',
                'timestamp': time.time(),
                'server_status': status
            }
            
            # Send response back to client
            if client_id in self.client_connections:
                self._send_to_client(client_id, status_message)
            
        except Exception as e:
            self.logger.error(f"Error handling status request: {e}")
    
    def _handle_udp_message(self, message: Dict, address: Tuple[str, int]):
        """Handle UDP message (heartbeats only - elections use dedicated socket)"""
        message_type = message.get('type')
        
        if message_type == 'heartbeat':
            sender_id = message.get('sender_id')
            if sender_id:
                self.heartbeat.receive_heartbeat(sender_id, message)
        elif message_type == 'election':
            # Elections should now go to the dedicated election port
            self.logger.warning(f"Election message received on heartbeat port from {address} - should use election port")
        else:
            self.logger.debug(f"Unknown UDP message type: {message_type}")
    
    def _handle_election_message(self, message: Dict, address: Tuple[str, int]):
        """Handle election-related messages"""
        try:
            # Parse election message
            election_msg = ElectionMessage(
                election_id=message.get('election_id'),
                candidate_id=message.get('candidate_id'),
                candidate_position=message.get('candidate_position', 0),
                message_type=message.get('message_type', 'election'),
                sender_id=message.get('sender_id'),
                lamport_timestamp=message.get('lamport_timestamp', 0)
            )
            
            # Process with LCR algorithm
            should_forward, response_msg = self.election.process_election_message(election_msg)
            
            if should_forward and response_msg:
                # Forward message to next server in ring
                next_server = self.election.get_next_neighbor()
                self._send_election_message(response_msg, next_server)
            
            self.elections_participated += 1
            self.logger.debug(f"Processed election message: {message.get('message_type')} from {message.get('sender_id')}")
            
        except Exception as e:
            self.logger.error(f"Error processing election message: {e}")
    
    def _send_election_message(self, election_msg, target_server_id: str):
        """Send election message to target server via UDP"""
        try:
            # Find target server config
            target_config = None
            for config in self.server_config.__class__.__dict__.get('__annotations__', {}):
                pass  # We'll get config from DEFAULT_SERVER_CONFIGS instead
            
            from common.config import DEFAULT_SERVER_CONFIGS
            target_config = next((config for config in DEFAULT_SERVER_CONFIGS if config.server_id == target_server_id), None)
            
            if not target_config:
                self.logger.error(f"Cannot find config for target server: {target_server_id}")
                return
            
            # Prepare message data
            message_data = {
                'type': 'election',
                'election_id': election_msg.election_id,
                'candidate_id': election_msg.candidate_id,
                'candidate_position': election_msg.candidate_position,
                'message_type': election_msg.message_type,
                'sender_id': election_msg.sender_id,
                'lamport_timestamp': election_msg.lamport_timestamp
            }
            
            # Send via UDP to ELECTION PORT (not heartbeat port!)
            self._send_udp_message(message_data, target_config.host, target_config.election_port)
            self.logger.debug(f"Sent {election_msg.message_type} message to {target_server_id} on election port {target_config.election_port}")
            
        except Exception as e:
            self.logger.error(f"Failed to send election message to {target_server_id}: {e}")
    
    def _send_udp_message(self, message: Dict, host: str, port: int):
        """Send UDP message to specified host:port"""
        try:
            data = json.dumps(message).encode()
            
            # Create temporary UDP socket for sending
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as send_socket:
                send_socket.sendto(data, (host, port))
                
        except Exception as e:
            self.logger.error(f"Failed to send UDP message to {host}:{port}: {e}")
    
    def start_election_process(self):
        """Manually start election process and send initial message"""
        try:
            # Sync failed servers with current heartbeat status before starting election
            self.election.sync_failed_servers_with_heartbeat(self.heartbeat)
            
            # Pass heartbeat monitor so retries can also sync
            election_id = self.election.start_election(self.heartbeat)
            if election_id:
                # Create and send initial election message
                election_msg = self.election.create_election_message("election")
                next_server = self.election.get_next_neighbor()
                self._send_election_message(election_msg, next_server)
                self.logger.info(f"Started election {election_id}, sent to {next_server}")
                
        except Exception as e:
            self.logger.error(f"Failed to start election process: {e}")
    
    def _broadcast_to_clients(self, message: Dict):
        """Broadcast message to all connected clients"""
        disconnected_clients = []
        
        with self._lock:
            for client_id, conn in self.client_connections.items():
                try:
                    self._send_to_client(client_id, message)
                except Exception as e:
                    self.logger.warning(f"Failed to send to {client_id}: {e}")
                    disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self._disconnect_client(client_id)
    
    def _send_to_client(self, client_id: str, message: Dict):
        """Send message to specific client"""
        with self._lock:
            if client_id not in self.client_connections:
                return
            
            conn = self.client_connections[client_id]
            data = json.dumps(message).encode()
            conn.socket.send(data)
    
    def _disconnect_client(self, client_id: str):
        """Disconnect and clean up client"""
        with self._lock:
            if client_id not in self.client_connections:
                return
            
            conn = self.client_connections[client_id]
            
            try:
                conn.socket.close()
            except:
                pass
            
            username = conn.username or 'Anonymous'
            del self.client_connections[client_id]
            
            self.logger.info(f"Client {client_id} ({username}) disconnected")
    
    def _on_server_failure(self, server_id: str):
        """Handle server failure detected by heartbeat monitor"""
        self.logger.warning(f"Server failure detected: {server_id}")
        
        # Trigger election if failed server was the leader
        if self.election.get_current_leader() == server_id:
            self.logger.info("Leader failed, starting new election")
            self.election.handle_server_failure(server_id)
    
    def _on_server_recovery(self, server_id: str):
        """Handle server recovery detected by heartbeat monitor"""
        self.logger.info(f"Server recovery detected: {server_id}")
        
        # Notify election system of server recovery
        self.election.handle_server_recovery(server_id)
    
    def _close_all_clients(self):
        """Close all client connections"""
        with self._lock:
            for client_id in list(self.client_connections.keys()):
                self._disconnect_client(client_id)
    
    def _stop_network_threads(self):
        """Stop network threads gracefully"""
        if self._tcp_thread and self._tcp_thread.is_alive():
            self._tcp_thread.join(timeout=2.0)
        
        if self._udp_thread and self._udp_thread.is_alive():
            self._udp_thread.join(timeout=2.0)
        
        if self._udp_election_thread and self._udp_election_thread.is_alive():
            self._udp_election_thread.join(timeout=2.0)
        
        # Stop client handler threads
        for thread in self._client_handler_threads:
            if thread.is_alive():
                thread.join(timeout=1.0)
    
    def _close_sockets(self):
        """Close network sockets"""
        if self.tcp_server_socket:
            try:
                self.tcp_server_socket.close()
            except:
                pass
        
        if self.udp_heartbeat_socket:
            try:
                self.udp_heartbeat_socket.close()
            except:
                pass
        
        if self.udp_election_socket:
            try:
                self.udp_election_socket.close()
            except:
                pass
    
    def _cleanup(self):
        """Cleanup resources after error"""
        try:
            self._close_all_clients()
            self._close_sockets()
            self.heartbeat.stop_monitoring()
            self.storage.close()
        except:
            pass
    
    def is_leader(self) -> bool:
        """Check if this server is the current leader"""
        return self.election.is_leader()
    
    def get_server_status(self) -> Dict[str, Any]:
        """Get comprehensive server status"""
        with self._lock:
            current_time = time.time()
            uptime = current_time - self.start_time if self.start_time else 0
            
            return {
                'server_id': self.server_id,
                'state': self.state.value,
                'uptime': round(uptime, 1),
                'is_leader': self.is_leader(),
                'current_leader': self.election.get_current_leader(),
                'ring_position': self.server_config.ring_position,
                'connected_clients': len(self.client_connections),
                'messages_processed': self.messages_processed,
                'clients_served': self.clients_served,
                'elections_participated': self.elections_participated,
                'lamport_timestamp': self.lamport_clock.timestamp,
                'network': {
                    'tcp_port': self.server_config.tcp_port,
                    'heartbeat_port': self.server_config.heartbeat_port,
                    'host': self.server_config.host
                },
                'storage_stats': self.storage.get_stats(),
                'heartbeat_stats': self.heartbeat.get_heartbeat_statistics(),
                'election_status': self.election.get_election_status()
            }
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()

    def _udp_election_loop(self):
        """Main UDP server loop for election messages"""
        self.logger.info("UDP election thread started")
        
        while self.state == ServerState.RUNNING:
            try:
                data, address = self.udp_election_socket.recvfrom(NETWORK_CONSTANTS['max_message_size'])
                
                try:
                    message = json.loads(data.decode())
                    # Only handle election messages on the election port
                    if message.get('type') == 'election':
                        self._handle_election_message(message, address)
                    else:
                        self.logger.warning(f"Non-election message received on election port from {address}: {message.get('type')}")
                except json.JSONDecodeError:
                    self.logger.warning(f"Invalid JSON from {address} on election port: {data[:100]}")
                
            except socket.timeout:
                continue  # Normal timeout, check if still running
            except Exception as e:
                if self.state == ServerState.RUNNING:
                    self.logger.error(f"Error in UDP election loop: {e}")
                    time.sleep(0.1)
        
        self.logger.info("UDP election thread stopped")

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