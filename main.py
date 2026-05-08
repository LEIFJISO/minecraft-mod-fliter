"""Entry point for Minecraft NeoForge Mod Filter."""

import sys
import tkinter as tk

from src.gui import ModFilterApp


def main():
    root = tk.Tk()

    # Center the window on screen
    root.update_idletasks()
    w = root.winfo_reqwidth()
    h = root.winfo_reqheight()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    root.geometry(f'+{x}+{y}')

    app = ModFilterApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
