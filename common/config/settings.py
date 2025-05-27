"""Configuration settings for syncnet_v5"""

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
import json
import logging

@dataclass
class ServerConfig:
    """Server configuration"""
    host: str = 'localhost'
    port: int = 8888
    server_port: int = 8889  # Port for server-to-server communication
    max_clients: int = 1000
    max_rooms: int = 100
    max_room_size: int = 50
    message_size_limit: int = 4096
    heartbeat_interval: float = 1.0
    election_timeout: float = 5.0
    replication_timeout: float = 2.0
    log_level: str = 'INFO'
    log_file: Optional[str] = None

@dataclass
class ClientConfig:
    """Client configuration"""
    host: str = 'localhost'
    port: int = 8888
    reconnect_attempts: int = 3
    reconnect_delay: float = 1.0
    message_timeout: float = 5.0
    log_level: str = 'INFO'
    log_file: Optional[str] = None

@dataclass
class SecurityConfig:
    """Security configuration"""
    tls_enabled: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    ca_file: Optional[str] = None
    auth_required: bool = False
    auth_timeout: float = 30.0

@dataclass
class Config:
    """Main configuration"""
    server: ServerConfig
    client: ClientConfig
    security: SecurityConfig
    debug: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        """Create config from dictionary"""
        return cls(
            server=ServerConfig(**data.get('server', {})),
            client=ClientConfig(**data.get('client', {})),
            security=SecurityConfig(**data.get('security', {})),
            debug=data.get('debug', False)
        )
    
    @classmethod
    def from_file(cls, path: str) -> 'Config':
        """Load config from file"""
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            'server': self.server.__dict__,
            'client': self.client.__dict__,
            'security': self.security.__dict__,
            'debug': self.debug
        }
    
    def to_file(self, path: str):
        """Save config to file"""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=4)

def setup_logging(config: Config, component: str):
    """Setup logging for component
    
    Args:
        config: Configuration
        component: Component name ('server' or 'client')
    """
    if component == 'server':
        log_config = config.server
    else:
        log_config = config.client
        
    level = getattr(logging, log_config.log_level.upper())
    handlers = [logging.StreamHandler()]
    
    if log_config.log_file:
        handlers.append(logging.FileHandler(log_config.log_file))
        
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

# Default configuration
DEFAULT_CONFIG = Config(
    server=ServerConfig(),
    client=ClientConfig(),
    security=SecurityConfig()
)

# Environment variable prefix
ENV_PREFIX = 'SYNCNET_'

def load_config(config_file: Optional[str] = None) -> Config:
    """Load configuration from file and environment
    
    Args:
        config_file: Path to config file
        
    Returns:
        Config instance
    """
    # Start with default config
    config = DEFAULT_CONFIG
    
    # Load from file if specified
    if config_file and os.path.exists(config_file):
        config = Config.from_file(config_file)
    
    # Override with environment variables
    for key, value in os.environ.items():
        if key.startswith(ENV_PREFIX):
            # Convert SYNCNET_SERVER_PORT to server.port
            parts = key[len(ENV_PREFIX):].lower().split('_')
            if len(parts) >= 2:
                section = parts[0]
                option = '_'.join(parts[1:])
                
                # Convert value to appropriate type
                if section in ('server', 'client'):
                    if option in ('port', 'server_port', 'max_clients', 'max_rooms', 'max_room_size', 'message_size_limit'):
                        value = int(value)
                    elif option in ('heartbeat_interval', 'election_timeout', 'replication_timeout', 'reconnect_delay', 'message_timeout'):
                        value = float(value)
                elif section == 'security':
                    if option in ('tls_enabled', 'auth_required'):
                        value = value.lower() in ('true', '1', 'yes')
                    elif option == 'auth_timeout':
                        value = float(value)
                
                # Set the value
                if hasattr(config, section):
                    section_obj = getattr(config, section)
                    if hasattr(section_obj, option):
                        setattr(section_obj, option, value)
    
    return config 