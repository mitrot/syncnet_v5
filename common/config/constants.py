"""Network and timing constants for SyncNet v5"""

# Timing configuration in seconds
TIMEOUTS = {
    'heartbeat_interval': 2.0,
    'leader_death_detection': 5.0,  # Time without heartbeat to be considered failed
    'election_timeout': 5.0,      # Cooldown between elections
    'socket_timeout': 1.0
}

# Network constants
NETWORK_CONSTANTS = {
    'buffer_size': 4096,
    'max_connections': 100
} 