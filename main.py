"""Entry point for Minecraft Mod Filter (Fabric / Forge / NeoForge)."""

import tkinter as tk

from src.gui import ModFilterApp


def main():
    root = tk.Tk()
    app = ModFilterApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
