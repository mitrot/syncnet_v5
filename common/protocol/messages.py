"""Message protocol definitions for syncnet_v5"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import json

class MessageType(Enum):
    """Types of messages that can be exchanged"""
    # Client commands
    CREATE_ROOM = "create_room"
    JOIN_ROOM = "join_room"
    LEAVE_ROOM = "leave_room"
    LIST_ROOMS = "list_rooms"
    SEND_MESSAGE = "send_message"
    EXIT = "exit"
    
    # Server responses
    RESPONSE = "response"
    ERROR = "error"
    ROOM_LIST = "room_list"
    ROOM_MESSAGE = "room_message"
    SYSTEM_MESSAGE = "system_message"
    
    # Server-to-server messages
    HEARTBEAT = "heartbeat"
    VOTE_REQUEST = "vote_request"
    VOTE_RESPONSE = "vote_response"
    STATE_UPDATE = "state_update"
    STATE_SYNC = "state_sync"

@dataclass
class Message:
    """Base message class"""
    type: MessageType
    payload: Dict[str, Any]
    timestamp: float
    sender: Optional[str] = None
    room: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert message to JSON string"""
        return json.dumps({
            'type': self.type.value,
            'payload': self.payload,
            'timestamp': self.timestamp,
            'sender': self.sender,
            'room': self.room
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Create message from JSON string"""
        data = json.loads(json_str)
        return cls(
            type=MessageType(data['type']),
            payload=data['payload'],
            timestamp=data['timestamp'],
            sender=data.get('sender'),
            room=data.get('room')
        )

@dataclass
class ClientCommand(Message):
    """Client command message"""
    def __init__(self, command: str, args: List[str], **kwargs):
        super().__init__(
            type=MessageType(command),
            payload={'args': args},
            **kwargs
        )

@dataclass
class ServerResponse(Message):
    """Server response message"""
    def __init__(self, success: bool, message: str, data: Optional[Dict] = None, **kwargs):
        super().__init__(
            type=MessageType.RESPONSE,
            payload={
                'success': success,
                'message': message,
                'data': data or {}
            },
            **kwargs
        )

@dataclass
class RoomMessage(Message):
    """Chat room message"""
    def __init__(self, content: str, **kwargs):
        super().__init__(
            type=MessageType.ROOM_MESSAGE,
            payload={'content': content},
            **kwargs
        )

@dataclass
class SystemMessage(Message):
    """System notification message"""
    def __init__(self, content: str, level: str = "info", **kwargs):
        super().__init__(
            type=MessageType.SYSTEM_MESSAGE,
            payload={
                'content': content,
                'level': level
            },
            **kwargs
        ) 