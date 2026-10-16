"""Shared helpers for build_scene.py: collections, materials, mesh builders, Poly Haven append.
Project layout: <project>/blender/*.py, <project>/assets/{ph,tex,hdri,ai}/ (see tools/fetch_ph.py)."""
import bpy, bmesh, math, os
from mathutils import Vector

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))


def A(*p):
    return os.path.join(ROOT, 'assets', *p)


def coll(name, exclude=False):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
        if exclude:
            bpy.context.view_layer.layer_collection.children[c.name].exclude = True
    return c


def link(ob, collection):
    coll(collection).objects.link(ob)
    return ob


# ---------- materials ----------
def img(path, non_color=False):
    im = bpy.data.images.load(path, check_existing=True)
    if non_color:
        im.colorspace_settings.name = 'Non-Color'
    return im


def mat(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, inputs=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    for k, v in (inputs or {}).items():
        b.inputs[k].default_value = v
    return m


def noise_rough(m, lo, hi, scale=4.0):
    """Drive roughness with large soft noise so a surface never reads as one flat sheen."""
    nt = m.node_tree; L = nt.links.new
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale; nz.inputs['Detail'].default_value = 3
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value, mr.inputs['To Max'].default_value = lo, hi
    L(nz.outputs['Fac'], mr.inputs['Value']); L(mr.outputs['Result'], nt.nodes['Principled BSDF'].inputs['Roughness'])
    return m


def pbr(name, tex, scale=1.0, tint=None, rough=None, bump=0.4, coord='UV', grey=None, var=1.0):
    """Poly Haven texture set (assets/tex/<tex>_{Diffuse,Rough,nor_gl}.jpg). UVs are in metres, scale = repeats per metre.
    grey=(r, g, b): keep only the texture's light/dark variation around that linear albedo (drops the texture's own hue)."""
    m = mat(name)
    nt = m.node_tree; b = nt.nodes['Principled BSDF']; L = nt.links.new
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (scale, scale, scale)
    L(tc.outputs[coord], mp.inputs['Vector'])

    def tex_node(kind, nc):
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = img(A('tex', f'{tex}_{kind}.jpg'), nc)
        L(mp.outputs['Vector'], n.inputs['Vector'])
        return n

    dn = tex_node('Diffuse', False)
    col = dn.outputs['Color']
    if grey:
        import numpy as np
        px = np.empty(len(dn.image.pixels), np.float32); dn.image.pixels.foreach_get(px)
        mean = float((px.reshape(-1, 4)[:, :3] @ np.array([0.2126, 0.7152, 0.0722], np.float32)).mean())
        bw = nt.nodes.new('ShaderNodeRGBToBW'); L(col, bw.inputs['Color'])
        soft = nt.nodes.new('ShaderNodeMapRange')              # var < 1 flattens the texture's blotches toward its mean
        soft.inputs['To Min'].default_value = mean * (1 - var); soft.inputs['To Max'].default_value = mean * (1 - var) + var
        L(bw.outputs['Val'], soft.inputs['Value'])
        vm = nt.nodes.new('ShaderNodeVectorMath'); vm.operation = 'SCALE'
        vm.inputs[0].default_value = tuple(g / mean for g in grey)
        L(soft.outputs['Result'], vm.inputs['Scale']); col = vm.outputs['Vector']
    if tint:
        vm = nt.nodes.new('ShaderNodeVectorMath'); vm.operation = 'MULTIPLY'
        vm.inputs[1].default_value = tint
        L(col, vm.inputs[0]); col = vm.outputs['Vector']
    L(col, b.inputs['Base Color'])
    rc = tex_node('Rough', True).outputs['Color']
    if rough:
        mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['To Min'].default_value, mr.inputs['To Max'].default_value = rough
        L(rc, mr.inputs['Value']); rc = mr.outputs['Result']
    L(rc, b.inputs['Roughness'])
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = bump
    L(tex_node('nor_gl', True).outputs['Color'], nm.inputs['Color']); L(nm.outputs['Normal'], b.inputs['Normal'])
    return m


def glass(name, color=(1, 1, 1), ior=1.5, rough=0.0):
    """Clear dielectric. Shadow rays see a Transparent BSDF so glass with caustics off still lets light through."""
    m = mat(name, color, rough, inputs={'Transmission Weight': 1.0, 'IOR': ior})
    nt = m.node_tree; L = nt.links.new
    out = nt.nodes['Material Output']; b = nt.nodes['Principled BSDF']
    lp = nt.nodes.new('ShaderNodeLightPath'); tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
    tr.inputs['Color'].default_value = (*color, 1)
    L(lp.outputs['Is Shadow Ray'], mx.inputs['Fac']); L(b.outputs['BSDF'], mx.inputs[1]); L(tr.outputs['BSDF'], mx.inputs[2])
    L(mx.outputs['Shader'], out.inputs['Surface'])
    return m


def image_mat(name, path, rough=0.7):
    m = mat(name, rough=rough)
    nt = m.node_tree
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(path)
    nt.links.new(t.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color'])
    return m


# ---------- mesh builders ----------
def _finish(name, bm, materials, collection, smooth=False):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in materials:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return link(ob, collection)


def _planar_uv(bm, offset=(0, 0, 0)):
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        ax = max(range(3), key=lambda a: abs(f.normal[a]))
        ua, va = [(1, 2), (0, 2), (0, 1)][ax]
        for l in f.loops:
            l[uv].uv = (l.vert.co[ua] + offset[ua], l.vert.co[va] + offset[va])


def _add_box(bm, size, center, bevel=0.0):
    sx, sy, sz = (s / 2 for s in size)
    cx, cy, cz = center
    vs = [bm.verts.new((cx + x, cy + y, cz + z)) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
    fs = [bm.faces.new([vs[i] for i in idx]) for idx in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))]
    bmesh.ops.recalc_face_normals(bm, faces=fs)
    if bevel:
        edges = list({e for f in fs for e in f.edges})
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=2, affect='EDGES', profile=0.5)


