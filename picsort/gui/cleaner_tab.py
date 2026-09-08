"""Tab 2: find and remove visually similar images."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from picsort.gui.common import PathPicker, TaskRunner, human_size
from picsort.platform_utils import IS_MAC, open_path, reveal_in_file_manager
from picsort.similar import DEFAULT_THRESHOLD, SimilarGroup, SimilarImage, scan_folder

PREVIEW_SIZE = 320


class CleanerTab(ttk.Frame):
    def __init__(self, master: tk.Misc, runner: TaskRunner) -> None:
        super().__init__(master, padding=20)
        self.runner = runner
        self.cancel_event = threading.Event()
        self.running = False
        self.items: dict[str, SimilarImage] = {}
        self._preview_photo: ImageTk.PhotoImage | None = None

        self.scan_dir = tk.StringVar()
        self.threshold = tk.IntVar(value=DEFAULT_THRESHOLD)

        ttk.Label(self, text="Visual Cleaner", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 10))
        PathPicker(self, "Folder to scan:", self.scan_dir).pack(fill=tk.X, pady=4)

        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, pady=8)
        self.scan_btn = ttk.Button(controls, text="Scan for Similar Images", command=self.start)
        self.scan_btn.pack(side=tk.LEFT)
        self.cancel_btn = ttk.Button(controls, text="Cancel", command=self.cancel, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=8)
        ttk.Label(controls, text="Sensitivity (0 = identical only):").pack(side=tk.LEFT, padx=(15, 4))
        ttk.Spinbox(controls, from_=0, to=20, width=4, textvariable=self.threshold).pack(side=tk.LEFT)
        self.status = ttk.Label(controls, text="Ready")
        self.status.pack(side=tk.LEFT, padx=10)

        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(self, variable=self.progress_var, maximum=100).pack(fill=tk.X, pady=(0, 8))

        body = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True)

        tree_frame = ttk.Frame(body)
        self.tree = ttk.Treeview(tree_frame, columns=("distance", "size"), selectmode="extended")
        self.tree.heading("#0", text="Image")
        self.tree.heading("distance", text="Difference")
        self.tree.heading("size", text="Size")
        self.tree.column("#0", width=420, stretch=True)
        self.tree.column("distance", width=90, anchor=tk.CENTER, stretch=False)
        self.tree.column("size", width=90, anchor=tk.E, stretch=False)
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _e: self.open_selected())
        body.add(tree_frame, weight=3)

        preview_frame = ttk.LabelFrame(body, text="Preview", padding=8)
        self.preview = ttk.Label(preview_frame, anchor=tk.CENTER)
        self.preview.pack(fill=tk.BOTH, expand=True)
        self.preview_info = ttk.Label(preview_frame, text="", wraplength=PREVIEW_SIZE, justify=tk.LEFT)
        self.preview_info.pack(fill=tk.X, pady=(6, 0))
        body.add(preview_frame, weight=1)

        actions = ttk.Frame(self)
        actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(actions, text="Select All But First in Each Group", command=self.select_redundant).pack(side=tk.LEFT)
        self.delete_btn = ttk.Button(actions, text="Move Selected to Trash", command=self.delete_selected)
        self.delete_btn.pack(side=tk.RIGHT)
        ttk.Button(actions, text="Show in Finder" if IS_MAC else "Show in Folder", command=self.reveal_selected).pack(side=tk.RIGHT, padx=5)
        ttk.Button(actions, text="Open", command=self.open_selected).pack(side=tk.RIGHT, padx=5)

    # -- scanning ----------------------------------------------------------

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
        self.progress_var.set(0)
        self.status.configure(text="Looking for images…")
        threshold = self.threshold.get()
        self.runner.run(
            lambda: scan_folder(
                folder,
                threshold=threshold,
                progress=lambda done, total, name: self.runner.post(self._on_progress, done, total, name),
                cancel_event=self.cancel_event,
            ),
            self._on_done,
            self._on_error,
        )

    def cancel(self) -> None:
        self.cancel_event.set()
        self.status.configure(text="Cancelling…")

    def _on_progress(self, done: int, total: int, name: str) -> None:
        self.progress_var.set(done / total * 100 if total else 100)
        self.status.configure(text=f"Hashing {done} / {total}")

    def _finish(self) -> None:
        self.running = False
        self.scan_btn.configure(state=tk.NORMAL)
        self.cancel_btn.configure(state=tk.DISABLED)

    def _on_done(self, groups: list[SimilarGroup]) -> None:
        self._finish()
        self.progress_var.set(100)
        self._populate(groups)
        if self.cancel_event.is_set():
            self.status.configure(text="Cancelled")
            return
        total_images = sum(len(g.images) for g in groups)
        self.status.configure(text=f"Found {len(groups)} groups ({total_images} images)")

    def _on_error(self, exc: Exception) -> None:
        self._finish()
        self.status.configure(text="Failed")
        messagebox.showerror("PicSort", f"Scan failed:\n{exc}")

    def _populate(self, groups: list[SimilarGroup]) -> None:
        self.tree.delete(*self.tree.get_children())
        self.items.clear()
        for index, group in enumerate(groups, start=1):
            parent = self.tree.insert("", tk.END, text=f"Group {index}  ({len(group.images)} images)", open=True)
            for image in group.images:
                iid = self.tree.insert(
                    parent, tk.END, text=str(image.path),
                    values=("identical" if image.distance == 0 else f"{image.distance}", human_size(image.size)),
                )
                self.items[iid] = image

    # -- selection helpers -------------------------------------------------

    def _selected_images(self) -> list[tuple[str, SimilarImage]]:
        return [(iid, self.items[iid]) for iid in self.tree.selection() if iid in self.items]

    def select_redundant(self) -> None:
        keep: list[str] = []
        for group in self.tree.get_children():
            keep.extend(self.tree.get_children(group)[1:])
        self.tree.selection_set(keep)
        self.status.configure(text=f"Selected {len(keep)} images")

    def _on_select(self, _event: object) -> None:
        selected = self._selected_images()
        if not selected:
            return
        image = selected[-1][1]
        self._show_preview(image)

    def _show_preview(self, image: SimilarImage) -> None:
        try:
            with Image.open(image.path) as img:
                img.draft("RGB", (PREVIEW_SIZE * 2, PREVIEW_SIZE * 2))
                dimensions = img.size
                img = img.convert("RGB")
                img.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE))
                self._preview_photo = ImageTk.PhotoImage(img)
        except Exception:  # noqa: BLE001 - unreadable image
            self._preview_photo = None
            self.preview.configure(image="", text="No preview")
            self.preview_info.configure(text=image.path.name)
            return
        self.preview.configure(image=self._preview_photo, text="")
        self.preview_info.configure(
            text=f"{image.path.name}\n{dimensions[0]} × {dimensions[1]} px, {human_size(image.size)}"
        )

    # -- actions -----------------------------------------------------------

    def open_selected(self) -> None:
        for _iid, image in self._selected_images()[:5]:
            open_path(image.path)

    def reveal_selected(self) -> None:
        selected = self._selected_images()
        if selected:
            reveal_in_file_manager(selected[-1][1].path)

    def delete_selected(self) -> None:
        selected = self._selected_images()
        if not selected:
            return
        total = human_size(sum(img.size for _i, img in selected))
        if not messagebox.askyesno("Move to Trash", f"Move {len(selected)} files ({total}) to the trash?"):
            return
        try:
            from send2trash import send2trash
        except ImportError:
            if not messagebox.askyesno(
                "Trash unavailable",
                "The send2trash package is not installed, so files cannot be moved to the trash.\n\n"
                "Delete them permanently instead?",
            ):
                return
            send2trash = None

        failed = 0
        for iid, image in selected:
            try:
                if send2trash:
                    send2trash(str(image.path))
                else:
                    image.path.unlink()
            except Exception:  # noqa: BLE001 - keep going, report count
                failed += 1
                continue
            parent = self.tree.parent(iid)
            self.tree.delete(iid)
            self.items.pop(iid, None)
            if len(self.tree.get_children(parent)) < 2:
                for leftover in self.tree.get_children(parent):
                    self.items.pop(leftover, None)
                self.tree.delete(parent)
        message = f"Removed {len(selected) - failed} files"
        if failed:
            message += f", {failed} failed"
        self.status.configure(text=message)
