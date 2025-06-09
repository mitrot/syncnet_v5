"""Network and timing constants - standardized for batch files"""

# Port offsets (matches existing batch files using 8000+ range)
PORT_OFFSETS = {
    'tcp_client': 0,        # 8000, 8001, 8002
    'server_discovery': 10,  # 8010, 8011, 8012
    'heartbeat': 20,        # 8020, 8021, 8022
    'election': 30,         # 8030, 8031, 8032
    'multicast_chat': 40    # 8040, 8041, 8042
}

# Timing configuration
TIMEOUTS = {
    'server_discovery': 3.0,
    'heartbeat_interval': 2.0,
    'leader_death_detection': 6.0,
    'election_timeout': 8.0,
    'tcp_connection': 3.0,
    'socket_timeout': 1.0
}

# Network constants
NETWORK_CONSTANTS = {
    'multicast_group': '239.0.0.1',
    'broadcast_address': '255.255.255.255',
    'buffer_size': 1024,
    'multicast_buffer_size': 10240,
    'multicast_ttl': 2,
    'max_connections': 100,
    'max_message_size': 4096
} 