#!/usr/bin/env python3
"""SyncNet v5 Server Entry Point"""

import sys
import argparse
import logging
import signal
import time
import os
import traceback

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.server import SyncNetServer
from common.config import DEFAULT_SERVER_CONFIGS

# Global server instance for signal handling
_server_instance: SyncNetServer = None

def setup_logging(log_level: str = 'INFO', server_id: str = 'main'):
    """Setup logging configuration."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"{server_id}_{int(time.time())}.log")
    
    # Use a formatter that is compatible with more terminals
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File Handler
    try:
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Error setting up file logger: {e}")

def shutdown_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _server_instance
    print(f"\n🛑 Signal {signum} received, shutting down gracefully...")
    if _server_instance:
        _server_instance.stop()
    sys.exit(0)

def main():
    """Main server entry point."""
    global _server_instance

    parser = argparse.ArgumentParser(description='SyncNet v5 Distributed Server')
    parser.add_argument('--server-id', required=True, 
                       choices=[c.server_id for c in DEFAULT_SERVER_CONFIGS],
                       help='Server identifier')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    
    args = parser.parse_args()
    
    setup_logging(args.log_level, args.server_id)
    logger = logging.getLogger('main')
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    try:
        logger.info(f"Starting SyncNet v5 Server: {args.server_id}")
        _server_instance = SyncNetServer(args.server_id)
        _server_instance.start()
        
        # Keep main thread alive while server is running or starting
        while _server_instance and _server_instance.state in ["starting", "running"]:
            time.sleep(1)
            
    except Exception as e:
        logger.error(f"Server startup failed: {e}\n{traceback.format_exc()}")
        sys.exit(1)
    
    finally:
        if _server_instance and _server_instance.state != "stopped":
            logger.info("Main loop finished, ensuring server shutdown.")
            _server_instance.stop()

if __name__ == '__main__':
    main() 