import socket
import sys
import threading
import json
import time
import logging
import os

# Robustly add project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.config import DEFAULT_SERVER_CONFIGS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class SyncNetClient:
    """A command-line client for the SyncNet v5 chat system."""

    def __init__(self):
        self.sock: socket.socket = None
        self.is_connected = False
        self.current_server_index = 0
        self._receive_thread = None
        self._running = False
        self.in_room = False
        self.current_room = None
        self.prompt_lock = threading.Lock()
        self.state_change_event = threading.Event()

    def connect(self):
        """Attempt to connect to a server from the known list."""
        while not self.is_connected:
            server_config = DEFAULT_SERVER_CONFIGS[self.current_server_index]
            host, port = server_config.host, server_config.tcp_port
            try:
                logging.info(f"Attempting to connect to {server_config.server_id} at {host}:{port}...")
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(3.0) # Timeout for the connection attempt itself
                self.sock.connect((host, port))
                self.sock.settimeout(None) # Remove timeout for normal blocking operations
                
                self.is_connected = True
                self._running = True
                self._receive_thread = threading.Thread(target=self._receive_messages, daemon=True)
                self._receive_thread.start()
                logging.info(f"Successfully connected to {server_config.server_id}.")
            except (socket.timeout, ConnectionRefusedError) as e:
                logging.warning(f"Failed to connect to {server_config.server_id}: {e}")
                self.current_server_index = (self.current_server_index + 1) % len(DEFAULT_SERVER_CONFIGS)
                time.sleep(1) # Wait before trying the next server

    def _receive_messages(self):
        """Listen for incoming messages from the server."""
        while self._running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    logging.warning("Connection lost.")
                    self.is_connected = False
                    break
                
                message = json.loads(data.decode())
                self._handle_server_message(message)

            except (json.JSONDecodeError, UnicodeDecodeError):
                logging.warning("Received malformed message.")
            except Exception:
                logging.error("An error occurred while receiving messages.")
                self.is_connected = False
                break
        
        if self._running: # If the loop broke unexpectedly
            logging.info("Attempting to reconnect...")
            self.connect()

    def _handle_server_message(self, message: dict):
        """Process and display messages from the server."""
        msg_type = message.get("type")
        payload = message.get("payload")

        with self.prompt_lock:
            # Erase the current input line
            sys.stdout.write('\r' + ' ' * 60 + '\r')

            if msg_type == "redirect":
                leader_id = payload.get("leader_id")
                logging.info(f"Received redirect to leader: {leader_id}. Reconnecting...")
                # Find the index of the leader to connect next
                for i, config in enumerate(DEFAULT_SERVER_CONFIGS):
                    if config.server_id == leader_id:
                        self.current_server_index = i
                        break
                self.is_connected = False # Trigger reconnect in the receive loop
            elif msg_type == "room_joined":
                self.in_room = True
                self.current_room = payload.get("room_name")
                print(f"[System]: {payload.get('message')}")
                self.state_change_event.set() # Signal that state has changed
            elif msg_type == "room_left":
                self.in_room = False
                self.current_room = None
                print(f"[System]: {payload.get('message')}")
                self.state_change_event.set() # Signal that state has changed
            elif msg_type == "chat":
                sender = payload.get('sender', 'Unknown')
                # Shorten sender ID for display
                sender_short = sender.split(':')[1] if ':' in sender else sender
                print(f"[{self.current_room}] {sender_short}: {payload.get('message')}")
            elif msg_type == "room_list":
                print("Available rooms: " + (", ".join(payload) if payload else "None"))
            elif msg_type == "error":
                print(f"[Error]: {payload}")
            elif msg_type == "info":
                 print(f"[Info]: {payload}")
            else:
                print(f"[Server]: {payload}")
            
            # Reprint the input prompt
            if self.in_room:
                prompt = f"[{self.current_room}]> "
            else:
                prompt = "> "
            sys.stdout.write(prompt)
            sys.stdout.flush()

    def send_command(self, command: str, payload: dict = None):
        """Send a command to the server."""
        if not self.is_connected:
            logging.error("Not connected to any server.")
            return
        
        try:
            message = {"command": command, "payload": payload or {}}
            self.sock.sendall(json.dumps(message).encode())
        except Exception as e:
            logging.error(f"Failed to send command: {e}")
            self.is_connected = False

    def start(self):
        """Start the main client loop and manage menus."""
        self.connect()
        
        while self._running:
            if self.in_room:
                self.room_menu()
            else:
                self.main_menu()

    def main_menu(self):
        """Display and handle the main menu."""
        print("\n--- SyncNet Main Menu ---")
        print("Commands: Create <room>, Join <room>, List, Exit")
        
        try:
            user_input = input("> ").strip()
            if not user_input:
                return # Go back to start of the main while loop

            parts = user_input.split()
            command = parts[0].lower()
            
            if command == "create":
                if len(parts) > 1:
                    self.state_change_event.clear()
                    self.send_command("create_room", {"room_name": parts[1]})
                    self.state_change_event.wait(timeout=2.0) # Wait for confirmation
                else:
                    print("Usage: Create <room_name>")
            elif command == "join":
                 if len(parts) > 1:
                    self.state_change_event.clear()
                    self.send_command("join_room", {"room_name": parts[1]})
                    self.state_change_event.wait(timeout=2.0) # Wait for confirmation
                 else:
                    print("Usage: Join <room_name>")
            elif command == "list":
                self.send_command("list_rooms")
            elif command == "exit":
                self.stop()
            else:
                print("Unknown command. Available commands: Create, Join, List, Exit")

        except (KeyboardInterrupt, EOFError):
            self.stop()

    def room_menu(self):
        """Display and handle the in-room menu."""
        prompt = f"[{self.current_room}]> "
        try:
            user_input = input(prompt).strip()
            if not user_input:
                return

            parts = user_input.split(" ", 1)
            command = parts[0].lower()

            if command == "chat":
                if len(parts) > 1:
                    self.send_command("chat", {"message": parts[1]})
                else:
                    print("Usage: Chat <message>")
            elif command == "leave":
                self.state_change_event.clear()
                self.send_command("leave_room")
                self.state_change_event.wait(timeout=2.0) # Wait for confirmation
            elif command == "whereami":
                self.send_command("whereami")
            elif command == "exit":
                self.stop()
            else:
                print("Unknown command. Available commands: Chat <message>, Leave, WhereAmI, Exit")

        except (KeyboardInterrupt, EOFError):
            self.stop()

    def stop(self):
        """Stop the client gracefully."""
        print("\nExiting...")
        self._running = False
        if self.sock:
            self.sock.close()
        sys.exit(0)

if __name__ == "__main__":
    client = SyncNetClient()
    client.start() 