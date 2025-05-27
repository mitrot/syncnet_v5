"""Error handling utilities for syncnet_v5"""

from typing import Optional, Type, Callable, Any
import logging
import traceback
from dataclasses import dataclass

@dataclass
class SyncNetError(Exception):
    """Base exception for syncnet_v5"""
    message: str
    code: str
    details: Optional[dict] = None
    
    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

class NetworkError(SyncNetError):
    """Network-related errors"""
    pass

class ProtocolError(SyncNetError):
    """Protocol-related errors"""
    pass

class AuthenticationError(SyncNetError):
    """Authentication-related errors"""
    pass

class RoomError(SyncNetError):
    """Room-related errors"""
    pass

class StateError(SyncNetError):
    """State-related errors"""
    pass

# Error codes
ERROR_CODES = {
    # Network errors (1000-1999)
    'CONNECTION_FAILED': '1000',
    'CONNECTION_TIMEOUT': '1001',
    'CONNECTION_CLOSED': '1002',
    'NETWORK_ERROR': '1003',
    
    # Protocol errors (2000-2999)
    'INVALID_MESSAGE': '2000',
    'INVALID_COMMAND': '2001',
    'MESSAGE_TOO_LARGE': '2002',
    'PROTOCOL_ERROR': '2003',
    
    # Authentication errors (3000-3999)
    'AUTH_FAILED': '3000',
    'INVALID_CREDENTIALS': '3001',
    'SESSION_EXPIRED': '3002',
    'ACCESS_DENIED': '3003',
    
    # Room errors (4000-4999)
    'ROOM_NOT_FOUND': '4000',
    'ROOM_EXISTS': '4001',
    'ROOM_FULL': '4002',
    'NOT_IN_ROOM': '4003',
    
    # State errors (5000-5999)
    'STATE_ERROR': '5000',
    'CONSISTENCY_ERROR': '5001',
    'REPLICATION_ERROR': '5002',
    'LEADER_ERROR': '5003'
}

def create_error(
    code: str,
    message: str,
    details: Optional[dict] = None,
    error_type: Type[SyncNetError] = SyncNetError
) -> SyncNetError:
    """Create a syncnet error
    
    Args:
        code: Error code from ERROR_CODES
        message: Error message
        details: Additional error details
        error_type: Type of error to create
        
    Returns:
        SyncNetError instance
    """
    if code not in ERROR_CODES:
        code = 'PROTOCOL_ERROR'
    return error_type(
        message=message,
        code=ERROR_CODES[code],
        details=details
    )

def handle_error(
    error: Exception,
    logger: Optional[logging.Logger] = None,
    reraise: bool = True
) -> Optional[SyncNetError]:
    """Handle an exception
    
    Args:
        error: Exception to handle
        logger: Logger to use
        reraise: Whether to reraise the error
        
    Returns:
        SyncNetError if error was converted, None otherwise
        
    Raises:
        SyncNetError if reraise is True
    """
    if isinstance(error, SyncNetError):
        if logger:
            logger.error(str(error), extra=error.details or {})
        if reraise:
            raise error
        return error
    
    # Convert to SyncNetError
    if isinstance(error, ConnectionError):
        syncnet_error = create_error(
            'CONNECTION_FAILED',
            str(error),
            {'original_error': type(error).__name__},
            NetworkError
        )
    elif isinstance(error, TimeoutError):
        syncnet_error = create_error(
            'CONNECTION_TIMEOUT',
            str(error),
            {'original_error': type(error).__name__},
            NetworkError
        )
    else:
        syncnet_error = create_error(
            'PROTOCOL_ERROR',
            str(error),
            {
                'original_error': type(error).__name__,
                'traceback': traceback.format_exc()
            },
            ProtocolError
        )
    
    if logger:
        logger.error(str(syncnet_error), extra=syncnet_error.details or {})
    
    if reraise:
        raise syncnet_error
    return syncnet_error

def error_handler(
    logger: Optional[logging.Logger] = None,
    reraise: bool = True
) -> Callable:
    """Decorator for error handling
    
    Args:
        logger: Logger to use
        reraise: Whether to reraise errors
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                handle_error(e, logger, reraise)
        return wrapper
    return decorator 