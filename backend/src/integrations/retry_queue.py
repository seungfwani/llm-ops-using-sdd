"""Retry queue mechanism for failed tool operations.

Provides retry logic for failed open-source tool operations with exponential backoff.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RetryStatus(Enum):
    """Retry queue item status."""
    PENDING = "pending"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RetryQueueItem:
    """Item in the retry queue."""
    operation_id: str
    operation: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    max_retries: int = 3
    retry_count: int = 0
    status: RetryStatus = RetryStatus.PENDING
    next_retry_at: Optional[datetime] = None
    last_error: Optional[Exception] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_next_retry(self, base_delay_seconds: int = 60) -> datetime:
        """Calculate next retry time with exponential backoff.
        
        Args:
            base_delay_seconds: Base delay in seconds
        
        Returns:
            Next retry datetime
        """
        delay = base_delay_seconds * (2 ** self.retry_count)
        return datetime.utcnow() + timedelta(seconds=delay)
    
    def can_retry(self) -> bool:
        """Check if item can be retried.
        
        Returns:
            True if retries remaining and not cancelled
        """
        return (
            self.status != RetryStatus.CANCELLED
            and self.retry_count < self.max_retries
            and self.status != RetryStatus.SUCCEEDED
        )


class RetryQueue:
    """Queue for retrying failed tool operations."""
    
    def __init__(self, base_delay_seconds: int = 60, max_queue_size: int = 1000):
        """Initialize retry queue.
        
        Args:
            base_delay_seconds: Base delay for exponential backoff
            max_queue_size: Maximum number of items in queue
        """
        self.base_delay_seconds = base_delay_seconds
        self.max_queue_size = max_queue_size
        self._queue: Dict[str, RetryQueueItem] = {}
        self._lock = asyncio.Lock()
        self._running = False
    
    async def add(
        self,
        operation_id: str,
        operation: Callable,
        *args,
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> RetryQueueItem:
        """Add an operation to the retry queue.
        
        Args:
            operation_id: Unique identifier for the operation
            operation: Callable to retry
            *args: Positional arguments for operation
            max_retries: Maximum number of retry attempts
            metadata: Optional metadata dictionary
            **kwargs: Keyword arguments for operation
        
        Returns:
            RetryQueueItem
        
        Raises:
            ValueError: If queue is full
        """
        async with self._lock:
            if len(self._queue) >= self.max_queue_size:
                raise ValueError(f"Retry queue is full (max {self.max_queue_size})")
            
            item = RetryQueueItem(
                operation_id=operation_id,
                operation=operation,
                args=args,
                kwargs=kwargs,
                max_retries=max_retries,
                metadata=metadata or {},
            )
            item.next_retry_at = item.calculate_next_retry(self.base_delay_seconds)
            self._queue[operation_id] = item
            
            logger.info(f"Added operation {operation_id} to retry queue")
            return item
    
    async def remove(self, operation_id: str) -> Optional[RetryQueueItem]:
        """Remove an item from the queue.
        
        Args:
            operation_id: Operation identifier
        
        Returns:
            Removed item or None if not found
        """
        async with self._lock:
            return self._queue.pop(operation_id, None)
    
    async def get_pending_items(self) -> list[RetryQueueItem]:
        """Get items ready for retry.
        
        Returns:
            List of items that are ready to retry
        """
        async with self._lock:
            now = datetime.utcnow()
            return [
                item
                for item in self._queue.values()
                if item.can_retry()
                and item.status == RetryStatus.PENDING
                and item.next_retry_at
                and item.next_retry_at <= now
            ]
    
    async def retry_item(self, item: RetryQueueItem) -> bool:
        """Retry a queue item.
        
        Args:
            item: Queue item to retry
        
        Returns:
            True if operation succeeded, False otherwise
        """
        item.status = RetryStatus.RETRYING
        item.retry_count += 1
        
        try:
            # Execute the operation
            if asyncio.iscoroutinefunction(item.operation):
                result = await item.operation(*item.args, **item.kwargs)
            else:
                result = item.operation(*item.args, **item.kwargs)
            
            item.status = RetryStatus.SUCCEEDED
            item.last_error = None
            logger.info(f"Operation {item.operation_id} succeeded after {item.retry_count} retries")
            return True
        
        except Exception as e:
            item.last_error = e
            logger.warning(f"Operation {item.operation_id} failed (attempt {item.retry_count}/{item.max_retries}): {e}")
            
            if item.can_retry():
                item.status = RetryStatus.PENDING
                item.next_retry_at = item.calculate_next_retry(self.base_delay_seconds)
            else:
                item.status = RetryStatus.FAILED
                logger.error(f"Operation {item.operation_id} failed permanently after {item.retry_count} retries")
            
            return False
    
    async def start_worker(self, check_interval_seconds: int = 30):
        """Start background worker to process retry queue.
        
        Args:
            check_interval_seconds: Interval between queue checks
        """
        self._running = True
        logger.info("Retry queue worker started")
        
        while self._running:
            try:
                pending_items = await self.get_pending_items()
                for item in pending_items:
                    await self.retry_item(item)
                
                await asyncio.sleep(check_interval_seconds)
            except Exception as e:
                logger.exception(f"Error in retry queue worker: {e}")
                await asyncio.sleep(check_interval_seconds)
    
    def stop_worker(self):
        """Stop the background worker."""
        self._running = False
        logger.info("Retry queue worker stopped")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get queue status.
        
        Returns:
            Dictionary with queue statistics
        """
        async with self._lock:
            status_counts = {}
            for status in RetryStatus:
                status_counts[status.value] = sum(
                    1 for item in self._queue.values() if item.status == status
                )
            
            return {
                "total_items": len(self._queue),
                "status_counts": status_counts,
                "max_queue_size": self.max_queue_size,
            }

