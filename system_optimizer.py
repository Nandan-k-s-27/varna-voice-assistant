"""
VARNA v2.2 - System Optimization Mode
Background optimization commands for system management.

Commands:
  - "optimize system": Run full optimization
  - "kill memory hogs": Close high-memory processes
  - "clear temp files": Clean temporary files
  - "show top cpu apps": Display CPU-heavy processes
  - "show top memory apps": Display memory-heavy processes

This moves VARNA from assistant to system manager.
"""

import os
import shutil
import tempfile
from pathlib import Path
from dataclasses import dataclass
from utils.logger import get_logger

log = get_logger(__name__)

# Safe list of processes to never kill
_PROTECTED_PROCESSES = {
    "system", "svchost", "csrss", "wininit", "winlogon", "lsass",
    "services", "smss", "dwm", "explorer", "taskmgr", "cmd", "powershell",
    "python", "pythonw", "varna", "code", "vscode"
}

# Temp folder locations
_TEMP_FOLDERS = [
    Path(tempfile.gettempdir()),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Temp",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Temp",
]


@dataclass
class ProcessInfo:
    """Information about a running process."""
    name: str
    pid: int
    cpu_percent: float
    memory_mb: float
    
    def __str__(self) -> str:
        return f"{self.name}: CPU {self.cpu_percent:.1f}%, RAM {self.memory_mb:.0f}MB"


@dataclass
class OptimizationResult:
    """Result of optimization action."""
    success: bool
    message: str
    details: list[str] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = []


