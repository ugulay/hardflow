# Pure helpers for the v0.9 decal image library: discover image files on disk and
# fit a decal's aspect ratio to an image. No bpy / mathutils / filesystem-of-bpy
# here -- only the stdlib -- so it stays unit-testable without Blender (mirrors
# core/decal_math.py). The bpy side (loading images, building the material) lives
# in core/decal.py; the operators/UI in operators/decals.py + ui/decal_library.py.
import os


# Image extensions Blender can load as a texture. Lower-case, with the dot.
IMAGE_EXTS = frozenset((
    ".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff",
    ".bmp", ".exr", ".hdr", ".webp",
))


def is_image_file(name):
    """True if name (a filename or path) has a known image extension."""
    return os.path.splitext(name)[1].lower() in IMAGE_EXTS


def scan_library(folder):
    """List the image files directly inside folder as (display_name, abspath)
    tuples, sorted by filename. display_name is the file stem (no extension).

    Returns [] for a missing/empty/None folder or any access error, so callers
    can treat it as 'nothing in the library' without guarding."""
    if not folder or not os.path.isdir(folder):
        return []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    out = []
    for fn in names:
        full = os.path.join(folder, fn)
        if is_image_file(fn) and os.path.isfile(full):
            out.append((os.path.splitext(fn)[0], full))
    return out


def safe_filename(name, default="untitled"):
    """Sanitize a user-supplied name into a safe single filename stem (no
    extension): drop directory separators and characters illegal on common
    filesystems, turn control whitespace into spaces, collapse whitespace runs,
    and fall back to `default` when nothing usable is left. Keeps a user-typed
    INSERT/decal name from escaping its library folder or producing an invalid
    path. Pure stdlib so it is unit-tested; shared by the decal and asset
    export paths."""
    cleaned = []
    for ch in str(name):
        if ch in '/\\:*?"<>|':
            continue
        cleaned.append(' ' if ch in '\r\n\t' else ch)
    stem = " ".join("".join(cleaned).split()).strip('.')
    return stem or default


def aspect_size(img_w, img_h, longest):
    """Fit an image of (img_w x img_h) pixels into a decal whose longest side is
    `longest` meters, preserving aspect ratio. Returns (width, height) in meters.

    Degenerate inputs (a zero dimension) fall back to a square so a placement
    never collapses to a zero-area quad."""
    if img_w <= 0 or img_h <= 0 or longest <= 0:
        return (longest, longest)
    if img_w >= img_h:
        return (longest, longest * img_h / img_w)
    return (longest * img_w / img_h, longest)
