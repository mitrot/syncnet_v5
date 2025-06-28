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
        
        # Chat room state
        self.chat_rooms: Dict[str, set] = {} # room_name -> set of client_ids
        self.client_to_room: Dict[str, str] = {} # client_id -> room_name
        self.client_identities: Dict[str, dict] = {} # client_id -> {"username": "name"}

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

    def start(self) -> bool:
        """Start the SyncNet server and wait for it to be running."""
        if self._state != ServerState.STOPPED:
            self.logger.warning("Server is not stopped, cannot start.")
            return False

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
            return False
        
        # If we are here, the event was set. The state tells us if it was a success.
        if self._state == ServerState.RUNNING:
            return True
        else:
            self.logger.error(f"Server failed to start, final state: {self.state}")
            return False
            
    def _run(self):
        """The main execution loop of the server, run in a separate thread."""
        try:
            self.start_time = time.time()
            self._running = True
            
            self._setup_sockets()
            
            # Start network listeners first to ensure they are ready.
            self._start_thread(target=self._udp_listen_loop)
            self._start_thread(target=self._tcp_accept_loop)
            
            # Start the heartbeat sender and failure detector.
            self._start_thread(target=self._heartbeat_send_loop)
            self.heartbeat.start()

            # Start the election monitor last, once the communication backbone is stable.
            self._start_thread(target=self._monitor_cluster)

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
        listen_address = '0.0.0.0' # Listen on all available interfaces

        self.tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_server_socket.bind((listen_address, self.server_config.tcp_port))
        self.tcp_server_socket.listen(NETWORK_CONSTANTS['max_connections'])
        self.tcp_server_socket.settimeout(1.0)
        
        self.udp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.udp_server_socket.bind((listen_address, self.server_config.heartbeat_port))
        self.udp_server_socket.settimeout(1.0)
        
        self.logger.info(f"TCP listening on {listen_address}:{self.server_config.tcp_port}, UDP on {listen_address}:{self.server_config.heartbeat_port}")

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
                elif msg_type == "state_replication":
                    self._handle_state_replication(message['payload'])
                
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    self.logger.error(f"UDP listen loop error: {e}", exc_info=True)
    
    def _heartbeat_send_loop(self):
        """Dedicated loop for sending heartbeats periodically."""
        # Add a startup delay to ensure all servers are listening before we start sending
        time.sleep(3) 

        heartbeat_message = {
            "type": "heartbeat",
            "server_id": self.server_id
        }
        while self._running:
            try:
                self._broadcast_udp(heartbeat_message)
                time.sleep(TIMEOUTS['heartbeat_interval'])
            except Exception as e:
                self.logger.error(f"Heartbeat send loop error: {e}", exc_info=True)

    def _monitor_cluster(self):
        """Periodically check leader status and run elections if needed."""
        time.sleep(5) # Initial delay to allow cluster to stabilize
        while self._running:
            leader_is_alive = self.current_leader and self.current_leader in self.heartbeat.get_active_servers()
            
            if not leader_is_alive:
                if self.current_leader:
                    self.logger.warning(f"Leader {self.current_leader} is down. Clearing status and starting election.")
                    self.current_leader = None # Explicitly clear knowledge of the dead leader
                else:
                    self.logger.warning("Leader not established. Starting election.")
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
        """
        Handle a new client connection.
        If this server is the leader, it keeps the connection.
        If not, it sends a redirect and closes the connection.
        """
        client_id = f"{client_socket.getpeername()[0]}:{client_socket.getpeername()[1]}"

        # Immediately redirect if not the leader
        if not self.is_leader:
            self._send_redirect(client_socket)
            client_socket.close()
            return

        # --- From this point on, we are the leader ---
        self.client_connections[client_id] = client_socket
        self.logger.info(f"Client {client_id} connected to leader.")
        
        has_identity = False
        
        try:
            while self._running:
                data = client_socket.recv(NETWORK_CONSTANTS['buffer_size'])
                if not data:
                    break # Client disconnected
                
                request = json.loads(data.decode())
                command = request.get("command")
                payload = request.get("payload")

                if not has_identity:
                    if command == "set_username":
                        self._handle_set_username(client_id, payload)
                        has_identity = True
                    else:
                        # Ignore other commands until identity is established
                        self.logger.warning(f"Client {client_id} sent command '{command}' before setting username. Ignoring.")
                        continue
                else:
                    self.logger.debug(f"Leader received command '{command}' from {client_id}")
                    self._handle_client_command(client_id, command, payload)

        except (ConnectionResetError, BrokenPipeError, json.JSONDecodeError):
            self.logger.info(f"Client {client_id} disconnected.")
        except Exception as e:
            if self._running:
                self.logger.error(f"Client handling error for {client_id}: {e}")
        finally:
            self._cleanup_client(client_id)
            
    def _handle_client_command(self, client_id: str, command: str, payload: dict):
        """Process a command from a client. Must be run on the leader."""
        handler_map = {
            "set_username": self._handle_set_username,
            "create_room": self._handle_create_room,
            "join_room": self._handle_join_room,
            "list_rooms": self._handle_list_rooms,
            "leave_room": self._handle_leave_room,
            "chat": self._handle_chat_message,
            "whereami": self._handle_whereami,
            "ping": self._handle_ping
        }
        
        handler = handler_map.get(command)
        if handler:
            # Prevent clients from setting username more than once
            if command == "set_username":
                return self._send_to_client(client_id, {"type": "error", "payload": "Username is already set."})
            handler(client_id, payload)
        else:
            self._send_to_client(client_id, {"type": "error", "payload": f"Unknown command: {command}"})

    def _handle_set_username(self, client_id: str, payload: dict):
        username = payload.get("username", "Anonymous")
        with self._lock:
            # Do not allow changing username
            if client_id in self.client_identities:
                return
            self.client_identities[client_id] = {"username": username}
            self._replicate_state("set_identity", {"client_id": client_id, "identity": self.client_identities[client_id]})
        
        self.logger.info(f"Client {client_id} set username to '{username}'")
        # Acknowledge that the username has been set
        self._send_to_client(client_id, {"type": "ack", "payload": {"command": "set_username"}})

    def _handle_create_room(self, client_id: str, payload: dict):
        room_name = payload.get("room_name")
        if not room_name:
            return self._send_to_client(client_id, {"type": "error", "payload": "Room name is required."})

        with self._lock:
            if room_name in self.chat_rooms:
                return self._send_to_client(client_id, {"type": "error", "payload": f"Room '{room_name}' already exists."})
            
            # Create room and automatically join the creator
            self.chat_rooms[room_name] = {client_id}
            self.client_to_room[client_id] = room_name
            self._replicate_state("create_room", {"room_name": room_name, "client_id": client_id})

        self._send_to_client(client_id, {"type": "room_joined", "payload": {"room_name": room_name, "message": f"Successfully created and joined '{room_name}'."}})

    def _handle_join_room(self, client_id: str, payload: dict):
        room_name = payload.get("room_name")
        if not room_name:
            return self._send_to_client(client_id, {"type": "error", "payload": "Room name is required."})

        with self._lock:
            if room_name not in self.chat_rooms:
                return self._send_to_client(client_id, {"type": "error", "payload": f"Room '{room_name}' does not exist."})
            
            # Add client to room
            self.chat_rooms[room_name].add(client_id)
            self.client_to_room[client_id] = room_name
            self._replicate_state("join_room", {"room_name": room_name, "client_id": client_id})

        self._send_to_client(client_id, {"type": "room_joined", "payload": {"room_name": room_name, "message": f"Successfully joined '{room_name}'."}})

    def _handle_list_rooms(self, client_id: str, payload: dict):
        with self._lock:
            room_list = list(self.chat_rooms.keys())
        self._send_to_client(client_id, {"type": "room_list", "payload": room_list})
        
    def _handle_leave_room(self, client_id: str, payload: dict):
        with self._lock:
            room_name = self.client_to_room.pop(client_id, None)
            if room_name and room_name in self.chat_rooms:
                self.chat_rooms[room_name].discard(client_id)
                self._replicate_state("leave_room", {"room_name": room_name, "client_id": client_id})
                
        self._send_to_client(client_id, {"type": "room_left", "payload": {"message": "You have left the room."}})

    def _handle_chat_message(self, client_id: str, payload: dict):
        message = payload.get("message")
        if not message:
            return

        with self._lock:
            room_name = self.client_to_room.get(client_id)
            if not room_name:
                return self._send_to_client(client_id, {"type": "error", "payload": "You are not in a room."})

            sender_name = self.client_identities.get(client_id, {}).get("username", "Unknown")
            chat_message = {"type": "chat", "payload": {"sender_name": sender_name, "message": message}}
            
            # Broadcast to everyone in the room except the sender
            for member_id in self.chat_rooms.get(room_name, set()):
                if member_id != client_id:
                    self._send_to_client(member_id, chat_message)
    
    def _handle_whereami(self, client_id: str, payload: dict):
        with self._lock:
            room_name = self.client_to_room.get(client_id, "You are not in a room.")
        self._send_to_client(client_id, {"type": "info", "payload": room_name})

    def _handle_ping(self, client_id: str, payload: dict):
        """Respond to a client's ping to show the server is alive."""
        self._send_to_client(client_id, {"type": "pong"})

    def _cleanup_client(self, client_id: str):
        """Clean up resources for a disconnected client."""
        with self._lock:
            if client_id in self.client_connections:
                self.client_connections.pop(client_id).close()
            
            self.client_identities.pop(client_id, None)

            room_name = self.client_to_room.pop(client_id, None)
            if room_name and room_name in self.chat_rooms:
                self.chat_rooms[room_name].discard(client_id)
                self.logger.info(f"Client {client_id} removed from room {room_name}.")
                self._replicate_state("leave_room", {"room_name": room_name, "client_id": client_id})
                
    def _send_to_client(self, client_id: str, message: dict):
        """Send a JSON message to a specific client."""
        if client_id in self.client_connections:
            try:
                sock = self.client_connections[client_id]
                sock.sendall(json.dumps(message).encode())
            except Exception as e:
                self.logger.error(f"Failed to send message to {client_id}: {e}")
                self._cleanup_client(client_id)
                
    def _broadcast_udp(self, message: Dict):
        """Broadcast a UDP message to all other servers via unicast."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                # No broadcast needed; we send directly to each server.
                encoded_message = json.dumps(message).encode()
                
                for config in DEFAULT_SERVER_CONFIGS:
                    # Don't send to self
                    if config.server_id == self.server_id:
                        continue
                    
                    self.logger.debug(f"Broadcasting UDP message to {config.host}:{config.heartbeat_port}")
                    # Broadcast to heartbeat port
                    sock.sendto(encoded_message, (config.host, config.heartbeat_port))
        except Exception as e:
            self.logger.error(f"Failed to broadcast UDP message: {e}")

    def _replicate_state(self, action: str, data: dict):
        """Broadcast a state change to all other servers."""
        if not self.is_leader:
            return
            
        self.logger.debug(f"Replicating state: {action} with data {data}")
        replication_message = {
            "type": "state_replication",
            "payload": {
                "action": action,
                "data": data
            }
        }
        self._broadcast_udp(replication_message)
        
    def _handle_state_replication(self, payload: dict):
        """Apply a state change received from the leader."""
        if self.is_leader:
            return # Leaders don't apply replicated state, they create it.
            
        action = payload.get("action")
        data = payload.get("data")
        self.logger.debug(f"Follower applying state replication: {action}")

        with self._lock:
            room_name = data.get("room_name")
            client_id = data.get("client_id")

            if action == "create_room":
                self.chat_rooms[room_name] = {client_id}
                self.client_to_room[client_id] = room_name
            elif action == "join_room":
                if room_name in self.chat_rooms:
                    self.chat_rooms[room_name].add(client_id)
                else: # Edge case: join replication arrives before create
                    self.chat_rooms[room_name] = {client_id}
                self.client_to_room[client_id] = room_name
            elif action == "leave_room":
                if room_name in self.chat_rooms:
                    self.chat_rooms[room_name].discard(client_id)
                if client_id in self.client_to_room:
                    del self.client_to_room[client_id]
            elif action == "set_identity":
                identity = data.get("identity")
                self.client_identities[client_id] = identity

    def _send_redirect(self, client_socket: socket.socket):
        """Inform a client that this is not the leader and provide leader info."""
        if not self.current_leader:
            self.logger.warning("Redirect requested, but no leader is known. Closing connection.")
            return

        leader_config = next((c for c in DEFAULT_SERVER_CONFIGS if c.server_id == self.current_leader), None)
        if not leader_config:
            self.logger.error(f"Could not find config for leader {self.current_leader}")
            return
        
        redirect_info = {
            "type": "redirect",
            "payload": {
                "leader_id": leader_config.server_id,
                "leader_host": leader_config.host,
                "leader_port": leader_config.tcp_port
            }
        }
        
        try:
            client_socket.sendall(json.dumps(redirect_info).encode())
            self.logger.info(f"Redirected client to leader: {self.current_leader}")
        except Exception as e:
            self.logger.error(f"Failed to send redirect: {e}") 