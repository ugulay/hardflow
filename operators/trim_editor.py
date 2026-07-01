# Trim-sheet UV editor (v1.16).
#
# A trim sheet is one image carved into named rectangles ("regions"); a decal
# then borrows one region's UV sub-rect. The old workflow only offered an EQUAL
# cols x rows grid. This module adds free, unequal cutting: an interactive
# viewport editor where you drag out rectangles, resize them by their handles,
# move them, and split them (guillotine) -- UV-style cutting at any size.
#
# Architecture: all the rect math is pure in core/atlas.py (unit-tested); this
# module is the thin bpy/modal shell. Regions are stored on the Image datablock
# (bpy.types.Image.hardflow_trim) so they save with the .blend and travel with
# the sheet. The scene keeps a pointer to the "active" sheet image
# (Scene.hardflow_trim_image) so the N-panel and the placement ops can find it.
import bpy
from bpy.types import Operator, PropertyGroup
from bpy.props import (BoolProperty, CollectionProperty, FloatProperty,
                       IntProperty, StringProperty)
from bpy_extras.io_utils import ImportHelper

from ..core import atlas
from ..ui import draw as hud
from . import decals


# --- stored data model -------------------------------------------------------

class HARDFLOW_TrimRegion(PropertyGroup):
    """One named UV rectangle on a trim sheet, in [0,1] space (v up)."""
    name: StringProperty(default="Region")
    u0: FloatProperty(default=0.0, min=0.0, max=1.0)
    v0: FloatProperty(default=0.0, min=0.0, max=1.0)
    u1: FloatProperty(default=1.0, min=0.0, max=1.0)
    v1: FloatProperty(default=1.0, min=0.0, max=1.0)


class HARDFLOW_TrimSheet(PropertyGroup):
    """The region set stored on an Image (bpy.types.Image.hardflow_trim)."""
    regions: CollectionProperty(type=HARDFLOW_TrimRegion)
    active: IntProperty(default=0)


# --- shared helpers ----------------------------------------------------------

def sheet_image(context, name=""):
    """The trim-sheet image to act on: an explicit name wins, else the scene's
    active trim sheet (Scene.hardflow_trim_image). None when neither resolves."""
    if name:
        return bpy.data.images.get(name)
    return getattr(context.scene, "hardflow_trim_image", None)


def _rect(region):
    return (region.u0, region.v0, region.u1, region.v1)


def _write(region, rect):
    region.u0, region.v0, region.u1, region.v1 = rect


def _unique_name(regions, base="R"):
    """A region name not already in the collection (R0, R1, ...)."""
    existing = {r.name for r in regions}
    i = 0
    while "%s%d" % (base, i) in existing:
        i += 1
    return "%s%d" % (base, i)


def _seed_full(trim):
    """Give an empty sheet one whole-sheet region so the editor has something to
    grab and split."""
    r = trim.regions.add()
    r.name = "R0"
    _write(r, (0.0, 0.0, 1.0, 1.0))
    trim.active = 0


# --- the interactive editor --------------------------------------------------

