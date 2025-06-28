"""SyncNet v5 Server Entry Point"""

import sys
import argparse
import logging
import signal
import time
import os
import traceback

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from server.server import SyncNetServer, ServerState
from common.config import DEFAULT_SERVER_CONFIGS

# Global server instance for signal handling
_server_instance = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _server_instance
    if _server_instance:
        print(f"\n Signal {signum} received, shutting down gracefully...")
        _server_instance.stop()

def main():
    """Main server entry point."""
    global _server_instance

    parser = argparse.ArgumentParser(description="SyncNet v5 Server")
    parser.add_argument('--server-id', type=str, required=True, help='The ID of the server to start (e.g., server1)')
    parser.add_argument('--log-level', type=str, default='INFO', help='Set the logging level (e.g., DEBUG, INFO, WARNING)')
    args = parser.parse_args()

    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = os.path.join(log_dir, f"{args.server_id}.log")
    
    # Use the root logger for configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, args.log_level.upper(), logging.INFO))
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # File handler
    fh = logging.FileHandler(log_file, mode='w') # Overwrite log on each start
    fh.setFormatter(formatter)
    root_logger.addHandler(fh)
    
    # Stream handler (console)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    root_logger.addHandler(sh)
    
    main_logger = logging.getLogger('main')
    
    
    _server_instance = SyncNetServer(args.server_id)
    
    try:
        if _server_instance.start():
            main_logger.info(f"SyncNet server {args.server_id} is running! Press Ctrl+C to stop.")
            
            # Keep main thread alive while server is running
            while _server_instance.state == 'running':
                time.sleep(1)
        else:
            main_logger.error(f"Failed to start server {args.server_id}")
            sys.exit(1)
            
    except Exception as e:
        main_logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if _server_instance and _server_instance.state != 'stopped':
            _server_instance.stop()
        main_logger.info("Main function finished.")
    
    sys.exit(0)

if __name__ == '__main__':
    main() 