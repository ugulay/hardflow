# Game-ready audit: measure the mesh, report what an engine will object to,
# and offer the one-click fix for each thing that can safely be fixed.
#
# Layer split as usual: this file only *measures* (bmesh counts, areas, the
# signed volume) and *acts* (the fixes). Every pass/warn/fail decision and
# every phrasing lives in the pure core/gameready.py, where the rules are
# tested without Blender.
#
# The findings are cached per object in a module dict rather than stored on the
# scene: a report is transient (it is stale the moment you edit the mesh), it
# should not travel in the .blend, and the panel must not re-measure a heavy
# mesh on every redraw.
import bmesh
import bpy
from bpy.types import Operator
from bpy.props import StringProperty

from ..core import gameready
from ..preferences import get_prefs

# object name -> (list of findings, measurement dict)
_REPORTS = {}


def report_for(obj):
    """The cached findings for `obj`, or None when it has not been audited."""
    if obj is None:
        return None
    entry = _REPORTS.get(obj.name)
    return entry[0] if entry else None


def clear_reports():
    _REPORTS.clear()


def _texture_size(obj, fallback):
    """The largest image size used by the object's materials, so texel density
    is measured against the texture the model will actually ship with.
    Falls back to the preference when the object has no image texture yet."""
    best = 0
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None or not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            img = getattr(node, "image", None)
            if img is not None and img.size[0]:
                best = max(best, int(img.size[0]), int(img.size[1]))
    return best or fallback


def measure(obj):
    """Gather everything the pure rules need, in one bmesh pass.

    Object Mode only: it reads obj.data directly, which in Edit Mode would be
    the stale pre-edit copy."""
    me = obj.data
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()

        tris = quads = ngons = 0
        world_area = 0.0
        uv_area = 0.0
        uv_faces = 0
        out_of_bounds = 0
        tri_soup = []
        # Scale the areas by the object's scale so the density matches what
        # the engine sees, not the unapplied local size.
        sx, sy, sz = (abs(v) for v in obj.scale)
        area_scale = ((sx * sy) + (sy * sz) + (sx * sz)) / 3.0 or 1.0

        uv_layer = bm.loops.layers.uv.active
        for f in bm.faces:
            n = len(f.verts)
            if n == 3:
                tris += 1
            elif n == 4:
                quads += 1
            else:
                ngons += 1
            world_area += f.calc_area() * area_scale
            # Fan-triangulate for the volume sum; exact for convex faces and
            # close enough for the sign on anything a boolean leaves behind.
            co = [v.co for v in f.verts]
            for i in range(1, n - 1):
                tri_soup.append(((co[0].x, co[0].y, co[0].z),
                                 (co[i].x, co[i].y, co[i].z),
                                 (co[i + 1].x, co[i + 1].y, co[i + 1].z)))
            if uv_layer is not None:
                uvs = [l[uv_layer].uv for l in f.loops]
                a = 0.0
                for i in range(len(uvs)):
                    u0, v0 = uvs[i]
                    u1, v1 = uvs[(i + 1) % len(uvs)]
                    a += u0 * v1 - u1 * v0
                a = abs(a) * 0.5
                uv_area += a
                if a > 1e-12:
                    uv_faces += 1
                if any(u < -1e-6 or u > 1.0 + 1e-6 or v < -1e-6
                       or v > 1.0 + 1e-6 for u, v in uvs):
                    out_of_bounds += 1

        non_manifold = sum(1 for e in bm.edges if not e.is_manifold
                           and len(e.link_faces) > 2)
        boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
        loose_verts = sum(1 for v in bm.verts if not v.link_edges)
        loose_edges = sum(1 for e in bm.edges if not e.link_faces)
        closed = (non_manifold == 0 and boundary == 0 and len(bm.faces) > 0)

        return {
            'scale': tuple(obj.scale),
            'closed': closed,
            'volume': gameready.signed_volume(tri_soup) if closed else 0.0,
            'non_manifold_edges': non_manifold,
            'boundary_edges': boundary,
            'tris': tris, 'quads': quads, 'ngons': ngons,
            'total_faces': len(bm.faces),
            'loose_verts': loose_verts, 'loose_edges': loose_edges,
            'has_uv': uv_layer is not None,
            'uv_faces': uv_faces,
            'uv_area': uv_area,
            'uv_out_of_bounds': out_of_bounds,
            'world_area': world_area,
        }
    finally:
        bm.free()


