"""
Configuration package for SyncNet.

This package centralizes all static configuration for the server,
including network constants, timeouts, and server definitions.
"""
from .config import ServerConfig, DEFAULT_SERVER_CONFIGS, TIMEOUTS, NETWORK_CONSTANTS

__all__ = [
    'ServerConfig',
    'DEFAULT_SERVER_CONFIGS',
    'TIMEOUTS',
    'NETWORK_CONSTANTS'
]
