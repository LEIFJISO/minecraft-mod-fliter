"""GUI for Minecraft Mod Filter (Fabric / Forge / NeoForge)."""

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .filter import filter_mods


class ModFilterApp:
    """Main GUI application for filtering Minecraft mods."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title('Minecraft Mod 筛选器 (Fabric / Forge / NeoForge)')
        self.root.geometry('800x550')
        self.root.minsize(650, 450)
        self.root.resizable(True, True)

        self._is_running = False
        self._setup_ui()

    def _setup_ui(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass

        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # ── Input folder ──
        ttk.Label(main, text='输入文件夹 (存放所有 Mod):').pack(anchor=tk.W)
        f1 = ttk.Frame(main)
        f1.pack(fill=tk.X, pady=(0, 10))
        self.input_var = tk.StringVar()
        ttk.Entry(f1, textvariable=self.input_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(f1, text='浏览...', command=self._browse_input).pack(side=tk.LEFT, padx=(6, 0))

        # ── Output folder ──
        ttk.Label(main, text='输出文件夹 (存放筛选后的 Mod):').pack(anchor=tk.W)
        f2 = ttk.Frame(main)
        f2.pack(fill=tk.X, pady=(0, 10))
        self.output_var = tk.StringVar()
        ttk.Entry(f2, textvariable=self.output_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(f2, text='浏览...', command=self._browse_output).pack(side=tk.LEFT, padx=(6, 0))

        # ── Options ──
        opts = ttk.Frame(main)
        opts.pack(fill=tk.X, pady=(0, 10))

        self.copy_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts, text='复制到输出文件夹 (不保留原文件则移动)',
            variable=self.copy_var
        ).pack(side=tk.LEFT)

        self.strict_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts, text='严格模式: 检测声明 BOTH 但实际仅含客户端代码的 Mod',
            variable=self.strict_var
        ).pack(side=tk.LEFT, padx=(20, 0))

        # ── Filter button ──
        self.filter_btn = ttk.Button(main, text='开始筛选', command=self._start_filter)
        self.filter_btn.pack(pady=(0, 8))

        # ── Progress ──
        self.progress = ttk.Progressbar(main, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(0, 4))
        self.status_var = tk.StringVar(value='就绪')
        ttk.Label(main, textvariable=self.status_var).pack(anchor=tk.W)

        # ── Results table ──
        ttk.Label(main, text='筛选结果:').pack(anchor=tk.W, pady=(10, 4))
        tree_frame = ttk.Frame(main)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('status', 'name', 'reason')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='none')
        self.tree.heading('status', text='状态')
        self.tree.heading('name', text='文件名')
        self.tree.heading('reason', text='说明')
        self.tree.column('status', width=60, anchor=tk.CENTER)
        self.tree.column('name', width=240)
        self.tree.column('reason', width=430)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # ── Event handlers ──────────────────────────────────────────────

    def _browse_input(self):
        path = filedialog.askdirectory(title='选择输入文件夹')
        if path:
            self.input_var.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title='选择输出文件夹')
        if path:
            self.output_var.set(path)

    def _validate_paths(self) -> tuple[str, str] | None:
        """Validate input/output paths. Returns (input, output) or None."""
        input_dir = self.input_var.get().strip()
        output_dir = self.output_var.get().strip()

        if not input_dir:
            messagebox.showwarning('提示', '请选择输入文件夹')
            return None
        if not output_dir:
            messagebox.showwarning('提示', '请选择输出文件夹')
            return None
        if not os.path.isdir(input_dir):
            messagebox.showerror('错误', f'输入文件夹不存在:\n{input_dir}')
            return None
        in_p = Path(input_dir).resolve()
        out_p = Path(output_dir).resolve()
        if in_p == out_p:
            messagebox.showerror('错误', '输入和输出文件夹不能相同')
            return None
        return input_dir, output_dir

    def _start_filter(self):
        paths = self._validate_paths()
        if paths is None:
            return

        input_dir, output_dir = paths

        # Clear previous results
        for item in self.tree.get_children():
            self.tree.delete(item)

        self._is_running = True
        self.filter_btn.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self._copy_mode = self.copy_var.get()
        self._strict_mode = self.strict_var.get()

        thread = threading.Thread(
            target=self._run_filter, args=(input_dir, output_dir), daemon=True
        )
        thread.start()

    def _run_filter(self, input_dir: str, output_dir: str):
        results = filter_mods(
            Path(input_dir),
            Path(output_dir),
            copy=self._copy_mode,
            strict=self._strict_mode,
            progress_callback=self._on_progress,
        )
        self.root.after(0, self._on_filter_done, results)

    def _on_progress(self, current: int, total: int):
        self.root.after(0, self._update_progress, current, total)

    def _update_progress(self, current: int, total: int):
        self.progress['maximum'] = total
        self.progress['value'] = current
        self.status_var.set(f'处理中... ({current}/{total})')

    def _on_filter_done(self, results):
        icons = {
            'server': '\u2705', 'client': '\u274c', 'skipped': '\u26a0\ufe0f', 'error': '\u26a0\ufe0f',
        }
        for r in results:
            icon = icons.get(r.status, '?')
            self.tree.insert('', tk.END, values=(icon, r.jar_name, r.reason))

        count_server = sum(1 for r in results if r.status == 'server')
        count_client = sum(1 for r in results if r.status == 'client')
        count_skip = sum(1 for r in results if r.status == 'skipped')
        count_error = sum(1 for r in results if r.status == 'error')

        parts = [f'共 {len(results)} 个文件']
        if count_server:
            parts.append(f'{count_server} 个已{"复制" if self._copy_mode else "移动"}至输出文件夹')
        if count_client:
            parts.append(f'{count_client} 个仅客户端')
        if count_skip:
            parts.append(f'{count_skip} 个跳过')
        if count_error:
            parts.append(f'{count_error} 个错误')

        self.status_var.set('完成: ' + ', '.join(parts[1:]) if len(parts) > 1 else '未发现 .jar 文件')
        self.progress['value'] = self.progress['maximum']
        self._is_running = False
        self.filter_btn.config(state=tk.NORMAL)
