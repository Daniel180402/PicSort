"""Tab 1: sort files into Year/Month folders."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from picsort.gui.common import LogBox, PathPicker, TaskRunner
from picsort.organizer import Organizer, SortOptions, SortResult


class OrganizerTab(ttk.Frame):
    def __init__(self, master: tk.Misc, runner: TaskRunner) -> None:
        super().__init__(master, padding=20)
        self.runner = runner
        self.cancel_event = threading.Event()
        self.running = False

        self.source_dir = tk.StringVar()
        self.dest_dir = tk.StringVar()
        self.mode = tk.StringVar(value="copy")
        self.media_only = tk.BooleanVar(value=True)

        ttk.Label(self, text="Sort & Rename by Date", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 10))
        ttk.Label(
            self,
            text="Files are placed in Destination/Year/Month and renamed to their capture time. "
            "Exact duplicates are skipped automatically.",
            wraplength=700,
        ).pack(anchor=tk.W, pady=(0, 10))

        PathPicker(self, "Source:", self.source_dir).pack(fill=tk.X, pady=4)
        PathPicker(self, "Destination:", self.dest_dir).pack(fill=tk.X, pady=4)

        options = ttk.Frame(self)
        options.pack(fill=tk.X, pady=8)
        ttk.Radiobutton(options, text="Copy files (keep originals)", variable=self.mode, value="copy").pack(side=tk.LEFT)
        ttk.Radiobutton(options, text="Move files", variable=self.mode, value="move").pack(side=tk.LEFT, padx=15)
        ttk.Checkbutton(options, text="Photos and videos only", variable=self.media_only).pack(side=tk.LEFT, padx=15)

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, pady=8)
        self.start_btn = ttk.Button(buttons, text="Start Sorting", command=self.start)
        self.start_btn.pack(side=tk.LEFT)
        self.cancel_btn = ttk.Button(buttons, text="Cancel", command=self.cancel, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=8)
        self.status = ttk.Label(buttons, text="Ready")
        self.status.pack(side=tk.LEFT, padx=10)

        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(self, variable=self.progress_var, maximum=100).pack(fill=tk.X, pady=5)

        self.log = LogBox(self)
        self.log.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    # -- actions -----------------------------------------------------------

    def start(self) -> None:
        source, dest = self.source_dir.get().strip(), self.dest_dir.get().strip()
        if not source or not dest:
            messagebox.showerror("PicSort", "Please choose a source and a destination folder.")
            return
        if not Path(source).is_dir():
            messagebox.showerror("PicSort", "The source folder does not exist.")
            return
        if self.running:
            return
        if self.mode.get() == "move" and not messagebox.askyesno(
            "Move files?", "Files will be moved out of the source folder. Continue?"
        ):
            return

        options = SortOptions(
            source=Path(source),
            destination=Path(dest),
            move=self.mode.get() == "move",
            media_only=self.media_only.get(),
        )
        self.cancel_event.clear()
        self.running = True
        self.start_btn.configure(state=tk.DISABLED)
        self.cancel_btn.configure(state=tk.NORMAL)
        self.progress_var.set(0)
        self.log.clear()
        self.log.append(f"{'Moving' if options.move else 'Copying'} from {source} to {dest}")

        organizer = Organizer(
            options,
            progress=lambda done, total, name: self.runner.post(self._on_progress, done, total, name),
            log=lambda msg: self.runner.post(self.log.append, msg),
            cancel_event=self.cancel_event,
        )
        self.runner.run(organizer.run, self._on_done, self._on_error)

    def cancel(self) -> None:
        self.cancel_event.set()
        self.status.configure(text="Cancelling…")

    # -- callbacks on the Tk thread -----------------------------------------

    def _on_progress(self, done: int, total: int, name: str) -> None:
        self.progress_var.set(done / total * 100 if total else 100)
        self.status.configure(text=f"{done} / {total}  {name}")

    def _finish(self) -> None:
        self.running = False
        self.start_btn.configure(state=tk.NORMAL)
        self.cancel_btn.configure(state=tk.DISABLED)

    def _on_done(self, result: SortResult) -> None:
        self._finish()
        verb = "Moved" if self.mode.get() == "move" else "Copied"
        summary = f"{verb} {result.transferred}, skipped {result.skipped_duplicates} duplicates"
        if result.errors:
            summary += f", {len(result.errors)} errors"
        if result.cancelled:
            summary = "Cancelled. " + summary
        self.status.configure(text=summary)
        self.log.append(summary)
        if not result.cancelled:
            messagebox.showinfo("PicSort", f"Sorting complete.\n{summary}")

    def _on_error(self, exc: Exception) -> None:
        self._finish()
        self.status.configure(text="Failed")
        self.log.append(f"Failed: {exc}")
        messagebox.showerror("PicSort", f"Sorting failed:\n{exc}")
