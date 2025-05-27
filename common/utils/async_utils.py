"""Async utility functions for syncnet_v5"""

import asyncio
from typing import Any, Callable, Optional, TypeVar, Awaitable
import time
import logging

T = TypeVar('T')

async def with_timeout(coro: Awaitable[T], timeout: float) -> Optional[T]:
    """Execute coroutine with timeout
    
    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds
        
    Returns:
        Result of coroutine or None if timeout
    """
    try:
        return await asyncio.wait_for(coro, timeout)
    except asyncio.TimeoutError:
        return None

async def retry_async(
    func: Callable[..., Awaitable[T]],
    *args,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    **kwargs
) -> T:
    """Retry async function with exponential backoff
    
    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_retries: Maximum number of retries
        delay: Initial delay between retries
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of func
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                await asyncio.sleep(current_delay)
                current_delay *= backoff
            else:
                raise last_exception

class AsyncTimer:
    """Async timer for periodic tasks"""
    
    def __init__(self, interval: float, callback: Callable[[], Awaitable[None]]):
        self.interval = interval
        self.callback = callback
        self.task: Optional[asyncio.Task] = None
        self._stop = False
        
    async def _run(self):
        """Run the timer"""
        while not self._stop:
            try:
                await self.callback()
            except Exception as e:
                logging.error(f"Timer callback error: {e}")
            await asyncio.sleep(self.interval)
            
    def start(self):
        """Start the timer"""
        if self.task is None:
            self._stop = False
            self.task = asyncio.create_task(self._run())
            
    def stop(self):
        """Stop the timer"""
        if self.task is not None:
            self._stop = True
            self.task.cancel()
            self.task = None

class AsyncLock:
    """Async lock with timeout"""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._acquired = False
        
    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire lock with optional timeout
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            True if lock acquired, False if timeout
        """
        try:
            if timeout is None:
                await self._lock.acquire()
            else:
                await asyncio.wait_for(self._lock.acquire(), timeout)
            self._acquired = True
            return True
        except asyncio.TimeoutError:
            return False
        
    def release(self):
        """Release lock"""
        if self._acquired:
            self._lock.release()
            self._acquired = False
            
    async def __aenter__(self):
        """Async context manager entry"""
        await self.acquire()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        self.release() 