"""Message protocol for SyncNet v5"""
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any
import json
import time

class MessageType(Enum):
    """All message types"""
    # Server-to-server
    HEARTBEAT = "heartbeat"
    ELECTION = "election"
    SERVER_DISCOVERY = "server_discovery"
    DATA_REPLICATION = "data_replication"
    
    # Client-to-server
    CREATE_JOIN = "create_join"
    CHAT = "chat"
    LEAVE = "leave"
    CLIENT_DISCOVERY = "client_discovery"
    
    # Responses
    ACK = "ack"
    NACK = "nack"
    SERVER_LIST = "server_list"

@dataclass
class LamportClock:
    """Lamport logical clock"""
    timestamp: int = 0
    
    def tick(self) -> int:
        self.timestamp += 1
        return self.timestamp
        
    def update(self, received_timestamp: int) -> int:
        self.timestamp = max(self.timestamp, received_timestamp) + 1
        return self.timestamp

@dataclass
class Message:
    """Base message structure"""
    msg_type: MessageType
    sender_id: str
    data: Dict[str, Any]
    lamport_timestamp: int = 0
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
    
    def to_json(self) -> str:
        return json.dumps({
            'msg_type': self.msg_type.value,
            'sender_id': self.sender_id,
            'data': self.data,
            'lamport_timestamp': self.lamport_timestamp,
            'created_at': self.created_at
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        data = json.loads(json_str)
        return cls(
            msg_type=MessageType(data['msg_type']),
            sender_id=data['sender_id'],
            data=data['data'],
            lamport_timestamp=data['lamport_timestamp'],
            created_at=data['created_at']
        )
