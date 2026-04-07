"""
Config Loader with Hot Reload
==============================

Loads a YAML agent config from disk, validates it against the Pydantic schema,
and watches the file for changes. When the file changes, it reloads silently
and the next request to the RAG server uses the new config.

Used by:
  - rag_server/app.py (loads config at startup, swaps on reload)
  - admin_ui/app.py   (loads + saves config from web form, Phase 2)

Usage:

    from shared.config_loader import ConfigLoader

    loader = ConfigLoader("config/nashat_sales.yaml")
    config = loader.config            # current AgentConfig
    loader.start_watching()           # begin hot reload
    # ... later ...
    config = loader.config            # always reflects the latest valid load
    loader.stop_watching()
"""
from __future__ import annotations
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Make config.schema importable when this module is imported from anywhere
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from config.schema import AgentConfig, validate_default_mode_exists


class ConfigLoadError(Exception):
    """Raised when a YAML file fails to parse or validate."""


def load_and_validate(path: str | Path) -> AgentConfig:
    """Load a YAML file from disk and return a validated AgentConfig.

    Raises ConfigLoadError with a clear message on any failure.
    """
    path = Path(path)
    if not path.exists():
        raise ConfigLoadError(f"Config file not found: {path}")

    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigLoadError(f"YAML parse error in {path}: {e}")

    if raw is None:
        raise ConfigLoadError(f"Config file is empty: {path}")

    try:
        config = AgentConfig(**raw)
        validate_default_mode_exists(config)
    except Exception as e:
        raise ConfigLoadError(f"Schema validation failed for {path}: {e}")

    return config


class _ReloadHandler(FileSystemEventHandler):
    """Triggers reload when the watched YAML file is modified."""

    def __init__(self, loader: "ConfigLoader"):
        self._loader = loader
        self._last_reload = 0.0
        self._debounce_seconds = 0.5

    def on_modified(self, event):
        if event.is_directory:
            return
        if Path(event.src_path).resolve() != self._loader.path.resolve():
            return
        # Debounce: editors often trigger multiple modify events per save
        now = time.time()
        if now - self._last_reload < self._debounce_seconds:
            return
        self._last_reload = now
        self._loader._reload()


class ConfigLoader:
    """Loads and watches a single agent YAML file.

    The .config attribute is always the most recent successfully validated
    config. If a reload fails (e.g., the user saved invalid YAML), the
    previous valid config is kept and an error is logged to stderr — the
    server keeps running with the last-known-good state.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self._lock = threading.Lock()
        self._config: AgentConfig = load_and_validate(self.path)
        self._observer: Optional[Observer] = None
        self._on_reload_callbacks: list = []

    @property
    def config(self) -> AgentConfig:
        with self._lock:
            return self._config

    def on_reload(self, callback) -> None:
        """Register a callback to fire after a successful reload.

        Callback receives the new AgentConfig as its only argument.
        Useful for the RAG server to refresh its system prompt cache.
        """
        self._on_reload_callbacks.append(callback)

    def _reload(self) -> None:
        try:
            new_config = load_and_validate(self.path)
        except ConfigLoadError as e:
            print(f"[config_loader] reload FAILED, keeping previous config: {e}",
                  file=sys.stderr)
            return

        with self._lock:
            self._config = new_config

        print(f"[config_loader] reloaded {self.path.name} OK",
              file=sys.stderr)

        for cb in self._on_reload_callbacks:
            try:
                cb(new_config)
            except Exception as e:
                print(f"[config_loader] reload callback error: {e}",
                      file=sys.stderr)

    def start_watching(self) -> None:
        if self._observer is not None:
            return
        self._observer = Observer()
        handler = _ReloadHandler(self)
        # Watch the parent directory because some editors write atomically
        # (delete + rename), which only fires events on the directory.
        self._observer.schedule(handler, str(self.path.parent), recursive=False)
        self._observer.start()
        print(f"[config_loader] watching {self.path} for changes",
              file=sys.stderr)

    def stop_watching(self) -> None:
        if self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=2.0)
        self._observer = None
