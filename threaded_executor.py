"""
VARNA v2.2 - Threaded Execution Layer
Non-blocking command execution with parallel TTS preparation.

Architecture:
  STT → NLP → dispatch to executor thread
                     ↓
              TTS queue thread

This removes perceived lag by parallelizing execution and feedback.
"""

import threading
import queue
import time
from dataclasses import dataclass
from typing import Callable, Any
from enum import Enum, auto
from utils.logger import get_logger

log = get_logger(__name__)


class ExecutionPriority(Enum):
    """Execution priority levels."""
    HIGH = auto()      # System commands, confirmations
    NORMAL = auto()    # Regular commands
    LOW = auto()       # Background tasks


@dataclass
class ExecutionTask:
    """A task to be executed."""
    handler: Callable
    args: tuple = ()
    kwargs: dict = None
    priority: ExecutionPriority = ExecutionPriority.NORMAL
    callback: Callable | None = None   # Called on completion
    error_callback: Callable | None = None  # Called on error
    tts_message: str | None = None     # TTS to prepare in parallel
    
    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


@dataclass
class ExecutionResult:
    """Result of task execution."""
    success: bool
    result: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0


class ThreadedExecutor:
    """
    Non-blocking command executor with worker threads.
    
    Features:
      - Command execution in worker thread
      - TTS preparation in parallel
      - Priority queue for urgent commands
      - Callback support for completion/error
    """
    
    def __init__(self, max_workers: int = 2):
        """
        Initialize the executor.
        
        Args:
            max_workers: Number of worker threads.
        """
        self._task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._workers: list[threading.Thread] = []
        self._running = False
        self._max_workers = max_workers
        
        # Statistics
        self._stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_time_ms": 0.0
        }
        self._stats_lock = threading.Lock()
        
        # TTS preparation queue
        self._tts_queue: queue.Queue = queue.Queue()
        self._tts_worker: threading.Thread | None = None
        self._tts_callback: Callable | None = None
        
        log.info("ThreadedExecutor initialized with %d workers", max_workers)
    
    def start(self) -> None:
        """Start worker threads."""
        if self._running:
            return
        
        self._running = True
        
        # Start execution workers
        for i in range(self._max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"ExecutorWorker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)
        
        # Start TTS preparation worker
        self._tts_worker = threading.Thread(
            target=self._tts_worker_loop,
            name="TTSPrepWorker",
            daemon=True
        )
        self._tts_worker.start()
        
        log.info("ThreadedExecutor started")
    
    def stop(self) -> None:
        """Stop worker threads."""
        self._running = False
        
        # Send stop signals
        for _ in self._workers:
            self._task_queue.put((0, None))  # Sentinel
        
        self._tts_queue.put(None)  # Sentinel for TTS
        
        # Wait for workers to finish
        for worker in self._workers:
            worker.join(timeout=1.0)
        
        if self._tts_worker:
            self._tts_worker.join(timeout=1.0)
        
        self._workers.clear()
        log.info("ThreadedExecutor stopped")
    
    def submit(self, task: ExecutionTask) -> None:
        """
        Submit a task for execution.
        
        Args:
            task: ExecutionTask to execute.
        """
        with self._stats_lock:
            self._stats["total_tasks"] += 1
        
        # Priority value (lower = higher priority)
        priority_value = task.priority.value
        
        # Queue the task
        self._task_queue.put((priority_value, task))
        
        # Queue TTS preparation if provided
        if task.tts_message and self._tts_callback:
            self._tts_queue.put(task.tts_message)
        
        log.debug("Task submitted: %s (priority=%s)", 
                 task.handler.__name__, task.priority.name)
    
    def execute_sync(self, handler: Callable, *args, **kwargs) -> ExecutionResult:
        """
        Execute a task synchronously (blocking).
        
        For cases where we need the result immediately.
        """
        start_time = time.perf_counter()
        
        try:
            result = handler(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            with self._stats_lock:
                self._stats["completed_tasks"] += 1
                self._stats["total_time_ms"] += elapsed_ms
            
            return ExecutionResult(
                success=True,
                result=result,
                execution_time_ms=elapsed_ms
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            with self._stats_lock:
                self._stats["failed_tasks"] += 1
            
            log.error("Execution error: %s", e)
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=elapsed_ms
            )
    
    def set_tts_callback(self, callback: Callable) -> None:
        """Set callback for TTS preparation."""
        self._tts_callback = callback
    
    def _worker_loop(self) -> None:
        """Worker thread main loop."""
        while self._running:
            try:
                _, task = self._task_queue.get(timeout=0.5)
                
                if task is None:  # Sentinel
                    break
                
                # Execute the task
                start_time = time.perf_counter()
                
                try:
                    result = task.handler(*task.args, **task.kwargs)
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    
                    with self._stats_lock:
                        self._stats["completed_tasks"] += 1
                        self._stats["total_time_ms"] += elapsed_ms
                    
                    # Call success callback
                    if task.callback:
                        try:
                            task.callback(ExecutionResult(
                                success=True,
                                result=result,
                                execution_time_ms=elapsed_ms
                            ))
                        except Exception as e:
                            log.error("Callback error: %s", e)
                    
                except Exception as e:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    
                    with self._stats_lock:
                        self._stats["failed_tasks"] += 1
                    
                    log.error("Task execution error: %s", e)
                    
                    # Call error callback
                    if task.error_callback:
                        try:
                            task.error_callback(ExecutionResult(
                                success=False,
                                error=str(e),
                                execution_time_ms=elapsed_ms
                            ))
                        except Exception as cb_e:
                            log.error("Error callback error: %s", cb_e)
                
                finally:
                    self._task_queue.task_done()
                    
            except queue.Empty:
                continue
            except Exception as e:
                log.error("Worker loop error: %s", e)
    
    def _tts_worker_loop(self) -> None:
        """TTS preparation worker loop."""
        while self._running:
            try:
                message = self._tts_queue.get(timeout=0.5)
                
                if message is None:  # Sentinel
                    break
                
                # Prepare TTS (call the callback)
                if self._tts_callback:
                    try:
                        self._tts_callback(message)
                    except Exception as e:
                        log.error("TTS prep error: %s", e)
                
                self._tts_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                log.error("TTS worker error: %s", e)
    
    def get_stats(self) -> dict:
        """Get execution statistics."""
        with self._stats_lock:
            stats = dict(self._stats)
            if stats["completed_tasks"] > 0:
                stats["avg_time_ms"] = stats["total_time_ms"] / stats["completed_tasks"]
            else:
                stats["avg_time_ms"] = 0.0
            return stats
    
    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self._task_queue.qsize()


# Singleton
_executor: ThreadedExecutor | None = None


def get_executor() -> ThreadedExecutor:
    """Get or create the singleton executor instance."""
    global _executor
    if _executor is None:
        _executor = ThreadedExecutor()
        _executor.start()
    return _executor


def shutdown_executor() -> None:
    """Shutdown the executor."""
    global _executor
    if _executor:
        _executor.stop()
        _executor = None
