from collections import namedtuple

NETWORK_CONSTANTS = {
    'buffer_size': 4096,
    'max_connections': 10
}

TIMEOUTS = {
    'heartbeat_interval': 2.5,
    'leader_death_detection': 8.0, 
    'election_timeout': 5.0 
}

ServerConfig = namedtuple('ServerConfig', ['server_id', 'host', 'tcp_port', 'heartbeat_port', 'ring_position'])

DEFAULT_SERVER_CONFIGS = [
    ServerConfig('server1', '127.0.0.1', 8000, 8020, 10),
    ServerConfig('server2', '127.0.0.1', 8001, 8021, 20),
    ServerConfig('server3', '127.0.0.1', 8002, 8022, 30),
] 