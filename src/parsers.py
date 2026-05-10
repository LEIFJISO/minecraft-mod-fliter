"""Metadata parsers for Fabric, Forge, and NeoForge mods."""

import json
import re
import zipfile
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


def resolve_mod_metadata(jar_path: Path) -> dict:
    """Detect the mod loader type and extract declared side(s).

    Returns:
        dict with keys: 'loader' (str), 'sides' (set[str]), 'raw_side' (str or None)
    """
    with zipfile.ZipFile(jar_path, 'r') as zf:
        namelist = zf.NameToInfo

        # 1. Check Fabric (fabric.mod.json) — highest priority for 信雅互联
        if 'fabric.mod.json' in namelist:
            result = _parse_fabric(zf)
            if result:
                return result

        # 2. Check NeoForge
        for candidate in ('META-INF/neoforge.mods.toml', 'neoforge.mods.toml'):
            if candidate in namelist:
                result = _parse_forge_toml(zf, candidate, 'NeoForge')
                if result:
                    return result

        # 3. Check Forge (META-INF/mods.toml)
        if 'META-INF/mods.toml' in namelist:
            result = _parse_forge_toml(zf, 'META-INF/mods.toml', 'Forge')
            if result:
                return result

    return {'loader': 'Unknown', 'sides': {'unknown'}, 'raw_side': None}


def _parse_fabric(zf: zipfile.ZipFile) -> dict | None:
    """Parse fabric.mod.json for environment field."""
    try:
        raw = zf.read('fabric.mod.json').decode('utf-8')
    except UnicodeDecodeError:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {'loader': 'Fabric', 'sides': {'error'}, 'raw_side': None}

    # Standard Fabric: "environment" field
    env = data.get('environment')
    if env is None:
        env_raw = None
    elif isinstance(env, str):
        env_raw = env
    else:
        env_raw = str(env)

    if env == 'client':
        sides = {'CLIENT'}
    elif env == 'server':
        sides = {'SERVER'}
    elif env == '*':
        sides = {'BOTH'}
    else:
        # Some mods use nested or non-standard formats; default to BOTH
        sides = {'BOTH'}

    return {'loader': 'Fabric', 'sides': sides, 'raw_side': env_raw}


def _parse_forge_toml(zf: zipfile.ZipFile, path: str, loader: str) -> dict | None:
    """Parse a Forge/NeoForge-style TOML for side field."""
    try:
        raw_bytes = zf.read(path)
    except KeyError:
        return None

    try:
        raw = raw_bytes.decode('utf-8')
    except UnicodeDecodeError:
        try:
            raw = raw_bytes.decode('utf-8-sig')
        except UnicodeDecodeError:
            raw = raw_bytes.decode('latin-1')

    # Try proper TOML parser first
    if tomllib is not None:
        try:
            data = tomllib.loads(raw)
            mods_list = data.get('mods', [])
            if not isinstance(mods_list, list):
                mods_list = [mods_list]
            sides: set[str] = set()
            raw_side = None
            for mod_entry in mods_list:
                side_val = mod_entry.get('side', 'BOTH').upper()
                sides.add(side_val)
                if raw_side is None and isinstance(side_val, str):
                    raw_side = side_val
            return {'loader': loader, 'sides': sides if sides else {'BOTH'}, 'raw_side': raw_side}
        except Exception:
            pass

    # Regex fallback
    try:
        sides = _parse_toml_side_regex(raw)
        raw_side = next(iter(sides)) if len(sides) == 1 else None
        return {'loader': loader, 'sides': sides if sides else {'BOTH'}, 'raw_side': raw_side}
    except Exception:
        return {'loader': loader, 'sides': {'error'}, 'raw_side': None}


def _parse_toml_side_regex(content: str) -> set[str]:
    """Simple regex-based parser to extract side values from TOML."""
    sides: set[str] = set()
    in_mods_section = False

    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        if stripped == '[[mods]]':
            in_mods_section = True
            continue
        if stripped.startswith('['):
            in_mods_section = False
            continue

        if in_mods_section:
            m = re.match(r'^side\s*=\s*"([^"]*)"', stripped, re.IGNORECASE)
            if m:
                sides.add(m.group(1).upper())

    return sides