class HARDFLOW_OT_audit(Operator):
    bl_idname = "object.hardflow_audit"
    bl_label = "Game-Ready Audit"
    bl_description = ("Check the selected mesh(es) for what an engine will "
                      "object to: unapplied scale, inverted normals, "
                      "non-manifold geometry, n-gons, loose geometry, missing "
                      "UVs and texel density")
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT'
                and any(o.type == 'MESH' for o in context.selected_objects))

    def execute(self, context):
        prefs = get_prefs(context)
        targets = [o for o in context.selected_objects if o.type == 'MESH']
        worst = gameready.OK
        for obj in targets:
            try:
                m = measure(obj)
                rows = gameready.audit(
                    m, target_texel=prefs.gameready_texel_target,
                    texture_size=_texture_size(obj,
                                               prefs.gameready_texture_size))
            except Exception as ex:  # noqa: BLE001 -- one bad mesh can't abort
                self.report({'WARNING'}, "Audit failed on %s: %s"
                            % (obj.name, ex))
                continue
            _REPORTS[obj.name] = (rows, m)
            if gameready._RANK[gameready.worst(rows)] > gameready._RANK[worst]:
                worst = gameready.worst(rows)
        if not _REPORTS:
            self.report({'ERROR'}, "Audit: nothing measured")
            return {'CANCELLED'}
        active = context.active_object
        rows = report_for(active) or []
        _lvl, ok, warn, fail = gameready.summary(rows)
        self.report({'INFO'}, "Audit %s: %d ok, %d warning(s), %d problem(s)"
                    % (active.name if active else "", ok, warn, fail))
        return {'FINISHED'}


class HARDFLOW_OT_audit_fix(Operator):
    bl_idname = "object.hardflow_audit_fix"
    bl_label = "Fix"
    bl_description = "Apply the fix for this audit finding"
    bl_options = {'REGISTER', 'UNDO'}

    fix: StringProperty(options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (context.mode == 'OBJECT' and obj is not None
                and obj.type == 'MESH')

    def execute(self, context):
        obj = context.active_object
        handler = {
            gameready.FIX_SCALE: self._apply_scale,
            gameready.FIX_NORMALS: self._recalc_normals,
            gameready.FIX_NGONS: self._triangulate_ngons,
            gameready.FIX_LOOSE: self._delete_loose,
            gameready.FIX_SELECT_NONMANIFOLD: self._select_non_manifold,
            gameready.FIX_UNWRAP: self._unwrap,
        }.get(self.fix)
        if handler is None:
            self.report({'ERROR'}, "Unknown fix '%s'" % self.fix)
            return {'CANCELLED'}
        try:
            message = handler(context, obj)
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, "Fix failed: %s" % ex)
            return {'CANCELLED'}
        # The report is stale the moment the mesh changes -- re-measure so the
        # panel shows the result of the fix rather than the problem it solved.
        try:
            prefs = get_prefs(context)
            m = measure(obj)
            _REPORTS[obj.name] = (
                gameready.audit(m, target_texel=prefs.gameready_texel_target,
                                texture_size=_texture_size(
                                    obj, prefs.gameready_texture_size)), m)
        except Exception:  # noqa: BLE001
            _REPORTS.pop(obj.name, None)
        self.report({'INFO'}, message)
        return {'FINISHED'}

    # --- the fixes --------------------------------------------------------

    @staticmethod
    def _apply_scale(context, obj):
        with context.temp_override(active_object=obj, selected_objects=[obj],
                                   selected_editable_objects=[obj],
                                   object=obj):
            bpy.ops.object.transform_apply(location=False, rotation=False,
                                           scale=True)
        return "Scale applied"

    @staticmethod
    def _recalc_normals(context, obj):
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(obj.data)
        finally:
            bm.free()
        obj.data.update()
        return "Normals recalculated outward"

    @staticmethod
    def _triangulate_ngons(context, obj):
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            ngons = [f for f in bm.faces if len(f.verts) > 4]
            if not ngons:
                return "No n-gons left"
            bmesh.ops.triangulate(bm, faces=ngons)
            bm.to_mesh(obj.data)
        finally:
            bm.free()
        obj.data.update()
        return "Triangulated %d n-gon(s)" % len(ngons)

    @staticmethod
    def _delete_loose(context, obj):
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            verts = [v for v in bm.verts if not v.link_edges]
            edges = [e for e in bm.edges if not e.link_faces]
            bmesh.ops.delete(bm, geom=edges, context='EDGES')
            bmesh.ops.delete(bm, geom=verts, context='VERTS')
            bm.to_mesh(obj.data)
        finally:
            bm.free()
        obj.data.update()
        return "Removed %d vert(s) and %d wire edge(s)" % (len(verts),
                                                           len(edges))

    @staticmethod
    def _select_non_manifold(context, obj):
        """Non-manifold geometry is NOT auto-fixed: merging or deleting it is a
        modelling decision. Select it in Edit Mode so it can be looked at."""
        with context.temp_override(active_object=obj, object=obj):
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.mesh.select_mode(type='EDGE')
            bpy.ops.mesh.select_non_manifold()
        return "Non-manifold edges selected in Edit Mode"

    @staticmethod
    def _unwrap(context, obj):
        """Hardflow's own cut-aware unwrap rather than a bare Smart UV
        Project: on a boolean model the seams belong on the cuts, and the
        marks that say where those are already exist on the mesh."""
        with context.temp_override(active_object=obj, object=obj,
                                   selected_objects=[obj],
                                   selected_editable_objects=[obj]):
            bpy.ops.mesh.hardflow_unwrap()
        return "Unwrapped along the cut seams"