class SystemOptimizer:
    """
    System optimization and management utilities.
    
    Provides:
    - Process monitoring and management
    - Temp file cleanup
    - Memory optimization suggestions
    - System health checks
    """
    
    def __init__(self):
        """Initialize optimizer."""
        self._psutil_available = False
        try:
            import psutil
            self._psutil_available = True
        except ImportError:
            log.warning("psutil not available - optimization features limited")
        
        log.info("SystemOptimizer initialized (psutil=%s)", self._psutil_available)
    
    def get_top_cpu_processes(self, n: int = 5) -> list[ProcessInfo]:
        """Get top N CPU-consuming processes."""
        if not self._psutil_available:
            return []
        
        import psutil
        
        processes = []
        for proc in psutil.process_iter(['name', 'pid', 'cpu_percent', 'memory_info']):
            try:
                info = proc.info
                memory_mb = info['memory_info'].rss / (1024 * 1024) if info['memory_info'] else 0
                processes.append(ProcessInfo(
                    name=info['name'] or "Unknown",
                    pid=info['pid'],
                    cpu_percent=info['cpu_percent'] or 0,
                    memory_mb=memory_mb
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Sort by CPU
        processes.sort(key=lambda p: -p.cpu_percent)
        return processes[:n]
    
    def get_top_memory_processes(self, n: int = 5) -> list[ProcessInfo]:
        """Get top N memory-consuming processes."""
        if not self._psutil_available:
            return []
        
        import psutil
        
        processes = []
        for proc in psutil.process_iter(['name', 'pid', 'cpu_percent', 'memory_info']):
            try:
                info = proc.info
                memory_mb = info['memory_info'].rss / (1024 * 1024) if info['memory_info'] else 0
                processes.append(ProcessInfo(
                    name=info['name'] or "Unknown",
                    pid=info['pid'],
                    cpu_percent=info['cpu_percent'] or 0,
                    memory_mb=memory_mb
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Sort by memory
        processes.sort(key=lambda p: -p.memory_mb)
        return processes[:n]
    
    def get_memory_hogs(self, threshold_mb: float = 500) -> list[ProcessInfo]:
        """Get processes using more than threshold MB."""
        if not self._psutil_available:
            return []
        
        import psutil
        
        hogs = []
        for proc in psutil.process_iter(['name', 'pid', 'cpu_percent', 'memory_info']):
            try:
                info = proc.info
                memory_mb = info['memory_info'].rss / (1024 * 1024) if info['memory_info'] else 0
                
                # Skip protected and small processes
                if info['name'] and info['name'].lower() in _PROTECTED_PROCESSES:
                    continue
                
                if memory_mb >= threshold_mb:
                    hogs.append(ProcessInfo(
                        name=info['name'] or "Unknown",
                        pid=info['pid'],
                        cpu_percent=info['cpu_percent'] or 0,
                        memory_mb=memory_mb
                    ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        hogs.sort(key=lambda p: -p.memory_mb)
        return hogs
    
    def kill_process(self, name: str) -> OptimizationResult:
        """Kill a process by name (with protection check)."""
        if not self._psutil_available:
            return OptimizationResult(False, "psutil not available")
        
        import psutil
        
        name_lower = name.lower()
        
        # Check protection
        if name_lower in _PROTECTED_PROCESSES:
            return OptimizationResult(
                False, 
                f"Cannot kill protected process: {name}"
            )
        
        killed = []
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == name_lower:
                    proc.kill()
                    killed.append(str(proc.info['pid']))
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                log.debug("Cannot kill %s: %s", name, e)
        
        if killed:
            return OptimizationResult(
                True,
                f"Killed {len(killed)} {name} process(es)",
                killed
            )
        else:
            return OptimizationResult(False, f"No {name} process found")
    
    def clear_temp_files(self, older_than_days: int = 7) -> OptimizationResult:
        """
        Clear temporary files older than N days.
        
        Args:
            older_than_days: Only delete files older than this.
            
        Returns:
            OptimizationResult with details.
        """
        import time
        
        cutoff_time = time.time() - (older_than_days * 86400)
        deleted_count = 0
        freed_bytes = 0
        errors = []
        
        for temp_folder in _TEMP_FOLDERS:
            if not temp_folder.exists():
                continue
            
            try:
                for item in temp_folder.iterdir():
                    try:
                        stat = item.stat()
                        if stat.st_mtime < cutoff_time:
                            size = stat.st_size if item.is_file() else 0
                            
                            if item.is_file():
                                item.unlink()
                                deleted_count += 1
                                freed_bytes += size
                            elif item.is_dir():
                                shutil.rmtree(item, ignore_errors=True)
                                deleted_count += 1
                    except (PermissionError, OSError) as e:
                        errors.append(str(e))
            except PermissionError:
                errors.append(f"Cannot access {temp_folder}")
        
        freed_mb = freed_bytes / (1024 * 1024)
        
        return OptimizationResult(
            success=deleted_count > 0,
            message=f"Deleted {deleted_count} items, freed {freed_mb:.1f} MB",
            details=errors[:5] if errors else []
        )
    
    def get_system_health(self) -> dict:
        """Get system health summary."""
        if not self._psutil_available:
            return {"status": "limited", "message": "psutil not available"}
        
        import psutil
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.5)
        
        # Memory
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        mem_available_gb = mem.available / (1024 ** 3)
        
        # Disk
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_free_gb = disk.free / (1024 ** 3)
        
        # Status
        if cpu_percent > 90 or mem_percent > 90:
            status = "critical"
        elif cpu_percent > 70 or mem_percent > 70:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "cpu_percent": cpu_percent,
            "memory_percent": mem_percent,
            "memory_available_gb": round(mem_available_gb, 1),
            "disk_percent": disk_percent,
            "disk_free_gb": round(disk_free_gb, 1),
        }
    
    def suggest_optimizations(self) -> list[str]:
        """Get optimization suggestions based on current state."""
        suggestions = []
        
        health = self.get_system_health()
        
        if health.get("cpu_percent", 0) > 70:
            top_cpu = self.get_top_cpu_processes(3)
            if top_cpu:
                suggestions.append(
                    f"High CPU usage. Consider closing: {', '.join(p.name for p in top_cpu)}"
                )
        
        if health.get("memory_percent", 0) > 70:
            hogs = self.get_memory_hogs(500)
            if hogs:
                suggestions.append(
                    f"High memory usage. Memory hogs: {', '.join(p.name for p in hogs[:3])}"
                )
        
        if health.get("disk_free_gb", 100) < 10:
            suggestions.append("Low disk space. Consider clearing temp files.")
        
        if not suggestions:
            suggestions.append("System is running optimally.")
        
        return suggestions
    
    def run_full_optimization(self) -> OptimizationResult:
        """Run full system optimization."""
        results = []
        
        # 1. Clear temp files
        temp_result = self.clear_temp_files(older_than_days=7)
        results.append(f"Temp cleanup: {temp_result.message}")
        
        # 2. Get suggestions
        suggestions = self.suggest_optimizations()
        results.extend(suggestions)
        
        # 3. Health check
        health = self.get_system_health()
        results.append(f"System status: {health.get('status', 'unknown')}")
        
        return OptimizationResult(
            success=True,
            message="Optimization complete",
            details=results
        )


# Singleton
_optimizer: SystemOptimizer | None = None


def get_optimizer() -> SystemOptimizer:
    """Get or create the singleton optimizer."""
    global _optimizer
    if _optimizer is None:
        _optimizer = SystemOptimizer()
    return _optimizer