class HARDFLOW_OT_trim_editor(Operator):
    bl_idname = "object.hardflow_trim_editor"
    bl_label = "Trim Sheet Editor"
    bl_description = ("Carve a trim sheet into custom UV rectangles: LMB drag = "
                      "new region, drag handles = resize, C = split, X = delete")
    bl_options = {'REGISTER', 'UNDO'}

    image_name: StringProperty()

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        self._image = sheet_image(context, self.image_name)
        if self._image is None:
            self.report({'WARNING'}, "Pick or load a trim-sheet image first")
            return {'CANCELLED'}
        trim = self._image.hardflow_trim
        if len(trim.regions) == 0:
            _seed_full(trim)
        # Snapshot for a clean Esc-cancel (region edits are plain data).
        self._snapshot = [(r.name, _rect(r)) for r in trim.regions]
        self._texture = None       # built lazily on first draw (needs a GPU)
        self._snap = True
        self._div = 16             # snap lattice = 1/div per axis
        self._drag = None          # {'mode': NEW/RESIZE/MOVE, ...}
        self._mouse = (0, 0)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    # -- geometry / coordinate mapping --

    def _canvas(self, region):
        """The screen-space box the sheet is drawn in: a centered square fit to
        the image's aspect. Returns (x, y, w, h)."""
        rw, rh = region.width, region.height
        box = min(rw, rh) * 0.72
        aw, ah = self._image.size[0], self._image.size[1]
        aspect = (aw / ah) if (aw and ah) else 1.0
        if aspect >= 1.0:
            cw, ch = box, box / aspect
        else:
            cw, ch = box * aspect, box
        return ((rw - cw) * 0.5, (rh - ch) * 0.5, cw, ch)

    def _to_uv(self, region, sx, sy):
        cx, cy, cw, ch = self._canvas(region)
        if cw <= 0 or ch <= 0:
            return (0.0, 0.0)
        return ((sx - cx) / cw, (sy - cy) / ch)

    def _to_screen(self, region, u, v):
        cx, cy, cw, ch = self._canvas(region)
        return (cx + u * cw, cy + v * ch)

    def _pixel_tol(self, region):
        cx, cy, cw, ch = self._canvas(region)
        return (12.0 / cw) if cw > 0 else 0.03

    @property
    def _step(self):
        return (1.0 / self._div) if self._snap else 0.0

    # -- region access --

    def _trim(self):
        return self._image.hardflow_trim

    def _regions(self):
        return self._image.hardflow_trim.regions

    def _active(self):
        regs = self._regions()
        i = self._trim().active
        return regs[i] if 0 <= i < len(regs) else None

    def _snap_uv(self, uv):
        s = self._step
        return (atlas.snap_value(uv[0], s), atlas.snap_value(uv[1], s))

    # -- modal --

    def modal(self, context, event):
        context.area.tag_redraw()
        region = context.region

        if event.type == 'MOUSEMOVE':
            self._mouse = (event.mouse_region_x, event.mouse_region_y)
            if self._drag is not None:
                self._update_drag(region)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self._begin_drag(region, event)

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._finish_drag()

        elif event.type == 'TAB' and event.value == 'PRESS':
            regs = self._regions()
            if len(regs):
                self._trim().active = (self._trim().active + 1) % len(regs)

        elif event.type in {'X', 'DEL', 'BACK_SPACE'} and event.value == 'PRESS':
            self._delete_active()

        elif event.type == 'C' and event.value == 'PRESS':
            self._split_active(region, 'V' if event.shift else 'U')

        elif event.type == 'A' and event.value == 'PRESS':
            self._add_region((0.25, 0.25, 0.75, 0.75))

        elif event.type == 'G' and event.value == 'PRESS':
            self._snap = not self._snap

        elif event.type in {'RIGHT_BRACKET', 'WHEELUPMOUSE'} and event.value == 'PRESS':
            self._div = min(self._div + (2 if self._div < 16 else 4), 64)

        elif event.type in {'LEFT_BRACKET', 'WHEELDOWNMOUSE'} and event.value == 'PRESS':
            self._div = max(self._div - (2 if self._div <= 16 else 4), 2)

        elif event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            return self._confirm(context)

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            return self._cancel(context)

        elif event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def _begin_drag(self, region, event):
        uv = self._to_uv(region, *self._mouse)
        regs = self._regions()
        tol = self._pixel_tol(region)
        # 1) a resize handle of the active region?
        act = self._active()
        if act is not None:
            h = atlas.nearest_handle(_rect(act), uv[0], uv[1], tol)
            if h is not None and h != 'MOVE':
                self._drag = {'mode': 'RESIZE', 'handle': h}
                return
        # 2) inside an existing region -> select + move it
        idx = atlas.rect_at_point([_rect(r) for r in regs], uv[0], uv[1])
        if idx >= 0:
            self._trim().active = idx
            self._drag = {'mode': 'MOVE', 'last': uv}
            return
        # 3) empty canvas -> draw a new region from here
        anchor = self._snap_uv(uv)
        reg = regs.add()
        reg.name = _unique_name(regs)
        _write(reg, (anchor[0], anchor[1], anchor[0], anchor[1]))
        self._trim().active = len(regs) - 1
        self._drag = {'mode': 'NEW', 'anchor': anchor}

    def _update_drag(self, region):
        act = self._active()
        if act is None or self._drag is None:
            return
        mode = self._drag['mode']
        uv = self._to_uv(region, *self._mouse)
        if mode == 'MOVE':
            last = self._drag['last']
            _write(act, atlas.move_rect(_rect(act), uv[0] - last[0],
                                        uv[1] - last[1]))
            self._drag['last'] = uv
            return
        uv = self._snap_uv(uv)
        if mode == 'NEW':
            ax, ay = self._drag['anchor']
            _write(act, atlas.normalize_rect((ax, ay, uv[0], uv[1])))
        elif mode == 'RESIZE':
            _write(act, atlas.resize_rect(_rect(act), self._drag['handle'],
                                          uv[0], uv[1]))

    def _finish_drag(self):
        act = self._active()
        if act is not None and self._drag is not None:
            rect = atlas.snap_rect(_rect(act), self._step)
            # a click with no real drag leaves a zero-area new region -> drop it
            if self._drag['mode'] == 'NEW' and atlas.rect_area(rect) < 1e-5:
                self._delete_active()
            else:
                _write(act, rect)
        self._drag = None

    def _add_region(self, rect):
        regs = self._regions()
        reg = regs.add()
        reg.name = _unique_name(regs)
        _write(reg, atlas.normalize_rect(rect))
        self._trim().active = len(regs) - 1

    def _delete_active(self):
        regs = self._regions()
        i = self._trim().active
        if 0 <= i < len(regs):
            regs.remove(i)
            self._trim().active = min(i, len(regs) - 1)

    def _split_active(self, region, axis):
        act = self._active()
        if act is None:
            return
        rect = _rect(act)
        u0, v0, u1, v1 = rect
        uv = self._to_uv(region, *self._mouse)
        if axis == 'U':
            t = (uv[0] - u0) / (u1 - u0) if u1 > u0 else 0.5
        else:
            t = (uv[1] - v0) / (v1 - v0) if v1 > v0 else 0.5
        a, b = atlas.guillotine_split(rect, axis, t)
        _write(act, a)
        self._add_region(b)

    def _confirm(self, context):
        self._cleanup(context)
        n = len(self._regions())
        self.report({'INFO'}, "Trim sheet '%s': %d region(s)"
                    % (self._image.name, n))
        return {'FINISHED'}

    def _cancel(self, context):
        regs = self._regions()
        regs.clear()
        for name, rect in self._snapshot:
            r = regs.add()
            r.name = name
            _write(r, rect)
        self._trim().active = 0
        self._cleanup(context)
        return {'CANCELLED'}

    def _cleanup(self, context):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        if context.area is not None:
            context.area.tag_redraw()

    # -- drawing --

    def _draw_px(self, context):
        region = context.region
        if self._image is None:
            return
        cx, cy, cw, ch = self._canvas(region)
        # dark backdrop for contrast against the viewport
        hud.draw_rect_fill(cx - 8, cy - 8, cw + 16, ch + 16, (0.0, 0.0, 0.0, 0.85))
        try:
            if self._texture is None:
                import gpu
                self._texture = gpu.texture.from_image(self._image)
            hud.draw_image(self._texture, cx, cy, cw, ch)
        except Exception:  # noqa: BLE001 -- never let a draw error kill the modal
            pass

        if self._step > 0:
            segs = []
            n = self._div
            for i in range(n + 1):
                x = cx + (i / n) * cw
                segs += [(x, cy), (x, cy + ch)]
                y = cy + (i / n) * ch
                segs += [(cx, y), (cx + cw, y)]
            hud.draw_grid(segs, (1.0, 1.0, 1.0, 0.08))

        active_i = self._trim().active
        for i, r in enumerate(self._regions()):
            rect = _rect(r)
            u0, v0, u1, v1 = rect
            pts = [self._to_screen(region, *c) for c in
                   ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
            active = (i == active_i)
            hud.draw_face_fill(pts, (0.15, 0.8, 1.0, 0.18) if active
                               else (1.0, 1.0, 1.0, 0.05))
            hud.draw_shape(pts, (0.2, 0.85, 1.0, 1.0) if active
                           else (1.0, 1.0, 1.0, 0.55), closed=True,
                           width=2.0 if active else 1.0)
            lx, ly = self._to_screen(region, u0, v1)
            hud.draw_text(lx + 4, ly - 16, r.name,
                          (0.2, 0.85, 1.0, 1.0) if active
                          else (0.85, 0.85, 0.85, 1.0), size=12)
            if active:
                handles = atlas.rect_handle_points(rect)
                hud.draw_points([self._to_screen(region, *p)
                                 for p in handles.values()],
                                (1.0, 0.9, 0.2, 1.0), size=8.0)

        self._draw_hud(region)

    def _draw_hud(self, region):
        lines = [
            "LMB drag: new region · click: select · handles: resize",
            "C: split │ · Shift+C: split ─ · X: delete · A: add · Tab: next",
            "Snap: %s (1/%d) — G toggle · [ ] / wheel density"
            % ("on" if self._snap else "off", self._div),
        ]
        act = self._active()
        if act is not None:
            aw, ah = self._image.size[0], self._image.size[1]
            pw, ph = atlas.rect_pixels(_rect(act), aw or 0, ah or 0)
            lines.append(("Region '%s':  %d × %d px" % (act.name,
                          round(pw), round(ph)), (1.0, 0.9, 0.2, 1.0)))
        lines.append("Enter: apply · Esc: cancel")
        hud.draw_hud(region, lines, title="Trim Sheet Editor")


# --- region management ops (N-panel) -----------------------------------------

class HARDFLOW_OT_load_trim_image(Operator, ImportHelper):
    bl_idname = "object.hardflow_load_trim_image"
    bl_label = "Load Trim Sheet"
    bl_description = ("Load an image and make it the active trim sheet to edit "
                      "into custom UV regions")
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.tga;*.tif;*.tiff;*.bmp;*.exr;*.hdr;*.webp",
        options={'HIDDEN'},
    )
    open_editor: BoolProperty(default=True)

    def execute(self, context):
        try:
            img = bpy.data.images.load(self.filepath, check_existing=True)
        except RuntimeError as ex:
            self.report({'ERROR'}, "Could not load image: %s" % ex)
            return {'CANCELLED'}
        context.scene.hardflow_trim_image = img
        if len(img.hardflow_trim.regions) == 0:
            _seed_full(img.hardflow_trim)
        if self.open_editor:
            return _launch_editor(context, self, img.name)
        return {'FINISHED'}


