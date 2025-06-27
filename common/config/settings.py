"""Server and network configuration classes."""
from dataclasses import dataclass

@dataclass
class ServerConfig:
    """Configuration for a single SyncNet server."""
    server_id: str
    host: str
    base_port: int
    ring_position: int

    @property
    def tcp_port(self) -> int:
        """The port for client-facing TCP connections."""
        return self.base_port

    @property
    def heartbeat_port(self) -> int:
        """The port for all inter-server UDP communication."""
        # This is offset by 20 from the base port.
        return self.base_port + 20 