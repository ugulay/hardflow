# Pure helpers for the v1.0 asset / kitbash library: discover
# .blend asset files on disk. No bpy here -- only the stdlib -- so it stays
# unit-testable without Blender (mirrors core/decal_image.py). The bpy side
# (appending objects, placing INSERTs) lives in core/asset.py; the operators/UI
# in operators/assets.py + ui/asset_panel.py.
import os


# Library file extensions: a kit part is a .blend the user appends from.
ASSET_EXTS = frozenset((".blend",))


def is_asset_file(name):
    """True if name (a filename or path) is a Blender library file."""
    return os.path.splitext(name)[1].lower() in ASSET_EXTS


def scan_assets(folder):
    """List the .blend files directly inside folder as (display_name, abspath)
    tuples, sorted by filename. display_name is the file stem (no extension).

    Returns [] for a missing/empty/None folder or any access error, so callers
    can treat it as 'nothing in the library' without guarding. Mirrors
    core/decal_image.scan_library."""
    if not folder or not os.path.isdir(folder):
        return []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    out = []
    for fn in names:
        full = os.path.join(folder, fn)
        if is_asset_file(fn) and os.path.isfile(full):
            out.append((os.path.splitext(fn)[0], full))
    return out
