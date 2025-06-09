#!/usr/bin/env python3
"""SyncNet v5 Client Implementation - Phase 3A"""

import asyncio
import json
import logging
import socket
import sys
import time
import threading
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

# Add parent directory to path for imports
sys.path.append('.')

from common.config import DEFAULT_SERVER_CONFIGS, TIMEOUTS, NETWORK_CONSTANTS

class ClientState(Enum):
    """Client connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"

@dataclass
class ServerInfo:
    """Information about a server"""
    server_id: str
    host: str
    tcp_port: int
    ring_position: int
    is_leader: bool = False
    last_ping: float = 0.0
    connection_failures: int = 0

class SyncNetClient:
    """SyncNet v5 distributed chat client"""
    
    def __init__(self, username: str, preferred_server: Optional[str] = None):
        self.username = username
        self.client_id = f"client_{username}_{int(time.time())}"
        
        # Connection state
        self.state = ClientState.DISCONNECTED
        self.current_server: Optional[ServerInfo] = None
        self.socket: Optional[socket.socket] = None
        
        # Server information
        self.servers = self._load_server_configs()
        self.preferred_server = preferred_server or 'server1'
        
        # Messaging
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.message_queue: List[Dict] = []
        self.last_message_id = 0
        
        # Threading
        self._running = False
        self._receiver_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        
        # Statistics
        self.messages_sent = 0
        self.messages_received = 0
        self.reconnect_attempts = 0
        self.start_time = time.time()
        
        # Logging
        self.logger = logging.getLogger(f'client.{username}')
        
        # Setup default message handlers
        self._setup_message_handlers()
        
        self.logger.info(f"SyncNet client initialized for {username}")
    
    def _load_server_configs(self) -> Dict[str, ServerInfo]:
        """Load server configurations"""
        servers = {}
        for config in DEFAULT_SERVER_CONFIGS:
            servers[config.server_id] = ServerInfo(
                server_id=config.server_id,
                host=config.host,
                tcp_port=config.tcp_port,
                ring_position=config.ring_position
            )
        return servers
    
    def _setup_message_handlers(self):
        """Setup default message handlers"""
        self.register_handler('welcome', self._handle_welcome)
        self.register_handler('chat', self._handle_chat_message)
        self.register_handler('user_joined', self._handle_user_joined)
        self.register_handler('user_left', self._handle_user_left)
        self.register_handler('status_response', self._handle_status_response)
        self.register_handler('error', self._handle_error)
    
    def register_handler(self, message_type: str, handler: Callable):
        """Register a message handler"""
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)
    
    def connect(self, server_id: Optional[str] = None) -> bool:
        """Connect to a server"""
        target_server = server_id or self.preferred_server
        
        if target_server not in self.servers:
            self.logger.error(f"Invalid server: {target_server}")
            return False
        
        with self._lock:
            if self.state == ClientState.CONNECTED:
                self.logger.warning("Already connected")
                return True
            
            self.state = ClientState.CONNECTING
            server_info = self.servers[target_server]
            
            try:
                # Create TCP socket
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(TIMEOUTS['tcp_connection'])
                
                # Connect to server
                self.socket.connect((server_info.host, server_info.tcp_port))
                
                # Update connection state
                self.current_server = server_info
                self.state = ClientState.CONNECTED
                self.reconnect_attempts = 0
                
                # Start receiver thread
                self._running = True
                self._receiver_thread = threading.Thread(
                    target=self._receiver_loop,
                    name=f"receiver-{self.username}",
                    daemon=True
                )
                self._receiver_thread.start()
                
                # Send join message
                self._send_join_message()
                
                self.logger.info(f"Connected to {target_server} at {server_info.host}:{server_info.tcp_port}")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to connect to {target_server}: {e}")
                self.state = ClientState.ERROR
                if self.socket:
                    self.socket.close()
                    self.socket = None
                return False
    
    def disconnect(self):
        """Disconnect from server"""
        with self._lock:
            if self.state == ClientState.DISCONNECTED:
                return
            
            self.logger.info("Disconnecting from server...")
            self._running = False
            
            # Close socket
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
            
            # Wait for receiver thread
            if self._receiver_thread and self._receiver_thread.is_alive():
                self._receiver_thread.join(timeout=2.0)
            
            self.state = ClientState.DISCONNECTED
            self.current_server = None
            
            uptime = time.time() - self.start_time
            self.logger.info(f"Disconnected after {uptime:.1f}s")
    
    def _send_join_message(self):
        """Send join message to server"""
        join_message = {
            'type': 'join',
            'username': self.username,
            'client_id': self.client_id,
            'timestamp': time.time()
        }
        self._send_message(join_message)
    
    def _send_message(self, message: Dict) -> bool:
        """Send message to server"""
        if not self.socket or self.state != ClientState.CONNECTED:
            self.logger.warning("Not connected to server")
            return False
        
        try:
            # Add message ID
            message['message_id'] = self.last_message_id
            self.last_message_id += 1
            
            # Serialize and send
            data = json.dumps(message).encode('utf-8')
            self.socket.send(data)
            
            self.messages_sent += 1
            self.logger.debug(f"Sent message: {message['type']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            self._handle_connection_error()
            return False
    
    def _receiver_loop(self):
        """Main message receiver loop"""
        self.logger.debug("Receiver thread started")
        
        # Set socket timeout for receive operations
        if self.socket:
            self.socket.settimeout(TIMEOUTS['socket_timeout'])
        
        while self._running and self.socket:
            try:
                # Receive data with timeout
                data = self.socket.recv(NETWORK_CONSTANTS['max_message_size'])
                if not data:
                    self.logger.debug("No data received, server disconnected")
                    break  # Server disconnected
                
                # Parse message
                try:
                    message = json.loads(data.decode('utf-8'))
                    self._handle_received_message(message)
                    self.messages_received += 1
                    
                except json.JSONDecodeError:
                    self.logger.warning(f"Invalid JSON received: {data[:100]}")
                
            except socket.timeout:
                # This is normal, just continue the loop
                continue
            except ConnectionResetError:
                self.logger.warning("Server disconnected")
                break
            except OSError as e:
                # Socket was closed
                if self._running:
                    self.logger.warning(f"Socket error: {e}")
                break
            except Exception as e:
                if self._running:
                    self.logger.error(f"Error in receiver loop: {e}")
                    break
        
        self.logger.debug("Receiver thread stopped")
        if self._running:
            self._handle_connection_error()
    
    def _handle_received_message(self, message: Dict):
        """Handle incoming message from server"""
        message_type = message.get('type', 'unknown')
        
        # Call registered handlers
        if message_type in self.message_handlers:
            for handler in self.message_handlers[message_type]:
                try:
                    handler(message)
                except Exception as e:
                    self.logger.error(f"Error in message handler for {message_type}: {e}")
        else:
            self.logger.debug(f"No handler for message type: {message_type}")
    
    def _handle_connection_error(self):
        """Handle connection error and attempt reconnection"""
        if not self._running:
            return
        
        with self._lock:
            if self.state == ClientState.RECONNECTING:
                return  # Already reconnecting
            
            self.state = ClientState.RECONNECTING
            self.reconnect_attempts += 1
            
            self.logger.warning(f"Connection lost, attempting reconnection ({self.reconnect_attempts})")
            
            # Try to reconnect
            if self.reconnect_attempts <= 3:
                time.sleep(2 ** self.reconnect_attempts)  # Exponential backoff
                self._attempt_reconnect()
            else:
                self.logger.error("Max reconnection attempts reached")
                self.state = ClientState.ERROR
    
    def _attempt_reconnect(self):
        """Attempt to reconnect to servers"""
        # Try current server first
        if self.current_server:
            if self.connect(self.current_server.server_id):
                return
        
        # Try other servers
        for server_id in self.servers:
            if server_id != (self.current_server.server_id if self.current_server else None):
                if self.connect(server_id):
                    return
        
        # All servers failed
        self.logger.error("Failed to reconnect to any server")
        self.state = ClientState.ERROR
    
    # Message handlers
    def _handle_welcome(self, message: Dict):
        """Handle welcome message from server"""
        server_id = message.get('server_id', 'unknown')
        is_leader = message.get('is_leader', False)
        
        if server_id in self.servers:
            self.servers[server_id].is_leader = is_leader
        
        self.logger.info(f"Welcome from {server_id} (Leader: {is_leader})")
        print(f"✅ Connected to {server_id} (Leader: {is_leader})")
    
    def _handle_chat_message(self, message: Dict):
        """Handle chat message"""
        username = message.get('username', 'Anonymous')
        content = message.get('content', '')
        server_id = message.get('server_id', 'unknown')
        timestamp = message.get('timestamp', 0)
        
        # Don't show our own messages
        if username == self.username:
            return
        
        # Format timestamp
        dt = datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e10 else timestamp)
        time_str = dt.strftime('%H:%M:%S')
        
        print(f"[{time_str}] {username}: {content}")
    
    def _handle_user_joined(self, message: Dict):
        """Handle user joined notification"""
        username = message.get('username', 'Anonymous')
        if username != self.username:
            print(f"🟢 {username} joined the chat")
    
    def _handle_user_left(self, message: Dict):
        """Handle user left notification"""
        username = message.get('username', 'Anonymous')
        if username != self.username:
            print(f"🔴 {username} left the chat")
    
    def _handle_status_response(self, message: Dict):
        """Handle server status response"""
        status = message.get('status', {})
        print(f"\n📊 Server Status:")
        print(f"   Server: {status.get('server_id', 'unknown')}")
        print(f"   State: {status.get('state', 'unknown')}")
        print(f"   Uptime: {status.get('uptime', 0):.1f}s")
        print(f"   Is Leader: {status.get('is_leader', False)}")
        print(f"   Connected Clients: {status.get('connected_clients', 0)}")
        print(f"   Messages Processed: {status.get('messages_processed', 0)}")
    
    def _handle_error(self, message: Dict):
        """Handle error message"""
        error = message.get('error', 'Unknown error')
        print(f"❌ Error: {error}")
    
    # Public API methods
    def send_chat_message(self, content: str) -> bool:
        """Send a chat message"""
        if not content.strip():
            return False
        
        message = {
            'type': 'chat',
            'username': self.username,
            'content': content.strip(),
            'timestamp': time.time()
        }
        
        return self._send_message(message)
    
    def request_status(self) -> bool:
        """Request server status"""
        message = {
            'type': 'status',
            'username': self.username
        }
        
        return self._send_message(message)
    
    def get_client_status(self) -> Dict[str, Any]:
        """Get client status information"""
        uptime = time.time() - self.start_time
        
        return {
            'username': self.username,
            'client_id': self.client_id,
            'state': self.state.value,
            'uptime': round(uptime, 1),
            'current_server': self.current_server.server_id if self.current_server else None,
            'messages_sent': self.messages_sent,
            'messages_received': self.messages_received,
            'reconnect_attempts': self.reconnect_attempts,
            'available_servers': list(self.servers.keys())
        }
    
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self.state == ClientState.CONNECTED
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


class SyncNetChatUI:
    """Simple chat UI for SyncNet client"""
    
    def __init__(self, username: str):
        self.username = username
        self.client = SyncNetClient(username)
        self.running = False
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def start(self):
        """Start the chat UI"""
        print("🚀 SyncNet v5 Distributed Chat Client")
        print("="*50)
        print(f"Username: {self.username}")
        print("Type '/help' for available commands")
        print("="*50)
        
        # Connect to server
        if not self.client.connect():
            print("❌ Failed to connect to server")
            return
        
        self.running = True
        
        try:
            while self.running:
                try:
                    # Get user input
                    user_input = input("> ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle commands
                    if user_input.startswith('/'):
                        self._handle_command(user_input)
                    else:
                        # Send chat message
                        self.client.send_chat_message(user_input)
                        
                except KeyboardInterrupt:
                    break
                except EOFError:
                    break
                    
        finally:
            self.client.disconnect()
            print("\n👋 Goodbye!")
    
    def _handle_command(self, command: str):
        """Handle user commands"""
        parts = command[1:].split()
        if not parts:
            return
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        if cmd == 'help':
            self._show_help()
        elif cmd == 'status':
            self.client.request_status()
        elif cmd == 'info':
            self._show_client_info()
        elif cmd == 'connect':
            server_id = args[0] if args else None
            if self.client.connect(server_id):
                print(f"✅ Connected to {server_id or 'default server'}")
            else:
                print(f"❌ Failed to connect to {server_id or 'default server'}")
        elif cmd == 'disconnect':
            self.client.disconnect()
            print("⚠️  Disconnected from server")
        elif cmd == 'quit' or cmd == 'exit':
            self.running = False
        else:
            print(f"❌ Unknown command: {cmd}")
    
    def _show_help(self):
        """Show available commands"""
        print("\n📋 Available Commands:")
        print("  /help          - Show this help message")
        print("  /status        - Request server status")
        print("  /info          - Show client information")
        print("  /connect [id]  - Connect to specific server")
        print("  /disconnect    - Disconnect from server")
        print("  /quit          - Exit the client")
        print("\n💬 Just type your message to chat!")
    
    def _show_client_info(self):
        """Show client information"""
        status = self.client.get_client_status()
        print(f"\n🖥️  Client Information:")
        print(f"   Username: {status['username']}")
        print(f"   Client ID: {status['client_id']}")
        print(f"   State: {status['state']}")
        print(f"   Uptime: {status['uptime']}s")
        print(f"   Current Server: {status['current_server']}")
        print(f"   Messages Sent: {status['messages_sent']}")
        print(f"   Messages Received: {status['messages_received']}")
        print(f"   Reconnect Attempts: {status['reconnect_attempts']}")
        print(f"   Available Servers: {', '.join(status['available_servers'])}")


def main():
    """Main client entry point"""
    if len(sys.argv) < 2:
        print("Usage: python syncnet_client.py <username> [server_id]")
        print("Available servers: server1, server2, server3")
        sys.exit(1)
    
    username = sys.argv[1]
    server_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        ui = SyncNetChatUI(username)
        ui.start()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Client error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main() 