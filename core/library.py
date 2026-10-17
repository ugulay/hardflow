# Pure library-path resolution -- stdlib only, no bpy.
#
# Hardflow ships a small starter library (decals, trim sheets and INSERT kit
# parts) inside the add-on, so a fresh install opens with content instead of
# three empty grids: the trim-sheet editor, the chroma key, the heightmap POM,
# the atlas and the whole INSERT system were unreachable until the user had
# sourced their own assets. The paid incumbents are bought for their libraries,
# so an empty one reads as an unfinished tool.
#
# Resolution order is "the user's folder if they set one, else the bundled one",
# and callers also need to know WHICH they got: the bundled folder ships inside
# the extension, so the library's rename/delete-on-disk buttons must not be
# pointed at it (on an extension install it may be read-only, and a file deleted
# there comes back on the next update -- confusing either way).
import os

DECALS = 'decals'
ASSETS = 'assets'
TRIMS = 'trims'
KINDS = (DECALS, ASSETS, TRIMS)

# Folder inside the add-on that holds the shipped content.
ROOT_DIRNAME = "library"


def bundled_dir(addon_dir, kind, root=ROOT_DIRNAME):
    """Absolute path of a bundled library folder, or "" when `addon_dir` is
    missing/None or `kind` is not one of KINDS. Does NOT check existence -- use
    `resolve_dir`, which falls back when the folder is not there (a trimmed-down
    install, or a source checkout before the library is generated)."""
    if not addon_dir or kind not in KINDS:
        return ""
    return os.path.join(addon_dir, root, kind)


def resolve_dir(user_path, bundled_path):
    """Which folder to scan, as ``(path, is_bundled)``.

    The user's own folder wins whenever they set one that exists; otherwise the
    bundled folder, when it exists; otherwise ``("", False)`` so callers keep
    their existing "nothing in the library" behaviour. A user path that is set
    but missing (a moved drive, a stale pref) falls back to the bundled content
    rather than showing an empty grid."""
    if user_path and os.path.isdir(user_path):
        return (user_path, False)
    if bundled_path and os.path.isdir(bundled_path):
        return (bundled_path, True)
    return ("", False)


def is_inside(path, folder):
    """True when `path` is `folder` or sits underneath it.

    Used for the read-only guard: an item scanned out of the bundled folder must
    not offer rename/delete. Case- and separator-insensitive, so it behaves on
    Windows, and never raises on unrelated drives or malformed input."""
    if not path or not folder:
        return False
    try:
        p = os.path.normcase(os.path.abspath(path))
        f = os.path.normcase(os.path.abspath(folder))
    except (OSError, ValueError):
        return False
    if p == f:
        return True
    return p.startswith(f.rstrip(os.sep) + os.sep)
