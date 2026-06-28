"""
FORGE File Watcher — Watches project directory for changes.
Uses watchdog to monitor filesystem events and emit callbacks.
"""

import os
import time
import threading
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, \
        FileCreatedEvent, FileDeletedEvent, FileMovedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


class ForgeFileHandler:
    """
    Handles filesystem events for FORGE project directories.
    Filters out .forge/, __pycache__/, .git/ and other noise.
    """

    IGNORE_DIRS = {".forge", "__pycache__", ".git", ".venv", "venv",
                   "node_modules", ".pytest_cache", "__MACOSX", ".mypy_cache"}
    IGNORE_EXTENSIONS = {".pyc", ".pyo", ".swp", ".swo", ".tmp", ".bak",
                         ".db-journal", ".db-wal"}

    def __init__(self, callback=None):
        """
        Args:
            callback: Function(event_type, filepath) called on file changes.
                      event_type: 'modified' | 'created' | 'deleted' | 'moved'
        """
        self.callback = callback
        self._debounce_timers = {}
        self._lock = threading.Lock()

    def should_ignore(self, path: str) -> bool:
        """Check if a path should be ignored."""
        parts = Path(path).parts
        for part in parts:
            if part in self.IGNORE_DIRS:
                return True
        
        _, ext = os.path.splitext(path)
        if ext.lower() in self.IGNORE_EXTENSIONS:
            return True
        
        return False

    def _debounced_emit(self, event_type: str, filepath: str):
        """Debounce rapid events for the same file (100ms window)."""
        key = f"{event_type}:{filepath}"
        
        with self._lock:
            if key in self._debounce_timers:
                self._debounce_timers[key].cancel()
            
            timer = threading.Timer(0.1, self._emit, args=(event_type, filepath))
            self._debounce_timers[key] = timer
            timer.start()

    def _emit(self, event_type: str, filepath: str):
        """Emit a file change event."""
        with self._lock:
            key = f"{event_type}:{filepath}"
            self._debounce_timers.pop(key, None)
        
        if self.callback:
            try:
                self.callback(event_type, filepath)
            except Exception:
                pass  # Don't crash on callback errors


if HAS_WATCHDOG:
    class _WatchdogHandler(FileSystemEventHandler):
        """Watchdog event handler that delegates to ForgeFileHandler."""

        def __init__(self, forge_handler: ForgeFileHandler):
            super().__init__()
            self.forge_handler = forge_handler

        def on_modified(self, event):
            if event.is_directory:
                return
            if not self.forge_handler.should_ignore(event.src_path):
                self.forge_handler._debounced_emit("modified", event.src_path)

        def on_created(self, event):
            if event.is_directory:
                return
            if not self.forge_handler.should_ignore(event.src_path):
                self.forge_handler._debounced_emit("created", event.src_path)

        def on_deleted(self, event):
            if event.is_directory:
                return
            if not self.forge_handler.should_ignore(event.src_path):
                self.forge_handler._debounced_emit("deleted", event.src_path)

        def on_moved(self, event):
            if event.is_directory:
                return
            if not self.forge_handler.should_ignore(event.dest_path):
                self.forge_handler._debounced_emit("moved", event.dest_path)


class FileWatcher:
    """
    Watches a project directory for file changes.
    Uses watchdog for efficient OS-level monitoring.
    Falls back to polling if watchdog is unavailable.
    """

    def __init__(self, project_path: str, callback=None):
        """
        Args:
            project_path: Root directory to watch.
            callback: Function(event_type, filepath) called on changes.
        """
        self.project_path = project_path
        self.handler = ForgeFileHandler(callback=callback)
        self._observer = None
        self._running = False
        self._poll_thread = None

    def start(self):
        """Start watching for file changes."""
        if self._running:
            return

        self._running = True

        if HAS_WATCHDOG:
            self._observer = Observer()
            watchdog_handler = _WatchdogHandler(self.handler)
            self._observer.schedule(watchdog_handler, self.project_path, 
                                    recursive=True)
            self._observer.daemon = True
            self._observer.start()
        else:
            # Fallback: simple polling
            self._poll_thread = threading.Thread(
                target=self._poll_loop, daemon=True
            )
            self._poll_thread.start()

    def stop(self):
        """Stop watching."""
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    def _poll_loop(self):
        """Fallback polling loop when watchdog is unavailable."""
        last_state = self._scan_dir()
        while self._running:
            time.sleep(2.0)  # Poll every 2 seconds
            current_state = self._scan_dir()
            
            # Detect changes
            for path, mtime in current_state.items():
                if path not in last_state:
                    self.handler._debounced_emit("created", path)
                elif mtime != last_state[path]:
                    self.handler._debounced_emit("modified", path)
            
            for path in last_state:
                if path not in current_state:
                    self.handler._debounced_emit("deleted", path)
            
            last_state = current_state

    def _scan_dir(self) -> dict[str, float]:
        """Scan directory and return {filepath: mtime} mapping."""
        state = {}
        try:
            for root, dirs, files in os.walk(self.project_path):
                # Prune ignored directories
                dirs[:] = [d for d in dirs 
                          if d not in ForgeFileHandler.IGNORE_DIRS]
                for f in files:
                    path = os.path.join(root, f)
                    if not self.handler.should_ignore(path):
                        try:
                            state[path] = os.path.getmtime(path)
                        except OSError:
                            pass
        except OSError:
            pass
        return state

    def get_project_tree(self) -> list[dict]:
        """
        Get the project file tree as a nested structure.
        Returns list of {name, path, is_dir, children} dicts.
        """
        return self._build_tree(self.project_path)

    def _build_tree(self, directory: str) -> list[dict]:
        """Recursively build a file tree."""
        entries = []
        try:
            items = sorted(os.listdir(directory))
        except OSError:
            return entries

        for item in items:
            if item in ForgeFileHandler.IGNORE_DIRS:
                continue
            
            full_path = os.path.join(directory, item)
            rel_path = os.path.relpath(full_path, self.project_path)
            
            if os.path.isdir(full_path):
                children = self._build_tree(full_path)
                entries.append({
                    "name": item,
                    "path": rel_path,
                    "is_dir": True,
                    "children": children,
                })
            else:
                _, ext = os.path.splitext(item)
                if ext.lower() not in ForgeFileHandler.IGNORE_EXTENSIONS:
                    entries.append({
                        "name": item,
                        "path": rel_path,
                        "is_dir": False,
                        "children": [],
                    })

        return entries

    @property
    def is_running(self) -> bool:
        return self._running
