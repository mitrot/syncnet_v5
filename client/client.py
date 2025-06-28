import socket
import sys
import threading
import json
import time
import os
from typing import Any, List, Optional
import argparse

# Use platform-specific non-blocking input
try:
    import msvcrt
    _IS_WINDOWS = True
except ImportError:
    import sys
    import tty
    import termios
    _IS_WINDOWS = False

# add project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.config import DEFAULT_SERVER_CONFIGS, ServerConfig

class SyncNetClient:
    """A command-line client for the SyncNet v5 chat system."""

    def __init__(self, servers: Optional[List[ServerConfig]] = None):
        self.sock: socket.socket = None
        self.username: str = "Anonymous"
        self.is_connected = False
        self.servers = servers or DEFAULT_SERVER_CONFIGS
        self.current_server_index = 0
        self._receive_thread = None
        self._running = False
        self.in_room = False
        self.current_room = None
        self.prompt_lock = threading.Lock()
        self.state_change_event = threading.Event()
        self.connection_acknowledged = threading.Event()
        self.redirect_in_progress = threading.Event()
        self.last_pong_time = 0
        self._heartbeat_thread = None
        self._user_input_buffer = ""

    def _print_help(self):
        """Prints the available commands based on the client's state."""
        if self.in_room:
            print("\n--- SyncNet Room Menu ---")
            print("Commands: Chat <message>, Leave, WhereAmI, Help, Exit")
        else:
            print("\n--- SyncNet Main Menu ---")
            print("Commands: Create <room>, Join <room>, List, Help, Exit")

    def start(self):
        """Prompt for username and start the main client loop."""
        self.username = input("Please enter your name: ").strip() or "Anonymous"
        self._running = True
        
        # outer loop handles maintaining a connection.
        while self._running:
            self.connect() # This will block until a connection is made to the leader
            
            # inner loop handles the user interface while connected.
            if self.is_connected:
                self._print_help() # Show menu once on connect
                self._start_heartbeat()

            # Main UI loop
            while self.is_connected and self._running:
                self._handle_user_input()
                time.sleep(0.1) # Prevent busy-waiting
            
            # If the inner loop breaks, we are disconnected.
            # The connect() method will handle printing the reconnect message.
            if self._running:
                time.sleep(1) # Brief pause before trying to reconnect

    def connect(self):
        """Loop until a connection to the leader is established."""
        is_retrying = False
        while not self.is_connected and self._running:
            # If we're looping, it means a connection attempt failed.
            if is_retrying:
                time.sleep(2) # Wait before the next attempt
            else:
                # first attempt - If it fails, we'll start showing messages.
                pass

            server_config = self.servers[self.current_server_index]
            host, port = server_config.host, server_config.tcp_port
            try:
                if self.sock:
                    self.sock.close() # Ensure old socket is closed
                
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(3.0)
                self.sock.connect((host, port))
                
                # We have a socket, now perform the handshake
                self.sock.settimeout(None)
                self.connection_acknowledged.clear()
                self.redirect_in_progress.clear()
                self.send_command("set_username", {"username": self.username})
                
                # Start receiver thread if it's not alive
                if self._receive_thread is None or not self._receive_thread.is_alive():
                    self._receive_thread = threading.Thread(target=self._receive_messages, daemon=True)
                    self._receive_thread.start()

                # Wait for EITHER an acknowledgement OR a redirect signal
                # The receiver thread will set one of these events.
                self.connection_acknowledged.wait(timeout=5.0) 

                if self.redirect_in_progress.is_set():
                    # Redirect was handled by the receiver thread, which has updated the index.
                    # The loop will now try the correct server.
                    continue
                
                if self.connection_acknowledged.is_set():
                    self.is_connected = True
                    print(f"\n[System] Welcome! You are connected as '{self.username}'.")
                else:
                    # Timeout waiting for ack and no redirect occurred. Try next server.
                    self.is_connected = False
                    self.sock.close() 
                    self.current_server_index = (self.current_server_index + 1) % len(self.servers)

            except (socket.timeout, ConnectionRefusedError, OSError):
                self.current_server_index = (self.current_server_index + 1) % len(self.servers)
            
            if not self.is_connected and not is_retrying and self._running:
                print("\n[System] Connection lost. Searching for leader...")
                is_retrying = True
    
    def _receive_messages(self):
        """Listen for incoming messages from the server."""
        while self._running:
            try:
                # Set a timeout on recv so the loop can check self._running periodically
                if self.sock:
                    self.sock.settimeout(1.0) 
                    data = self.sock.recv(4096)
                else:
                    break

                if not data:
                    break # Connection closed by the server
                
                # Any data from the server resets the heartbeat timer
                self.last_pong_time = time.time()

                message = json.loads(data.decode())
                self._handle_server_message(message)

            except socket.timeout:
                continue # Allows the while self._running check to run
            except (socket.error, ConnectionResetError, BrokenPipeError, json.JSONDecodeError):
                # Any of these errors mean the connection is broken.
                # We break the loop silently and let the main loop handle it.
                break
        
        # If the connection breaks for any reason, reset the client's application state.
        # The main loop will handle reconnection.
        self.is_connected = False
        self.in_room = False
        self.current_room = None

    def _handle_server_message(self, message: dict):
        """Process and display messages from the server."""
        msg_type = message.get("type")
        payload = message.get("payload")

        with self.prompt_lock:
            # Clear the current line to make way for the server message
            current_line = self._get_prompt() + self._user_input_buffer
            sys.stdout.write('\r' + ' ' * len(current_line) + '\r')
            
            # Handle non-printing messages first
            if msg_type == "redirect":
                leader_host = payload.get("leader_host")
                leader_port = payload.get("leader_port")
                leader_id = payload.get("leader_id")

                if not (leader_host and leader_port):
                    print(f"[Error] Received incomplete redirect information.")
                    self.redirect_in_progress.set() 
                    self.is_connected = False
                    if self.sock: self.sock.close()
                    return

                # If the client is connecting from outside Docker (e.g., localhost),
                # it must override the server's advertised Docker hostname with one it can resolve.
                original_host = self.servers[self.current_server_index].host
                connect_to_host = leader_host
                if original_host in ('localhost', '127.0.0.1'):
                    connect_to_host = 'localhost'
                    print(f"\n[System] Redirected to leader {leader_id} ({leader_host}:{leader_port}). Connecting via {connect_to_host}:{leader_port}.")
                else:
                    print(f"\n[System] Redirected to leader at {leader_host}:{leader_port}")

                # Overwrite the server list to only contain the leader's address.
                self.servers = [ServerConfig(leader_id, connect_to_host, leader_port, 0, 0)]
                self.current_server_index = 0

                self.redirect_in_progress.set()
                self.is_connected = False
                if self.sock: self.sock.close()
                return # Don't print or show a prompt for redirects

            # The actual message printing logic for visible messages
            self._print_server_message(msg_type, payload)

            # Reprint the input prompt and the user's current text
            sys.stdout.write(self._get_prompt() + self._user_input_buffer)
            sys.stdout.flush()

    def _print_server_message(self, msg_type: str, payload: Any):
        """Handles the actual printing of the message content."""
        if msg_type == "ack" and payload.get("command") == "set_username":
            self.connection_acknowledged.set()
        elif msg_type == "room_joined":
            self.in_room = True
            self.current_room = payload.get("room_name")
            print(f"[System]: {payload.get('message')}")
            self.state_change_event.set()
        elif msg_type == "room_left":
            self.in_room = False
            self.current_room = None
            print(f"[System]: {payload.get('message')}")
            self.state_change_event.set()
        elif msg_type == "chat":
            sender = payload.get('sender_name', 'Unknown')
            print(f"[{self.current_room}] {sender}: {payload.get('message')}")
        elif msg_type == "room_list":
            print("Available rooms: " + (", ".join(payload) if payload else "None"))
        elif msg_type == "error":
            print(f"[Error]: {payload}")
        elif msg_type == "info":
            print(f"[Info]: {payload}")
        # Silently ignore other message types like 'pong'

    def send_command(self, command: str, payload: dict = None):
        """Send a command to the server."""
        if not self.sock:
             return

        try:
            message = {"command": command, "payload": payload or {}}
            self.sock.sendall(json.dumps(message).encode())
        except (socket.error, BrokenPipeError):
            self.is_connected = False
        
    def _handle_user_input(self):
        """Platform-agnostic non-blocking check for user input."""
        if _IS_WINDOWS:
            if msvcrt.kbhit():
                char = msvcrt.getwch() # No-echo version
                if char in ('\r', '\n'): # Enter key
                    sys.stdout.write('\n')
                    sys.stdout.flush()
                    self._process_input_buffer()
                elif char == '\x08': # Backspace
                    if self._user_input_buffer:
                        self._user_input_buffer = self._user_input_buffer[:-1]
                        # Redraw the line after backspace
                        line = self._get_prompt() + self._user_input_buffer
                        sys.stdout.write('\r' + ' ' * (len(line) + 20) + '\r') # Extra space to clear
                        sys.stdout.write(line)
                        sys.stdout.flush()
                else:
                    self._user_input_buffer += char
                    sys.stdout.write(char) # Echo manually
                    sys.stdout.flush()
        else:
            # Non-Windows implementation would go here
            # not in scope.
            self._blocking_input_loop()

    def _get_prompt(self) -> str:
        return f"[{self.current_room}]> " if self.in_room else "> "

    def _process_input_buffer(self):
        """Process the command from the input buffer."""
        user_input = self._user_input_buffer.strip()
        self._user_input_buffer = "" # Reset buffer

        if not user_input:
            sys.stdout.write(self._get_prompt())
            sys.stdout.flush()
            return
            
        if self.in_room:
            self._room_loop(user_input)
        else:
            self._main_loop(user_input)

    def _blocking_input_loop(self):
        """Fallback to blocking input for non-Windows systems."""
        try:
            prompt = self._get_prompt()
            user_input = input(prompt)
            if self.in_room:
                self._room_loop(user_input)
            else:
                self._main_loop(user_input)
        except (EOFError, KeyboardInterrupt):
            self.stop()
            
    def _main_loop(self, user_input: str):
        """Handle input when in the main menu (not in a room)."""
        parts = user_input.split(" ", 1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None
        
        if command == "create":
            if arg:
                self.state_change_event.clear()
                self.send_command("create_room", {"room_name": arg})
                if not self.state_change_event.wait(timeout=5.0):
                    print("[System] Server did not confirm room creation in time.")
            else:
                print("Usage: Create <room_name>")
        elif command == "join":
             if arg:
                self.state_change_event.clear()
                self.send_command("join_room", {"room_name": arg})
                if not self.state_change_event.wait(timeout=5.0):
                    print("[System] Server did not confirm room join in time.")
             else:
                print("Usage: Join <room_name>")
        elif command == "list":
            self.send_command("list_rooms")
        elif command == "help":
            self._print_help()
        elif command == "exit":
            self.stop()
        else:
            print(f"Unknown command: '{command}'. Type 'Help' for a list of commands.")
            sys.stdout.write(self._get_prompt())
            sys.stdout.flush()

    def _room_loop(self, user_input: str):
        """Handle input when inside a chat room."""
        # If the input starts with a known command, process it.
        # Otherwise, send the entire input as a chat message.
        parts = user_input.split(" ", 1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None
        
        if command == "leave":
            self.state_change_event.clear()
            self.send_command("leave_room")
            if not self.state_change_event.wait(timeout=5.0):
                print("[System] Server did not confirm leaving room in time.")
        elif command == "whereami":
            self.send_command("whereami")
        elif command == "help":
            self._print_help()
        elif command == "exit":
            self.stop()
        else:
            # Default action is to send a chat message
            self.send_command("chat", {"message": user_input})

    def _start_heartbeat(self):
        """Start the heartbeat thread."""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _heartbeat_loop(self):
        """Periodically send pings and check for server responsiveness."""
        HEARTBEAT_INTERVAL = 2.5 # seconds
        HEARTBEAT_TIMEOUT = 10.0 # seconds

        self.last_pong_time = time.time() # Initial timestamp

        while self.is_connected and self._running:
            # Check if the server is still alive
            if time.time() - self.last_pong_time > HEARTBEAT_TIMEOUT:
                print("\n[System] Heartbeat timeout. Connection lost.")
                self.is_connected = False # This will break the main loops
                # Close socket to interrupt any blocking calls like input()
                if self.sock:
                    self.sock.close()
                break # Exit the heartbeat loop

            # Send a ping
            self.send_command("ping")
            
            # Wait for the next interval
            time.sleep(HEARTBEAT_INTERVAL)

    def stop(self):
        """Stop the client gracefully."""
        print("\nExiting...")
        self._running = False
        if self.sock:
            # Shutdown the socket to unblock the receiver thread
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass # Socket might already be closed
            self.sock.close()
        
        # Wait briefly for the receiver thread to exit
        if self._receive_thread and self._receive_thread.is_alive():
            self._receive_thread.join(timeout=1.0)
            
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SyncNet v5 Chat Client")
    parser.add_argument("--host", help="Server host to connect to (overrides default config)")
    parser.add_argument("--port", type=int, help="Server port to connect to (overrides default config)")
    args = parser.parse_args()

    custom_servers = None
    if args.host and args.port:
        print(f"Attempting to connect to specified server: {args.host}:{args.port}")
        # Create a dummy ServerConfig for the custom server. The other fields aren't used by the client.
        custom_servers = [ServerConfig(server_id='custom', host=args.host, tcp_port=args.port, heartbeat_port=0, ring_position=0)]
    else:
        print("Starting client with default server list...")

    client = SyncNetClient(servers=custom_servers)
    try:
        client.start()
    except (KeyboardInterrupt, EOFError):
        client.stop()