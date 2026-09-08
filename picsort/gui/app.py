"""Main window."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from picsort import __version__
from picsort.gui.cleaner_tab import CleanerTab
from picsort.gui.common import TaskRunner
from picsort.gui.organizer_tab import OrganizerTab
from picsort.gui.people_tab import PeopleTab
from picsort.platform_utils import IS_MAC, IS_WINDOWS

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def _set_icon(root: tk.Tk) -> None:
    """Use the PicSort icon for the window (the .app/.exe bundle carries its own)."""
    icon_file = ASSETS / "icon_256.png"
    if not icon_file.exists():
        return
    try:
        root._picsort_icon = tk.PhotoImage(file=str(icon_file))  # keep a reference alive
        root.iconphoto(True, root._picsort_icon)
    except tk.TclError:
        pass


def _apply_style(root: tk.Tk) -> None:
    style = ttk.Style(root)
    preferred = "aqua" if IS_MAC else "vista" if IS_WINDOWS else "clam"
    if preferred in style.theme_names():
        style.theme_use(preferred)
    style.configure("Title.TLabel", font=("TkDefaultFont", 16, "bold"))


class PicSortApp(ttk.Frame):
    def __init__(self, root: tk.Tk) -> None:
        super().__init__(root)
        self.root = root
        self.runner = TaskRunner(root)
        self.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        notebook.add(OrganizerTab(notebook, self.runner), text="  Organizer  ")
        notebook.add(CleanerTab(notebook, self.runner), text="  Visual Cleaner  ")
        notebook.add(PeopleTab(notebook, self.runner), text="  People  ")


def main() -> None:
    root = tk.Tk()
    root.title(f"PicSort {__version__}")
    root.geometry("1000x720")
    root.minsize(760, 520)
    _apply_style(root)
    _set_icon(root)
    if IS_MAC:
        root.createcommand("tk::mac::Quit", root.destroy)
    root.bind_all("<Command-q>" if IS_MAC else "<Control-q>", lambda _e: root.destroy())
    PicSortApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
