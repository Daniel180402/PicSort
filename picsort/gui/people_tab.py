"""Tab 3: group photos by person (optional face recognition)."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from picsort.faces import FACE_REC_AVAILABLE, cluster_faces
from picsort.gui.common import PathPicker, TaskRunner
from picsort.platform_utils import open_path


class PeopleTab(ttk.Frame):
    def __init__(self, master: tk.Misc, runner: TaskRunner) -> None:
        super().__init__(master, padding=20)
        self.runner = runner
        self.cancel_event = threading.Event()
        self.running = False
        self.clusters: dict[int, list[Path]] = {}
        self.person_ids: list[int] = []

        ttk.Label(self, text="People", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 10))

        if not FACE_REC_AVAILABLE:
            ttk.Label(
                self,
                text="Face recognition is optional and not installed.\n\n"
                "Install the extra dependencies and restart PicSort:\n"
                "    pip install -r requirements-faces.txt\n\n"
                "See README.md for platform specific notes (dlib needs a C++ compiler).",
                justify=tk.LEFT,
            ).pack(anchor=tk.W, pady=20)
            return

        self.scan_dir = tk.StringVar()
        PathPicker(self, "Folder to scan:", self.scan_dir).pack(fill=tk.X, pady=4)

        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, pady=8)
        self.scan_btn = ttk.Button(controls, text="Scan for Faces", command=self.start)
        self.scan_btn.pack(side=tk.LEFT)
        self.cancel_btn = ttk.Button(controls, text="Cancel", command=self.cancel, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=8)
        self.status = ttk.Label(controls, text="Ready")
        self.status.pack(side=tk.LEFT, padx=10)

        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(self, variable=self.progress_var, maximum=100).pack(fill=tk.X, pady=(0, 8))

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned)
        ttk.Label(left, text="People found").pack(anchor=tk.W)
        self.people_list = tk.Listbox(left, width=22, exportselection=False)
        self.people_list.pack(fill=tk.BOTH, expand=True)
        self.people_list.bind("<<ListboxSelect>>", self._on_person_select)
        paned.add(left, weight=1)

        right = ttk.Frame(paned)
        ttk.Label(right, text="Photos of selected person (double-click to open)").pack(anchor=tk.W)
        self.photos = ttk.Treeview(right, columns=("path",), show="headings")
        self.photos.heading("path", text="File")
        self.photos.pack(fill=tk.BOTH, expand=True)
        self.photos.bind("<Double-1>", self._open_photo)
        paned.add(right, weight=3)

    def start(self) -> None:
        folder = self.scan_dir.get().strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showerror("PicSort", "Please choose an existing folder to scan.")
            return
        if self.running:
            return
        self.running = True
        self.cancel_event.clear()
        self.scan_btn.configure(state=tk.DISABLED)
        self.cancel_btn.configure(state=tk.NORMAL)
        self.status.configure(text="Scanning…")
        self.runner.run(
            lambda: cluster_faces(
                folder,
                progress=lambda done, total, name: self.runner.post(self._on_progress, done, total, name),
                cancel_event=self.cancel_event,
            ),
            self._on_done,
            self._on_error,
        )

    def cancel(self) -> None:
        self.cancel_event.set()

    def _on_progress(self, done: int, total: int, _name: str) -> None:
        self.progress_var.set(done / total * 100 if total else 100)
        self.status.configure(text=f"Scanning {done} / {total}")

    def _finish(self) -> None:
        self.running = False
        self.scan_btn.configure(state=tk.NORMAL)
        self.cancel_btn.configure(state=tk.DISABLED)

    def _on_done(self, clusters: dict[int, list[Path]]) -> None:
        self._finish()
        self.clusters = clusters
        self.person_ids = list(clusters)
        self.people_list.delete(0, tk.END)
        for person_id in self.person_ids:
            self.people_list.insert(tk.END, f"Person {person_id + 1}  ({len(clusters[person_id])} photos)")
        self.photos.delete(*self.photos.get_children())
        self.status.configure(text=f"Found {len(clusters)} people")

    def _on_error(self, exc: Exception) -> None:
        self._finish()
        self.status.configure(text="Failed")
        messagebox.showerror("PicSort", f"Face scan failed:\n{exc}")

    def _on_person_select(self, _event: object) -> None:
        selection = self.people_list.curselection()
        if not selection:
            return
        person_id = self.person_ids[selection[0]]
        self.photos.delete(*self.photos.get_children())
        for path in self.clusters.get(person_id, []):
            self.photos.insert("", tk.END, values=(str(path),))

    def _open_photo(self, _event: object) -> None:
        for iid in self.photos.selection():
            open_path(self.photos.item(iid)["values"][0])
