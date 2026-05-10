"""Bytecode analysis for detecting client-side and server-side mod usage.

Reads Java class files inside a mod JAR to check which side-specific
packages are referenced.
"""

import struct
import zipfile
from pathlib import Path

# Packages only available on the Minecraft client.
CLIENT_ONLY_PREFIXES = (
    'net/minecraft/client/',
    'net/minecraftforge/client/',
    'net/neoforged/neoforge/client/',
    'net/fabricmc/fabric/api/client/',
    'net/fabricmc/fabric/impl/client/',
)

# Packages only available on the Minecraft dedicated server.
SERVER_ONLY_PREFIXES = (
    'net/minecraft/server/',
    'net/minecraftforge/server/',
    'net/neoforged/neoforge/server/',
    'net/fabricmc/fabric/api/server/',
    'net/fabricmc/fabric/impl/server/',
)

# Max number of class files to scan before giving up.
MAX_CLASS_SCAN = 300


def _read_u2(data: bytes, offset: int) -> tuple[int, int]:
    """Read an unsigned 16-bit value, returning (value, next_offset)."""
    return struct.unpack_from('>H', data, offset)[0], offset + 2


def _read_u4(data: bytes, offset: int) -> tuple[int, int]:
    """Read an unsigned 32-bit value, returning (value, next_offset)."""
    return struct.unpack_from('>I', data, offset)[0], offset + 4


def _parse_constant_pool(data: bytes) -> list:
    """Parse the constant pool from JVM class file bytes.

    Each entry is a tuple: (tag, ...) or None for the placeholder slot
    that follows CONSTANT_Long / CONSTANT_Double entries.

    For CONSTANT_Utf8 entries (tag=1), the second element is the offset
    to the *length* field (2 bytes) followed by the string bytes.
    """
    cp_count, offset = _read_u2(data, 8)
    entries: list = []

    i = 1
    while i < cp_count:
        tag = data[offset]
        offset += 1

        if tag == 1:  # CONSTANT_Utf8
            utf8_offset = offset  # points to length prefix
            length, offset = _read_u2(data, offset)
            entries.append((tag, utf8_offset))
            offset += length
        elif tag in (3, 4):  # CONSTANT_Integer, CONSTANT_Float
            entries.append((tag,))
            offset += 4
        elif tag in (5, 6):  # CONSTANT_Long, CONSTANT_Double (take 2 slots)
            entries.append((tag,))
            offset += 8
            entries.append(None)
            i += 1
        elif tag == 7:  # CONSTANT_Class
            name_index, offset = _read_u2(data, offset)
            entries.append((tag, name_index))
        elif tag == 8:  # CONSTANT_String
            string_index, offset = _read_u2(data, offset)
            entries.append((tag, string_index))
        elif tag in (9, 10, 11):  # Fieldref, Methodref, InterfaceMethodref
            class_index, offset = _read_u2(data, offset)
            nat_index, offset = _read_u2(data, offset)
            entries.append((tag, class_index, nat_index))
        elif tag == 12:  # CONSTANT_NameAndType
            name_index, offset = _read_u2(data, offset)
            desc_index, offset = _read_u2(data, offset)
            entries.append((tag, name_index, desc_index))
        elif tag == 15:  # CONSTANT_MethodHandle
            ref_kind = data[offset]
            ref_index, offset = _read_u2(data, offset + 1)
            entries.append((tag, ref_kind, ref_index))
        elif tag == 16:  # CONSTANT_MethodType
            desc_index, offset = _read_u2(data, offset)
            entries.append((tag, desc_index))
        elif tag in (17, 18):  # CONSTANT_Dynamic, CONSTANT_InvokeDynamic
            bsm_idx, offset = _read_u2(data, offset)
            nat_idx, offset = _read_u2(data, offset)
            entries.append((tag, bsm_idx, nat_idx))
        elif tag in (19, 20):  # CONSTANT_Module, CONSTANT_Package
            name_index, offset = _read_u2(data, offset)
            entries.append((tag, name_index))
        else:
            return entries  # unknown tag, bail out

        i += 1

    return entries


def _resolve_class_name(cp: list, class_index: int, data: bytes) -> str | None:
    """Resolve a CONSTANT_Class entry to its fully-qualified class name.

    class_index is 1-based. Returns None if resolution fails.
    """
    if class_index <= 0 or class_index > len(cp):
        return None
    entry = cp[class_index - 1]
    if entry is None or entry[0] != 7:  # not CONSTANT_Class
        return None
    name_index = entry[1]
    if name_index <= 0 or name_index > len(cp):
        return None
    utf8_entry = cp[name_index - 1]
    if utf8_entry is None or utf8_entry[0] != 1:  # not CONSTANT_Utf8
        return None

    utf8_offset = utf8_entry[1]  # points to length prefix
    str_len = struct.unpack_from('>H', data, utf8_offset)[0]
    return data[utf8_offset + 2 : utf8_offset + 2 + str_len].decode('utf-8', errors='replace')


def _class_references_side(cp: list, data: bytes, prefixes: tuple[str, ...]) -> bool:
    """Check whether a single class references any of the given package prefixes."""
    for i, entry in enumerate(cp):
        if entry is None:
            continue
        tag = entry[0]
        class_index = None

        if tag == 7:  # CONSTANT_Class (self-referencing entry)
            class_index = i + 1
        elif tag in (9, 10, 11):  # Fieldref / Methodref / InterfaceMethodref
            class_index = entry[1]

        if class_index is not None:
            name = _resolve_class_name(cp, class_index, data)
            if name and name.startswith(prefixes):
                return True

    return False


def has_client_side_code(jar_path: Path) -> tuple[bool, str | None]:
    """Check if a mod JAR contains classes that reference client-only APIs.

    Scans up to MAX_CLASS_SCAN class files inside the JAR.

    Returns:
        (has_client_code, first_matched_class_name_or_None)
    """
    result = analyze_side_references(jar_path)
    return result['has_client'], result['client_cls']


def analyze_side_references(jar_path: Path) -> dict:
    """Analyze a mod JAR for client-side and server-side code references.

    Scans up to MAX_CLASS_SCAN class files inside the JAR.

    Returns:
        dict with keys:
            has_client  (bool) — found references to client-only packages
            has_server  (bool) — found references to server-only packages
            client_cls  (str|None) — first class that triggered client detection
            server_cls  (str|None) — first class that triggered server detection
    """
    result = {
        'has_client': False,
        'has_server': False,
        'client_cls': None,
        'server_cls': None,
    }
    try:
        with zipfile.ZipFile(jar_path, 'r') as zf:
            scanned = 0
            for entry_name in zf.namelist():
                if not entry_name.endswith('.class'):
                    continue

                data = zf.read(entry_name)
                if len(data) < 10:
                    continue
                if data[:4] != b'\xca\xfe\xba\xbe':
                    continue

                try:
                    cp = _parse_constant_pool(data)
                except Exception:
                    continue

                if not result['has_client'] and _class_references_side(cp, data, CLIENT_ONLY_PREFIXES):
                    result['has_client'] = True
                    result['client_cls'] = entry_name

                if not result['has_server'] and _class_references_side(cp, data, SERVER_ONLY_PREFIXES):
                    result['has_server'] = True
                    result['server_cls'] = entry_name

                # Early exit if both sides found
                if result['has_client'] and result['has_server']:
                    break

                scanned += 1
                if scanned >= MAX_CLASS_SCAN:
                    break

    except Exception:
        pass

    return result
