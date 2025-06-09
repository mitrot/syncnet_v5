#!/usr/bin/env python3
"""SyncNet v5 Server Entry Point"""

import sys
import argparse
import logging
import signal
import time
import os

# Add parent directory for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.server import SyncNetServer
from common.config import DEFAULT_SERVER_CONFIGS

def setup_logging(log_level: str = 'INFO'):
    """Setup logging configuration"""
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatter without emojis for Windows compatibility
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # File handler
    file_handler = logging.FileHandler(f'logs/server_{int(time.time())}.log', mode='a', encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

def find_server_config(server_id: str):
    """Find server configuration by ID"""
    for config in DEFAULT_SERVER_CONFIGS:
        if config.server_id == server_id:
            return config
    return None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

def main():
    """Main server entry point"""
    parser = argparse.ArgumentParser(description='SyncNet v5 Distributed Server')
    parser.add_argument('--server-id', required=True, 
                       choices=['server1', 'server2', 'server3'],
                       help='Server identifier (server1, server2, or server3)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    parser.add_argument('--test-mode', action='store_true',
                       help='Run in test mode (auto-shutdown after 10 seconds)')
    
    args = parser.parse_args()
    
    # Setup logging
    os.makedirs('logs', exist_ok=True)
    setup_logging(args.log_level)
    
    logger = logging.getLogger('server.main')
    
    # Find server configuration
    config = find_server_config(args.server_id)
    if not config:
        logger.error(f"❌ Invalid server ID: {args.server_id}")
        sys.exit(1)
    
    logger.info(f"Starting SyncNet v5 Server: {args.server_id}")
    logger.info(f"Configuration: {config.host}:{config.tcp_port}")
    logger.info(f"Log Level: {args.log_level}")
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    server = None
    try:
        # Create and initialize server (pass server_id string, not config object)
        server = SyncNetServer(args.server_id)
        logger.info("Initializing server components...")
        
        # Start server
        logger.info("Starting server services...")
        server.start()
        
        logger.info(f"{args.server_id} is now running!")
        logger.info(f"TCP Port: {config.tcp_port}")
        logger.info(f"Heartbeat Port: {config.heartbeat_port}")
        logger.info(f"Election Port: {config.election_port}")
        logger.info("Server is ready to accept connections")
        
        if args.test_mode:
            logger.info("Test mode: Running for 10 seconds...")
            time.sleep(10)
            logger.info("Test mode complete, shutting down")
        else:
            # Keep server running
            logger.info("Server running... Press Ctrl+C to stop")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
    
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            import traceback
            logger.debug(traceback.format_exc())
        sys.exit(1)
    
    finally:
        if server:
            logger.info("Shutting down server...")
            try:
                server.stop()
                logger.info("Server shutdown complete")
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")

if __name__ == '__main__':
    main() 