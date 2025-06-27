"""Configuration module for SyncNet v5"""
from .settings import ServerConfig
from .constants import TIMEOUTS, NETWORK_CONSTANTS

# This fixes: cannot import name 'DEFAULT_SERVER_CONFIGS'
DEFAULT_SERVER_CONFIGS = [
    ServerConfig(
        server_id='server1',
        host='localhost',
        base_port=8000,
        ring_position=0
    ),
    ServerConfig(
        server_id='server2', 
        host='localhost',
        base_port=8001,
        ring_position=1
    ),
    ServerConfig(
        server_id='server3',
        host='localhost', 
        base_port=8002,
        ring_position=2
    )
]

__all__ = [
    'ServerConfig',
    'DEFAULT_SERVER_CONFIGS',
    'TIMEOUTS',
    'NETWORK_CONSTANTS'
]
