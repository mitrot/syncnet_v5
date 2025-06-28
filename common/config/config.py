from collections import namedtuple
import random

NETWORK_CONSTANTS = {
    'buffer_size': 4096,
    'max_connections': 10
}

TIMEOUTS = {
    'heartbeat_interval': 2.0,
    'leader_death_detection': 10.0, 
    'election_timeout': random.uniform(7, 10)
}

ServerConfig = namedtuple('ServerConfig', ['server_id', 'host', 'tcp_port', 'heartbeat_port', 'ring_position'])

DEFAULT_SERVER_CONFIGS = [
    # Using the IP address of your machine.
    # Other clients and servers on your network can connect to this IP.
    ServerConfig(server_id='server1', host='192.168.1.179', tcp_port=8000, heartbeat_port=8020, ring_position=1),
    ServerConfig(server_id='server2', host='192.168.1.179', tcp_port=8001, heartbeat_port=8021, ring_position=2),
    ServerConfig(server_id='server3', host='192.168.1.179', tcp_port=8002, heartbeat_port=8022, ring_position=3),
    # The architecture supports scaling beyond 3 servers by simply adding them here.
    #ServerConfig(server_id='server4', host='192.168.1.179', tcp_port=8003, heartbeat_port=8023, ring_position=4),
    #ServerConfig(server_id='server5', host='192.168.1.179', tcp_port=8004, heartbeat_port=8024, ring_position=5),
] 