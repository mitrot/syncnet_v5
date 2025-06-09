"""Server and network configuration classes"""
from dataclasses import dataclass
import socket

@dataclass
class ServerConfig:
    """Configuration for individual server"""
    server_id: str
    host: str
    base_port: int
    ring_position: int
    
    @property
    def tcp_port(self) -> int:
        return self.base_port
    
    @property 
    def discovery_port(self) -> int:
        return self.base_port + 10
        
    @property
    def heartbeat_port(self) -> int:
        return self.base_port + 20
        
    @property
    def election_port(self) -> int:
        return self.base_port + 30
        
    @property
    def multicast_port(self) -> int:
        return self.base_port + 40

@dataclass 
class NetworkConfig:
    """Network-wide configuration"""
    multicast_group: str = '239.0.0.1'
    broadcast_address: str = '255.255.255.255'
    buffer_size: int = 1024

@dataclass
class DatabaseConfig:
    """Database configuration"""
    db_path: str = 'syncnet.db'
    connection_timeout: int = 30 