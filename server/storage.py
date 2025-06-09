"""Database storage operations for SyncNet v5"""
import sqlite3
import threading
import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from contextlib import contextmanager
import os

from common.config import DatabaseConfig
from common.messages import Message, MessageType

@dataclass
class StoredMessage:
    """Represents a stored message with metadata"""
    id: int
    sender_id: str
    message_type: str
    content: str
    lamport_timestamp: int
    created_at: float
    server_id: str

class MessageStorage:
    """Thread-safe SQLite storage for messages and server state"""
    
    def __init__(self, config_or_server_id = None):
        """Initialize storage with either DatabaseConfig or server_id string"""
        if isinstance(config_or_server_id, str):
            # Create config from server_id
            server_id = config_or_server_id
            self.config = DatabaseConfig(
                db_path=f"data/{server_id}.db"
            )
        elif isinstance(config_or_server_id, DatabaseConfig):
            # Use provided config
            self.config = config_or_server_id
        else:
            # Use default config
            self.config = DatabaseConfig()
        
        self.db_path = self.config.db_path
        self.connection_timeout = self.config.connection_timeout
        self._lock = threading.RLock()
        self.logger = logging.getLogger(f'storage.{self.db_path}')
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize database
        self._initialize_database()
        
    def initialize(self):
        """Public method to initialize storage (called by server)"""
        # Database is already initialized in __init__, but this provides a consistent API
        self.logger.info("Storage initialization confirmed")
    
    def _initialize_database(self):
        """Create database tables if they don't exist"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    lamport_timestamp INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    server_id TEXT NOT NULL
                )
            ''')
            
            # Create indexes separately
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_lamport ON messages(lamport_timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id)')
            
            # Server state table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS server_state (
                    server_id TEXT PRIMARY KEY,
                    is_leader BOOLEAN NOT NULL DEFAULT 0,
                    last_heartbeat REAL,
                    ring_position INTEGER,
                    status TEXT DEFAULT 'active',
                    updated_at REAL NOT NULL
                )
            ''')
            
            # Election history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS election_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    election_id TEXT NOT NULL,
                    winner_id TEXT NOT NULL,
                    participants TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    completed_at REAL
                )
            ''')
            
            # Create index for election history
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_election_started ON election_history(started_at)')
            
            conn.commit()
            self.logger.info("Database initialized successfully")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling"""
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_path, 
                timeout=self.connection_timeout,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            self.logger.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def store_message(self, message_or_sender_id, content=None, 
                     message_type: str = "chat", 
                     lamport_timestamp: int = 0,
                     server_id: str = "unknown") -> int:
        """Store a message in the database - accepts Message object or individual parameters"""
        from common.messages import Message
        
        if isinstance(message_or_sender_id, Message):
            # Handle Message object
            message = message_or_sender_id
            sender_id = message.sender_id
            content = message.data.get('content', '') if isinstance(message.data, dict) else str(message.data)
            message_type = message.msg_type.value if hasattr(message.msg_type, 'value') else str(message.msg_type)
            lamport_timestamp = message.lamport_timestamp
            server_id = message.sender_id  # Use sender_id from message
        else:
            # Handle individual parameters
            sender_id = message_or_sender_id
        
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO messages 
                    (sender_id, message_type, content, lamport_timestamp, created_at, server_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (sender_id, message_type, content, lamport_timestamp, time.time(), server_id))
                
                message_id = cursor.lastrowid
                conn.commit()
                
                self.logger.debug(f"Stored message {message_id} from {sender_id}")
                return message_id
    
    def get_recent_messages(self, limit: int = 50) -> List[StoredMessage]:
        """Get recent messages ordered by timestamp"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, sender_id, message_type, content, 
                       lamport_timestamp, created_at, server_id
                FROM messages 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            
            messages = []
            for row in cursor.fetchall():
                messages.append(StoredMessage(
                    id=row['id'],
                    sender_id=row['sender_id'],
                    message_type=row['message_type'],
                    content=row['content'],
                    lamport_timestamp=row['lamport_timestamp'],
                    created_at=row['created_at'],
                    server_id=row['server_id']
                ))
            
            return messages
    
    def get_messages_since(self, timestamp: float) -> List[StoredMessage]:
        """Get messages since a specific timestamp"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, sender_id, message_type, content, 
                       lamport_timestamp, created_at, server_id
                FROM messages 
                WHERE created_at > ?
                ORDER BY created_at ASC
            ''', (timestamp,))
            
            messages = []
            for row in cursor.fetchall():
                messages.append(StoredMessage(
                    id=row['id'],
                    sender_id=row['sender_id'],
                    message_type=row['message_type'],
                    content=row['content'],
                    lamport_timestamp=row['lamport_timestamp'],
                    created_at=row['created_at'],
                    server_id=row['server_id']
                ))
            
            return messages
    
    def update_server_state(self, server_id: str, is_leader: bool = False,
                           last_heartbeat: float = None, 
                           ring_position: int = None,
                           status: str = 'active'):
        """Update server state information"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Use current time if heartbeat not provided
                if last_heartbeat is None:
                    last_heartbeat = time.time()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO server_state 
                    (server_id, is_leader, last_heartbeat, ring_position, status, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (server_id, is_leader, last_heartbeat, ring_position, status, time.time()))
                
                conn.commit()
                self.logger.debug(f"Updated server state for {server_id}")
    
    def get_server_states(self) -> List[Dict[str, Any]]:
        """Get all server states"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT server_id, is_leader, last_heartbeat, ring_position, status, updated_at
                FROM server_state
                ORDER BY ring_position
            ''')
            
            states = []
            for row in cursor.fetchall():
                states.append({
                    'server_id': row['server_id'],
                    'is_leader': bool(row['is_leader']),
                    'last_heartbeat': row['last_heartbeat'],
                    'ring_position': row['ring_position'],
                    'status': row['status'],
                    'updated_at': row['updated_at']
                })
            
            return states
    
    def record_election(self, election_id: str, winner_id: str, 
                       participants: List[str], started_at: float,
                       completed_at: float = None):
        """Record election results"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO election_history 
                    (election_id, winner_id, participants, started_at, completed_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (election_id, winner_id, ','.join(participants), started_at, completed_at))
                
                conn.commit()
                self.logger.info(f"Recorded election {election_id}, winner: {winner_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Message count
            cursor.execute('SELECT COUNT(*) FROM messages')
            message_count = cursor.fetchone()[0]
            
            # Server count
            cursor.execute('SELECT COUNT(*) FROM server_state')
            server_count = cursor.fetchone()[0]
            
            # Election count
            cursor.execute('SELECT COUNT(*) FROM election_history')
            election_count = cursor.fetchone()[0]
            
            # Database file size
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            return {
                'db_path': self.db_path,
                'message_count': message_count,
                'server_count': server_count,
                'election_count': election_count,
                'db_size_bytes': db_size,
                'db_size_mb': round(db_size / (1024 * 1024), 2)
            }
    
    def get_message_count(self) -> int:
        """Get total number of stored messages"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM messages')
            return cursor.fetchone()[0]
    
    def cleanup_old_messages(self, days_old: int = 30):
        """Remove messages older than specified days"""
        cutoff_time = time.time() - (days_old * 24 * 60 * 60)
        
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM messages WHERE created_at < ?', (cutoff_time,))
                deleted_count = cursor.rowcount
                conn.commit()
                
                self.logger.info(f"Cleaned up {deleted_count} old messages")
                return deleted_count
    
    def close(self):
        """Close database connections (cleanup)"""
        self.logger.info("Storage closed")
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close() 