"""Core filtering logic for NeoForge mods."""

import re
import shutil
import zipfile
from pathlib import Path
from typing import Callable, Optional

# Try to use a proper TOML parser
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


class FilterResult:
    """Result of filtering a single mod jar."""

    __slots__ = ('jar_name', 'status', 'reason')

    def __init__(self, jar_name: str, status: str, reason: str):
        self.jar_name = jar_name
        self.status = status   # 'server', 'client', 'error', 'skipped'
        self.reason = reason


def _parse_side_simple(toml_content: str) -> set[str]:
    """Simple regex-based parser to extract side values from neoforge.mods.toml."""
    sides: set[str] = set()
    in_mods_section = False

    for line in toml_content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        if stripped == '[[mods]]':
            in_mods_section = True
            continue
        if stripped.startswith('[[') or stripped.startswith('['):
            in_mods_section = False
            continue

        if in_mods_section:
            m = re.match(r'^side\s*=\s*"([^"]*)"', stripped, re.IGNORECASE)
            if m:
                sides.add(m.group(1).upper())

    return sides


def parse_mod_side(jar_path: Path) -> set[str]:
    """Parse the neoforge.mods.toml inside a jar and return a set of side values."""
    sides: set[str] = set()

    with zipfile.ZipFile(jar_path, 'r') as zf:
        toml_name = None
        for candidate in ('META-INF/neoforge.mods.toml', 'neoforge.mods.toml'):
            if candidate in zf.NameToInfo:
                toml_name = candidate
                break

        if toml_name is None:
            return {'unknown'}

        raw_bytes = zf.read(toml_name)
        try:
            raw = raw_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                raw = raw_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                raw = raw_bytes.decode('latin-1')

        if tomllib is not None:
            try:
                data = tomllib.loads(raw)
                mods_list = data.get('mods', [])
                if not isinstance(mods_list, list):
                    mods_list = [mods_list]
                for mod_entry in mods_list:
                    side = mod_entry.get('side', 'BOTH').upper()
                    sides.add(side)
                return sides
            except Exception:
                pass

        # Fallback to simple regex parser
        try:
            sides = _parse_side_simple(raw)
        except Exception:
            return {'error'}

    return sides


def is_server_compatible(sides: set[str]) -> bool:
    """Determine if a mod is server-compatible based on side values."""
    if 'error' in sides:
        return False
    if 'unknown' in sides:
        return False
    if not sides:
        return False
    # Include if any mod entry is SERVER or BOTH
    return bool(sides & {'SERVER', 'BOTH'})


def filter_mods(
    input_dir: Path,
    output_dir: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> list[FilterResult]:
    """Filter NeoForge mods from input_dir and move server-compatible ones to output_dir.

    Args:
        input_dir: Directory containing NeoForge mod .jar files.
        output_dir: Directory where server-side mods will be moved.
        progress_callback: Optional callback(current, total) for progress updates.

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
        try:
            sides = parse_mod_side(jar_path)

            if 'error' in sides:
                results.append(FilterResult(jar_path.name, 'error', 'TOML 解析失败'))
            elif 'unknown' in sides:
                results.append(FilterResult(jar_path.name, 'skipped', '未找到 neoforge.mods.toml'))
            elif is_server_compatible(sides):
                dest = output_dir / jar_path.name
                if dest.exists():
                    results.append(FilterResult(
                        jar_path.name, 'skipped',
                        f'目标文件已存在, 跳过 (side: {", ".join(sorted(sides))})'
                    ))
                else:
                    shutil.move(str(jar_path), str(dest))
                    results.append(FilterResult(
                        jar_path.name, 'server',
                        f'已移动到输出文件夹 (side: {", ".join(sorted(sides))})'
                    ))
            else:
                results.append(FilterResult(
                    jar_path.name, 'client',
                    f'跳过, 仅在客户端运行 (side: {", ".join(sorted(sides))})'
                ))
        except Exception as e:
            results.append(FilterResult(jar_path.name, 'error', str(e)))

        if progress_callback:
            progress_callback(idx, total)

    return results
