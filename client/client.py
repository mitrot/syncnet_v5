import argparse
import json
import os
import random
import socket
import sys
import threading
import time
from typing import Any, List, Optional

# Add project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.config import DEFAULT_SERVER_CONFIGS, ServerConfig

# Platform-specific imports for non-blocking input
try:
    import msvcrt
    _IS_WINDOWS = True
except ImportError:
    import termios
    import tty
    import select
    _IS_WINDOWS = False

class SyncNetClient:
    """A command-line client for the SyncNet v5 chat system."""

    def __init__(self, servers: Optional[List[ServerConfig]] = None, connect_via_localhost: bool = False):
        self.sock: Optional[socket.socket] = None
        self.username: str = "Anonymous"
        self.is_connected = False
        self.connect_via_localhost = connect_via_localhost
        self.initial_servers = self._get_default_servers(connect_via_localhost)
        self.servers = servers or list(self.initial_servers)
        self.current_server_index = 0
        self._receive_thread: Optional[threading.Thread] = None
        self._running = False
        self.in_room = False
        self.current_room: Optional[str] = None
        self.state_change_event = threading.Event()
        self.connection_acknowledged = threading.Event()
        self.redirect_in_progress = threading.Event()
        self.last_pong_time = 0
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._user_input_buffer = ""
        self._original_termios = None # For non-Windows terminal settings

    def _get_default_servers(self, use_localhost: bool) -> List[ServerConfig]:
        """Returns the list of servers, overriding with 'localhost' for local Docker setups."""
        if not use_localhost:
            return DEFAULT_SERVER_CONFIGS
        return [ServerConfig(c.server_id, 'localhost', c.tcp_port, c.heartbeat_port, c.ring_position)
                for c in DEFAULT_SERVER_CONFIGS]

    def _print_help(self):
        """Prints available commands based on state."""
        if self.in_room:
            print("\n--- SyncNet Room Menu ---\nCommands: Chat <message>, Leave, WhereAmI, Help, Exit")
        else:
            print("\n--- SyncNet Main Menu ---\nCommands: Create <room>, Join <room>, List, Help, Exit")

    def _get_prompt(self) -> str:
        """Returns the appropriate command prompt."""
        return f"[{self.current_room}]> " if self.in_room else "> "

    def _setup_terminal(self):
        """Set up the terminal for non-blocking, character-by-character input."""
        if not _IS_WINDOWS:
            self._original_termios = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())

    def _restore_terminal(self):
        """Restore the terminal to its original state."""
        if not _IS_WINDOWS and self._original_termios:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._original_termios)

    def start(self):
        """Start the client, setting up the terminal and managing the main loop."""
        try:
            self._setup_terminal()
            self._running = True
            self.username = self._get_username_from_input()
            if not self.username: return # User exited during prompt

            while self._running:
                self.connect()
                
                if self.is_connected:
                    print(f"\n[System] Welcome! You are connected as '{self.username}'.")
                    self._print_help()
                    sys.stdout.write(self._get_prompt())
                    sys.stdout.flush()
                    self._start_heartbeat()
                
                while self.is_connected and self._running:
                    self._handle_user_input()
                    time.sleep(0.05) # Small sleep to prevent busy-waiting
                
                if self._running and not self.is_connected:
                    print("\n[System] Connection lost. Will attempt to reconnect...")
                    time.sleep(1)
        finally:
            self._restore_terminal()

    def _get_username_from_input(self) -> Optional[str]:
        """Prompt for and return a username using non-blocking input."""
        sys.stdout.write("Please enter your name: ")
        sys.stdout.flush()
        
        while self._running:
            char_bytes = self._get_char()
            if not char_bytes:
                time.sleep(0.01)
                continue
            
            char = char_bytes.decode(errors='ignore')
            
            if char in ('\r', '\n'):
                sys.stdout.write('\n')
                username = self._user_input_buffer.strip() or "Anonymous"
                self._user_input_buffer = ""
                return username
            elif char in ('\x08', '\x7f'): # Backspace
                if self._user_input_buffer:
                    self._user_input_buffer = self._user_input_buffer[:-1]
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            elif char == '\x03': # Ctrl+C
                self.stop()
                return None
            elif char.isprintable():
                self._user_input_buffer += char
                sys.stdout.write(char)
                sys.stdout.flush()
        return None

    def _get_char(self) -> Optional[bytes]:
        """Get a single character from stdin without blocking."""
        if _IS_WINDOWS:
            if msvcrt.kbhit():
                return msvcrt.getch()
        else:
            if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                return sys.stdin.read(1).encode()
        return None

    def _handle_user_input(self):
        """Process a single character of user input."""
        char_bytes = self._get_char()
        if not char_bytes:
            return

        with threading.Lock(): # Protect against race conditions with server messages
            char = char_bytes.decode(errors='ignore')

            if char in ('\r', '\n'):
                sys.stdout.write('\n')
                self._process_command(self._user_input_buffer)
                self._user_input_buffer = ""
                sys.stdout.write(self._get_prompt())
                sys.stdout.flush()
            elif char in ('\x08', '\x7f'): # Backspace
                if self._user_input_buffer:
                    self._user_input_buffer = self._user_input_buffer[:-1]
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            elif char == '\x03': # Ctrl+C
                self.stop()
            elif char.isprintable():
                self._user_input_buffer += char
                sys.stdout.write(char)
                sys.stdout.flush()

    def _process_command(self, user_input: str):
        """Wrapper for routing commands."""
        self._process_input(user_input.strip())

    def connect(self):
        """Loop until a connection to the leader is established."""
        is_retrying = False
        while not self.is_connected and self._running:
            if is_retrying:
                time.sleep(2)
            
            server_config = self.servers[self.current_server_index]
            host, port = server_config.host, server_config.tcp_port
            try:
                if self.sock:
                    self.sock.close()
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(3.0)
                self.sock.connect((host, port))
                self.sock.settimeout(None)
                
                self.connection_acknowledged.clear()
                self.redirect_in_progress.clear()
                
                if self._receive_thread is None or not self._receive_thread.is_alive():
                    self._receive_thread = threading.Thread(target=self._receive_messages, daemon=True)
                    self._receive_thread.start()

                self.send_command("set_username", {"username": self.username})
                self.connection_acknowledged.wait(timeout=5.0) 

                if self.redirect_in_progress.is_set():
                    continue
                
                if not self.connection_acknowledged.is_set():
                    self.sock.close() 
                    self.current_server_index = (self.current_server_index + 1) % len(self.servers)
                else:
                    self.is_connected = True

            except (socket.timeout, ConnectionRefusedError, OSError):
                if len(self.servers) == 1:
                    print("\n[System] Connection to leader failed. Searching for a new leader...")
                    self.servers = list(self.initial_servers)
                    self.current_server_index = random.randint(0, len(self.servers) - 1)
                else:
                    self.current_server_index = (self.current_server_index + 1) % len(self.servers)
            
            is_retrying = True

    def _receive_messages(self):
        """Listen for and process incoming messages from the server."""
        while self._running:
            try:
                if not self.sock: break
                self.sock.settimeout(1.0) 
                data = self.sock.recv(4096)
                if not data: break
                
                self._handle_server_message(json.loads(data.decode()))

            except socket.timeout:
                continue
            except (socket.error, ConnectionResetError, BrokenPipeError, json.JSONDecodeError):
                break
        
        self.is_connected = False
        self.in_room = False
        self.current_room = None

    def _handle_server_message(self, message: dict):
        """Process a single message from the server and display it."""
        with threading.Lock():
            msg_type = message.get("type")
            payload = message.get("payload")

            if msg_type == "pong":
                self.last_pong_time = time.time()
                return
            if msg_type == "ack" and payload.get("command") == "set_username":
                self.connection_acknowledged.set()
                return
            
            # Special handling for messages that unblock the main thread's state change event
            if msg_type in ("room_joined", "room_left"):
                sys.stdout.write('\r' + (' ' * (len(self._get_prompt()) + len(self._user_input_buffer))) + '\r')

                if msg_type == "room_joined":
                    self.in_room = True
                    self.current_room = payload.get("room_name")
                    print(f"[System]: {payload.get('message')}")
                elif msg_type == "room_left":
                    self.in_room = False
                    self.current_room = None
                    print(f"[System]: {payload.get('message')}")

                self.state_change_event.set()
                return

            # Clear the current input line before printing the message
            sys.stdout.write('\r' + (' ' * (len(self._get_prompt()) + len(self._user_input_buffer))) + '\r')

            # --- Print the actual message content ---
            if msg_type == "redirect":
                leader_host, leader_port, leader_id = payload.get("leader_host"), payload.get("leader_port"), payload.get("leader_id")
                if not (leader_host and leader_port and leader_id):
                    print(f"[Error] Received incomplete redirect information.")
                else:
                    connect_to_host = 'localhost' if self.connect_via_localhost else leader_host
                    print(f"[System] This is a follower. Redirecting to leader {leader_id} at {connect_to_host}:{leader_port}")
                    self.servers = [ServerConfig(leader_id, connect_to_host, leader_port, 0, 0)]
                    self.current_server_index = 0
                    self.redirect_in_progress.set()
                    if self.sock: self.sock.close()
            
            elif msg_type == "chat":
                sender = payload.get('sender_name', 'Unknown')
                print(f"[{self.current_room}] {sender}: {payload.get('message')}")
            elif msg_type == "room_list":
                print("Available rooms: " + (", ".join(payload) if payload else "None"))
            elif msg_type == "error":
                print(f"[Error]: {payload}")
            elif msg_type == "info":
                print(f"[Info]: {payload}")
            
            # Restore the prompt and user's current input
            sys.stdout.write(self._get_prompt() + self._user_input_buffer)
            sys.stdout.flush()

    def send_command(self, command: str, payload: dict = None):
        """Send a JSON-formatted command to the server."""
        if not self.sock: return
        try:
            message = {"command": command, "payload": payload or {}}
            self.sock.sendall(json.dumps(message).encode())
        except (socket.error, BrokenPipeError):
            self.is_connected = False

    def _process_input(self, user_input: str):
        """Parse user input and route to the correct handler."""
        if not user_input:
            return

        parts = user_input.split(" ", 1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None

        if command == "help":
            self._print_help()
        elif command == "exit":
            self.stop()
        elif command == "whereami":
            self.send_command("whereami")
        elif self.in_room:
            self._room_loop(command, user_input)
        else:
            self._main_loop(command, arg)

    def _main_loop(self, command: str, arg: Optional[str]):
        """Handle commands when in the main menu (not in a room)."""
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
        else:
            print(f"Unknown command: '{command}'. Type 'Help' for a list of commands.")

    def _room_loop(self, command: str, original_input: str):
        """Handle commands when inside a chat room."""
        if command == "leave":
            self.state_change_event.clear()
            self.send_command("leave_room")
            if not self.state_change_event.wait(timeout=5.0):
                print("[System] Server did not confirm leaving room in time.")
        else:
            self.send_command("chat", {"message": original_input})

    def _start_heartbeat(self):
        """Start the heartbeat thread."""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _heartbeat_loop(self):
        """Periodically send pings and check for server responsiveness."""
        HEARTBEAT_INTERVAL = 1.5
        HEARTBEAT_TIMEOUT = 4.0
        self.last_pong_time = time.time()
        while self.is_connected and self._running:
            if time.time() - self.last_pong_time > HEARTBEAT_TIMEOUT:
                print("\n[System] Heartbeat timeout. Connection lost.")
                self.is_connected = False
                if self.sock: self.sock.close()
                break
            
            # Check if the socket is still valid before sending
            if self.sock:
                self.send_command("ping")
                
            time.sleep(HEARTBEAT_INTERVAL)

    def stop(self):
        """Gracefully stop the client."""
        if not self._running: return
        print("\nExiting...")
        self._running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()
        # No need to join threads, they are daemons and will exit.
        
def main():
    """Parse arguments and start the client."""
    parser = argparse.ArgumentParser(
        description="SyncNet v5 Chat Client",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--host", help="Server host to connect to (e.g., 192.168.1.101).")
    parser.add_argument("--port", type=int, help="Server port to connect to (e.g., 8000).")
    
    args = parser.parse_args()

    custom_servers = None
    is_localhost = False
    if args.host and args.port:
        print(f"Attempting to connect to specified server: {args.host}:{args.port}")
        custom_servers = [ServerConfig('custom', args.host, args.port, 0, 0)]
        if args.host in ('localhost', '127.0.0.1'):
            is_localhost = True
    else:
        print("No host specified. Connecting to default servers via localhost.")
        is_localhost = True

    client = SyncNetClient(servers=custom_servers, connect_via_localhost=is_localhost)
    try:
        client.start()
    except KeyboardInterrupt:
        # The stop() method handles the graceful shutdown.
        client.stop()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        # In case of a crash, try to restore terminal settings.
        # This is a fallback and might not always work depending on the crash.
        if not _IS_WINDOWS:
            try:
                import termios, tty
                original_termios = termios.tcgetattr(sys.stdin)
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_termios)
            except Exception as e_term:
                print(f"Could not restore terminal settings: {e_term}")
        print("Client shut down.")