def _launch_editor(context, op, image_name):
    """Start the modal editor in a 3D viewport, overriding context when the
    caller runs from a file browser / button elsewhere."""
    win = context.window
    area = (context.area if (context.area and context.area.type == 'VIEW_3D')
            else None)
    if area is None and win is not None:
        area = next((a for a in win.screen.areas if a.type == 'VIEW_3D'), None)
    region = (next((r for r in area.regions if r.type == 'WINDOW'), None)
              if area else None)
    if area is None or region is None:
        op.report({'WARNING'}, "Open a 3D viewport to edit the trim sheet")
        return {'CANCELLED'}
    with context.temp_override(window=win, area=area, region=region):
        result = bpy.ops.object.hardflow_trim_editor('INVOKE_DEFAULT',
                                                     image_name=image_name)
    return {'CANCELLED'} if result == {'CANCELLED'} else {'FINISHED'}


class HARDFLOW_OT_trim_region_add(Operator):
    bl_idname = "object.hardflow_trim_region_add"
    bl_label = "Add Region"
    bl_description = "Add a new UV region to the active trim sheet"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        img = sheet_image(context)
        if img is None:
            self.report({'WARNING'}, "No active trim sheet")
            return {'CANCELLED'}
        trim = img.hardflow_trim
        reg = trim.regions.add()
        reg.name = _unique_name(trim.regions)
        _write(reg, (0.25, 0.25, 0.75, 0.75))
        trim.active = len(trim.regions) - 1
        return {'FINISHED'}


