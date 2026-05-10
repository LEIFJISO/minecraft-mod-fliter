"""Core filtering logic for Minecraft mods (Fabric / Forge / NeoForge)."""

import shutil
import zipfile
from pathlib import Path
from typing import Callable, Optional

from .bytecode import analyze_side_references, has_client_side_code
from .parsers import resolve_mod_metadata


class FilterResult:
    """Result of filtering a single mod jar."""

    __slots__ = ('jar_name', 'status', 'reason', 'loader', 'declared_side')

    def __init__(self, jar_name: str, status: str, reason: str,
                 loader: str = '', declared_side: str = ''):
        self.jar_name = jar_name
        self.status = status       # 'server', 'client', 'skipped', 'error'
        self.reason = reason
        self.loader = loader       # 'Fabric', 'Forge', 'NeoForge', 'Unknown'
        self.declared_side = declared_side  # declared side string (e.g. 'BOTH', 'CLIENT')


def is_server_compatible(sides: set[str]) -> bool:
    """Determine if a set of side values indicates server compatibility."""
    if 'error' in sides:
        return False
    if 'unknown' in sides:
        return False
    if not sides:
        return False
    return bool(sides & {'SERVER', 'BOTH'})


def filter_mods(
    input_dir: Path,
    output_dir: Path,
    *,
    copy: bool = False,
    strict: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> list[FilterResult]:
    """Filter mods from input_dir, keeping only server-compatible ones.

    Args:
        input_dir: Directory containing mod .jar files.
        output_dir: Directory where server-side mods will be written.
        copy: If True, copy files (keep originals). If False, move files.
        strict: If True, run bytecode analysis to detect mods that
                declare side=BOTH but actually only use client-side APIs.
        progress_callback: Optional callback(current, total) for progress.

    Returns:
        List of FilterResult for each processed jar.
    """
    results: list[FilterResult] = []
    jar_files = sorted(input_dir.glob('*.jar'))
    total = len(jar_files)

    if total == 0:
        return results

    output_dir.mkdir(parents=True, exist_ok=True)

    for idx, jar_path in enumerate(jar_files, 1):
        result = _filter_one(jar_path, output_dir, copy=copy, strict=strict)
        results.append(result)

        if progress_callback:
            progress_callback(idx, total)

    return results


def _filter_one(
    jar_path: Path,
    output_dir: Path,
    *,
    copy: bool,
    strict: bool,
) -> FilterResult:
    """Process a single mod jar and return a FilterResult."""
    name = jar_path.name

    metadata = resolve_mod_metadata(jar_path)
    sides = metadata['sides']
    loader = metadata['loader']
    declared_side = metadata.get('raw_side') or (
        ', '.join(sorted(sides - {'error', 'unknown'})) if sides else ''
    )

    # ── Handle error / unknown metadata ──
    if 'error' in sides:
        return FilterResult(name, 'error', f'({loader}) 元数据解析失败', loader, declared_side)

    if 'unknown' in sides:
        if strict:
            refs = analyze_side_references(jar_path)
            if refs['has_client'] and not refs['has_server']:
                return FilterResult(
                    name, 'client',
                    f'(未知加载器) 仅检测到客户端代码 → {refs["client_cls"]}',
                    loader, declared_side
                )
        return FilterResult(
            name, 'skipped',
            '(未知加载器) 未找到支持的元数据文件',
            loader, declared_side
        )

    # ── Strict mode: bytecode analysis ──
    if strict and 'BOTH' in sides and 'SERVER' not in sides and 'CLIENT' not in sides:
        # Only BOTH declared — verify with bytecode
        refs = analyze_side_references(jar_path)
        if refs['has_client'] and not refs['has_server']:
            return FilterResult(
                name, 'client',
                f'({loader}) 声明 side=BOTH 但仅含客户端代码 → {refs["client_cls"]}',
                loader, 'BOTH'
            )

    # ── Normal side-based decision ──
    if is_server_compatible(sides):
        dest = output_dir / name
        if dest.exists():
            return FilterResult(
                name, 'skipped',
                f'({loader}) 目标文件已存在 (side: {", ".join(sorted(sides))})',
                loader, declared_side
            )
        action = '复制' if copy else '移动'
        if copy:
            shutil.copy2(str(jar_path), str(dest))
        else:
            shutil.move(str(jar_path), str(dest))
        return FilterResult(
            name, 'server',
            f'({loader}) 已{action}到输出文件夹 (side: {", ".join(sorted(sides))})',
            loader, declared_side
        )
    else:
        return FilterResult(
            name, 'client',
            f'({loader}) 仅客户端运行 (side: {", ".join(sorted(sides))})',
            loader, declared_side
        )
