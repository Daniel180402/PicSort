"""Shared widgets and a helper to run work off the Tk thread safely."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any, Callable


class TaskRunner:
    """Run functions in a background thread and deliver results on the Tk thread.

    Tkinter is not thread-safe, so worker threads never touch widgets. They
    ``post`` callables that the Tk event loop executes.
    """

    def __init__(self, root: tk.Misc, interval_ms: int = 50) -> None:
        self.root = root
        self._queue: queue.Queue[tuple[Callable[..., Any], tuple[Any, ...]]] = queue.Queue()
        self._interval = interval_ms
        self.root.after(self._interval, self._pump)

    def post(self, func: Callable[..., Any], *args: Any) -> None:
        self._queue.put((func, args))

    def run(
        self,
        work: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> threading.Thread:
        def target() -> None:
            try:
                result = work()
            except Exception as exc:  # noqa: BLE001 - reported to the UI
                self.post(on_error, exc)
            else:
                self.post(on_done, result)

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        return thread

    def _pump(self) -> None:
        try:
            while True:
                func, args = self._queue.get_nowait()
                func(*args)
        except queue.Empty:
            pass
        finally:
            self.root.after(self._interval, self._pump)


class PathPicker(ttk.Frame):
    """A labelled entry with a Browse button that picks a directory."""

    def __init__(self, master: tk.Misc, label: str, variable: tk.StringVar, width: int = 14) -> None:
        super().__init__(master)
        self.variable = variable
        ttk.Label(self, text=label, width=width).pack(side=tk.LEFT)
        ttk.Entry(self, textvariable=variable).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(self, text="Browse…", command=self.browse).pack(side=tk.LEFT)

    def browse(self) -> None:
        initial = self.variable.get() or None
        path = filedialog.askdirectory(initialdir=initial, mustexist=True)
        if path:
            self.variable.set(path)


class LogBox(ttk.Frame):
    """Read-only scrolling text area."""

    def __init__(self, master: tk.Misc, height: int = 10) -> None:
        super().__init__(master)
        self.text = tk.Text(self, height=height, state=tk.DISABLED, wrap="word")
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def append(self, message: str) -> None:
        self.text.configure(state=tk.NORMAL)
        self.text.insert(tk.END, message + "\n")
        self.text.see(tk.END)
        self.text.configure(state=tk.DISABLED)

    def clear(self) -> None:
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.configure(state=tk.DISABLED)


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
