"""Constants used throughout syncnet_v5"""

# Network constants
DEFAULT_BUFFER_SIZE = 4096
DEFAULT_TIMEOUT = 30.0
MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
MAX_USERNAME_LENGTH = 32
MAX_ROOM_NAME_LENGTH = 64
MAX_MESSAGE_LENGTH = 1024

# Protocol constants
PROTOCOL_VERSION = "1.0"
MAGIC_BYTES = b"SYNC"  # Magic bytes to identify syncnet protocol
HEADER_SIZE = 8  # Size of message header in bytes

# Room constants
DEFAULT_ROOM = "general"
SYSTEM_ROOM = "system"  # Room for system messages
MAX_ROOMS_PER_USER = 10
MAX_MESSAGES_PER_ROOM = 1000  # Maximum number of messages to keep in room history

# Server constants
MAX_SERVERS = 5  # Maximum number of servers in the cluster
MIN_SERVERS = 3  # Minimum number of servers for quorum
LEADER_TIMEOUT = 5.0  # Timeout for leader election
REPLICATION_TIMEOUT = 2.0  # Timeout for replication operations
HEARTBEAT_INTERVAL = 1.0  # Interval between heartbeats

# Client constants
RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 1.0
MESSAGE_TIMEOUT = 5.0
PING_INTERVAL = 30.0  # Interval between client pings

# Security constants
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
TOKEN_EXPIRY = 24 * 60 * 60  # Token expiry in seconds (24 hours)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_TIMEOUT = 300  # Timeout for login attempts in seconds (5 minutes)

# Error codes
class ErrorCode:
    """Error codes used in the system"""
    # Network errors (1000-1999)
    NETWORK_ERROR = 1000
    CONNECTION_ERROR = 1001
    TIMEOUT_ERROR = 1002
    PROTOCOL_ERROR = 1003
    
    # Authentication errors (2000-2999)
    AUTH_ERROR = 2000
    INVALID_CREDENTIALS = 2001
    TOKEN_EXPIRED = 2002
    INSUFFICIENT_PERMISSIONS = 2003
    
    # Room errors (3000-3999)
    ROOM_ERROR = 3000
    ROOM_NOT_FOUND = 3001
    ROOM_FULL = 3002
    ROOM_EXISTS = 3003
    ROOM_PERMISSION_DENIED = 3004
    
    # Message errors (4000-4999)
    MESSAGE_ERROR = 4000
    MESSAGE_TOO_LARGE = 4001
    INVALID_MESSAGE = 4002
    
    # Server errors (5000-5999)
    SERVER_ERROR = 5000
    LEADER_ERROR = 5001
    REPLICATION_ERROR = 5002
    QUORUM_ERROR = 5003
    
    # Client errors (6000-6999)
    CLIENT_ERROR = 6000
    INVALID_COMMAND = 6001
    RATE_LIMIT_EXCEEDED = 6002
    
    # System errors (9000-9999)
    SYSTEM_ERROR = 9000
    CONFIG_ERROR = 9001
    DATABASE_ERROR = 9002

# Message types
class MessageType:
    """Message types used in the system"""
    # Client commands (1-99)
    CREATE_ROOM = 1
    JOIN_ROOM = 2
    LEAVE_ROOM = 3
    SEND_MESSAGE = 4
    GET_ROOMS = 5
    GET_USERS = 6
    GET_HISTORY = 7
    LOGIN = 8
    LOGOUT = 9
    
    # Server responses (100-199)
    RESPONSE = 100
    ERROR = 101
    ROOM_CREATED = 102
    ROOM_JOINED = 103
    ROOM_LEFT = 104
    MESSAGE_SENT = 105
    ROOM_LIST = 106
    USER_LIST = 107
    MESSAGE_HISTORY = 108
    LOGIN_SUCCESS = 109
    LOGOUT_SUCCESS = 110
    
    # Server-to-server messages (200-299)
    HEARTBEAT = 200
    VOTE_REQUEST = 201
    VOTE_RESPONSE = 202
    REPLICATION_REQUEST = 203
    REPLICATION_RESPONSE = 204
    STATE_SYNC = 205
    
    # System messages (300-399)
    SYSTEM_MESSAGE = 300
    USER_JOINED = 301
    USER_LEFT = 302
    ROOM_DELETED = 303
    SERVER_SHUTDOWN = 304
    MAINTENANCE_MODE = 305

# User roles
class UserRole:
    """User roles in the system"""
    GUEST = 0
    USER = 1
    MODERATOR = 2
    ADMIN = 3
    SYSTEM = 4

# Room types
class RoomType:
    """Room types in the system"""
    PUBLIC = 0
    PRIVATE = 1
    SYSTEM = 2
    DIRECT = 3  # Direct message room

# Message status
class MessageStatus:
    """Message status in the system"""
    PENDING = 0
    DELIVERED = 1
    READ = 2
    FAILED = 3
    DELETED = 4

# Server states
class ServerState:
    """Server states in the cluster"""
    FOLLOWER = 0
    CANDIDATE = 1
    LEADER = 2
    SHUTDOWN = 3
    MAINTENANCE = 4 