def boxes(name, items, material, collection='Room', bevel=0.0):
    """Many boxes in one mesh. items = [(size, center)], world coordinates, UVs in metres."""
    bm = bmesh.new()
    for size, center in items:
        _add_box(bm, size, center, bevel)
    bm.normal_update()
    _planar_uv(bm)
    return _finish(name, bm, [material], collection, smooth=bool(bevel))


def box(name, size, center, material, collection='Room', bevel=0.0):
    return boxes(name, [(size, center)], material, collection, bevel)


def lathe(name, profile, loc, material, collection='Props', segments=48, smooth=True, caps=True):
    """Revolve a (radius, z) profile around Z. Profile ends at r = 0 make closed solids; caps=False leaves open rims."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r < 1e-6:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for a in (2 * math.pi * s / segments for s in range(segments))])
    for a, b in zip(rings, rings[1:]):
        for s in range(segments):
            s2 = (s + 1) % segments
            if len(a) == 1 and len(b) == 1:
                break
            if len(a) == 1:
                bm.faces.new((a[0], b[s2], b[s]))
            elif len(b) == 1:
                bm.faces.new((a[s], a[s2], b[0]))
            else:
                bm.faces.new((a[s], a[s2], b[s2], b[s]))
    for ring in (rings[0], rings[-1]):
        if caps and len(ring) > 1:
            bm.faces.new(ring)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for l in f.loops:
            c = l.vert.co
            l[uv].uv = (math.atan2(c.y, c.x) / (2 * math.pi), c.z)
    ob = _finish(name, bm, [material], collection)
    ob.location = loc
    if smooth:
        for p in ob.data.polygons:
            p.use_smooth = abs(p.normal.z) < 0.98
    return ob


def arc_solid(name, center, r_in, r_out, a0, a1, z0, z1, material, collection='Room', segs=96):
    """Solid band between two arcs around `center` (x, y). Angles in radians, 0 = -Y (towards the camera)."""
    cx, cy = center
    bm = bmesh.new()
    P = lambda r, a, z: bm.verts.new((cx + r * math.sin(a), cy - r * math.cos(a), z))
    rows = []
    for i in range(segs + 1):
        a = a0 + (a1 - a0) * i / segs
        rows.append([P(r_out, a, z0), P(r_out, a, z1), P(r_in, a, z1), P(r_in, a, z0)])
    for r0, r1 in zip(rows, rows[1:]):
        for k in range(4):
            bm.faces.new((r0[k], r1[k], r1[(k + 1) % 4], r0[(k + 1) % 4]))
    bm.faces.new(rows[0][::-1]); bm.faces.new(rows[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uv = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        flat = abs(f.normal.z) > 0.9
        for l in f.loops:
            c = l.vert.co
            ang = math.atan2(c.x - cx, cy - c.y)
            l[uv].uv = (c.x, c.y) if flat else (ang * r_out, c.z)
    return _finish(name, bm, [material], collection)


def flutes(name, center, radius, a0, a1, z0, z1, width, material, collection='Room', segs=8):
    """Half-round vertical flutes standing on an arc (fluted bar front). Grain runs along Z."""
    cx, cy = center
    n = int((a1 - a0) * radius / width)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    rr = width / 2
    for i in range(n):
        a = a0 + (i + 0.5) * (a1 - a0) / n
        out = Vector((math.sin(a), -math.cos(a), 0)); tan = Vector((math.cos(a), math.sin(a), 0))
        base = Vector((cx, cy, 0)) + out * radius
        ring = []
        for s in range(segs + 1):
            t = math.pi * s / segs
            p = base + tan * (-rr * math.cos(t)) + out * (rr * 0.8 * math.sin(t))
            ring.append((bm.verts.new((p.x, p.y, z0)), bm.verts.new((p.x, p.y, z1))))
        for s in range(segs):
            (a_lo, a_hi), (b_lo, b_hi) = ring[s], ring[s + 1]
            f = bm.faces.new((a_lo, b_lo, b_hi, a_hi))
            u0 = (a * radius) + (s / segs - 0.5) * width
            u1 = (a * radius) + ((s + 1) / segs - 0.5) * width
            for l, (u, v) in zip(f.loops, ((u0, z0), (u1, z0), (u1, z1), (u0, z1))):
                l[uv].uv = (u * 3.0 + i * 0.37, v)          # shift each slat so neighbours don't share grain
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = _finish(name, bm, [material], collection, smooth=True)
    return ob


# ---------- Poly Haven ----------
def append_ph(asset, res):
    """Append every object of assets/ph/<asset>/<asset>_<res>.blend into an excluded template collection."""
    path = A('ph', asset, f'{asset}_{res}.blend')
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    c = coll('_tpl_' + asset, exclude=True)
    out = {}
    for ob in dst.objects:
        if ob is not None:
            c.objects.link(ob)
            out[ob.name] = ob
    return out


def dup(ob, name, loc, rot_z=0.0, scale=1.0, collection='Props'):
    """Linked duplicate (shares mesh and materials)."""
    d = ob.copy()
    d.name = name
    d.location = loc
    d.rotation_mode = 'XYZ'                 # glTF imports come in quaternion mode, which ignores rotation_euler
    d.rotation_euler = (0, 0, rot_z)
    d.scale = (scale, scale, scale) if isinstance(scale, (int, float)) else scale
    return link(d, collection)


def join(name, parts):
    """Join objects into the first one (keeps every material)."""
    with bpy.context.temp_override(active_object=parts[0], selected_editable_objects=parts, selected_objects=parts):
        bpy.ops.object.join()
    parts[0].name = parts[0].data.name = name
    return parts[0]


def bevel_mod(ob, width=0.003, segments=2):
    m = ob.modifiers.new('bevel', 'BEVEL'); m.width = width; m.segments = segments; m.limit_method = 'ANGLE'
    m.harden_normals = False
    return ob


def missing_images():
    bad = []
    for im in bpy.data.images:
        if im.source == 'FILE' and not im.packed_file and not os.path.exists(bpy.path.abspath(im.filepath)):
            bad.append(im.filepath)
    return bad