class HARDFLOW_OT_trim_region_remove(Operator):
    bl_idname = "object.hardflow_trim_region_remove"
    bl_label = "Remove Region"
    bl_description = "Remove this UV region from the active trim sheet"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        img = sheet_image(context)
        if img is None:
            return {'CANCELLED'}
        trim = img.hardflow_trim
        i = self.index if self.index >= 0 else trim.active
        if 0 <= i < len(trim.regions):
            trim.regions.remove(i)
            trim.active = min(i, len(trim.regions) - 1)
        return {'FINISHED'}


class HARDFLOW_OT_trim_grid_regions(Operator):
    bl_idname = "object.hardflow_trim_grid_regions"
    bl_label = "Regions from Grid"
    bl_description = ("Fill the active trim sheet with an equal cols × rows grid "
                      "of regions (a starting point to then tweak by hand)")
    bl_options = {'REGISTER', 'UNDO'}

    cols: IntProperty(name="Columns", default=4, min=1, max=64)
    rows: IntProperty(name="Rows", default=4, min=1, max=64)
    replace: BoolProperty(name="Replace Existing", default=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        img = sheet_image(context)
        if img is None:
            self.report({'WARNING'}, "No active trim sheet")
            return {'CANCELLED'}
        trim = img.hardflow_trim
        if self.replace:
            trim.regions.clear()
        for idx, rect in enumerate(atlas.slice_grid(self.cols, self.rows)):
            reg = trim.regions.add()
            reg.name = _unique_name(trim.regions)
            _write(reg, rect)
        trim.active = 0
        return {'FINISHED'}


class HARDFLOW_OT_place_trim_region(Operator):
    bl_idname = "object.hardflow_place_trim_region"
    bl_label = "Place Region"
    bl_description = ("Place this trim-sheet region as a decal on the surface "
                      "under the cursor (cycle regions with Up/Down)")
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        img = sheet_image(context)
        if img is None or len(img.hardflow_trim.regions) == 0:
            self.report({'WARNING'}, "No trim regions to place")
            return {'CANCELLED'}
        idx = self.index if self.index >= 0 else img.hardflow_trim.active
        return decals._invoke_place(context, self, image_name=img.name,
                                    region_index=max(0, idx))


class HARDFLOW_OT_retrim_region(Operator):
    bl_idname = "object.hardflow_retrim_region"
    bl_label = "Apply Region to Decal"
    bl_description = ("Rewrite the selected decal's UVs to this trim-sheet "
                      "region (re-trim without re-placing)")
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=-1)

    def execute(self, context):
        from ..core import decal
        img = sheet_image(context)
        if img is None or len(img.hardflow_trim.regions) == 0:
            self.report({'WARNING'}, "No trim regions")
            return {'CANCELLED'}
        deco = decals._get_decal(context, "")
        if deco is None:
            self.report({'WARNING'}, "Select a Hardflow decal first")
            return {'CANCELLED'}
        trim = img.hardflow_trim
        i = self.index if self.index >= 0 else trim.active
        r = trim.regions[i % len(trim.regions)]
        rect = atlas.normalize_rect(_rect(r))
        if not decal.set_decal_uv_rect(deco, rect):
            self.report({'WARNING'}, "Decal has no UV map")
            return {'CANCELLED'}
        self.report({'INFO'}, "Re-trimmed '%s' to region '%s'"
                    % (deco.name, r.name))
        return {'FINISHED'}
