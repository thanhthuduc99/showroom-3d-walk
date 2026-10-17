"""HẺM streetwear store (Saigon alley) for the real-time site: same layout and assets as clothing-store/, rebuilt in Blender
so Cycles can bake its light. Example for bake_lightmap.py (big room). Run: blender -b -P blender/build_shop_example.py  -> scene.blend + web/frames.json
Layout coordinates (clothing-store/layout.js): x west-east, z north(-)/south(+), y up. Blender: (x, -z, y)."""
import bpy, bmesh, json, math, os, sys
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import A, ROOT, coll, link, mat, pbr, image_mat, noise_rough, _planar_uv, missing_images
from walk import make_camera, write_frames_json

N_FRAMES = 401
VERSION = 'r1'
W, D, H = 14.0, 10.0, 4.2
HW, HD, T = W / 2, D / 2, 0.25
FX0, FX1, FTOP = -4.0, 4.0, 3.1
EYE = 1.6

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
BLEND = os.path.join(ROOT, 'scene.blend')
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
B = lambda x, y, z: Vector((x, -z, y))          # layout -> Blender


def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


def emit(name, hexc, strength):
    return mat(name, (0, 0, 0), 1.0, inputs={'Emission Color': (*srgb(hexc), 1), 'Emission Strength': strength})


# ---------- materials (mats.js) ----------
M = {
    'wall': pbr('wall', 'concrete_wall_008', 1 / 3.2, grey=(0.3, 0.31, 0.33), rough=(0.85, 1.0), bump=0.6),
    'facade': pbr('facade', 'concrete_wall_008', 1 / 3.2, tint=(0.32, 0.32, 0.33), rough=(0.9, 1.0), bump=0.7),
    'floor': pbr('floor', 'concrete_floor_02', 1 / 3.6, grey=(0.2, 0.21, 0.22), var=0.8, rough=(0.18, 0.4), bump=0.25),
    'alley': pbr('alley', 'concrete_floor_01', 1 / 2.6, tint=(0.9, 0.88, 0.85), rough=(0.8, 1.0), bump=0.6),
    'ceiling': mat('ceiling', (0.035, 0.035, 0.037), 1.0),
    'plY': pbr('plaster_yellow', 'yellow_plaster', 1 / 3),
    'plW': pbr('plaster_white', 'painted_plaster_wall', 1 / 3),
    'shutter': pbr('shutter', 'painted_metal_shutter', 1 / 2.2, tint=(0.78, 0.8, 0.82), rough=(0.6, 0.9), bump=0.7),
    'velvet': mat('velvet', (0.012, 0.012, 0.014), 1.0, inputs={'Sheen Weight': 1.0}),
    'plywood': pbr('plywood', 'plywood', 1 / 1.2, rough=(0.75, 0.95)),
    'steel': mat('steel', srgb('#111214'), 0.42, 0.55),
    'stainless': mat('stainless', srgb('#c4c8cc'), 0.26, 1.0),
    'duct': mat('duct', srgb('#a3a9af'), 0.36, 1.0),
    'mirror': mat('mirror', (0.95, 0.95, 0.95), 0.02, 1.0),
    'rubber': mat('rubber', srgb('#0d0d0e'), 0.75),
    'black': mat('black_paint', srgb('#151617'), 0.55),
    'block': pbr('concrete_block', 'concrete_wall_008', 1 / 2, grey=(0.36, 0.36, 0.36), rough=(0.85, 1.0), bump=0.8),
    'neon': emit('neon', '#c8ff2e', 7),
    'sign': emit('sign_lime', '#c8ff2e', 6),
    'neonback': mat('neon_back', (0.004, 0.004, 0.004), 0.3, 0.2),
    'led': emit('led', '#ffcf96', 6),
    'lens': emit('lens', '#fff1dc', 25),
    'cardboard': mat('cardboard', srgb('#b98d5c'), 0.9),
    'boxBlack': mat('box_black', srgb('#18181a'), 0.6),
    'boxLime': mat('box_lime', srgb('#b9e33a'), 0.6),
    'boxWhite': mat('box_white', srgb('#e9e6de'), 0.6),
    'dark': mat('dark', srgb('#0d0d0e'), 1.0),
    'winglass': mat('window_glass', srgb('#1b2024'), 0.08, 0.1),
}
M['mural'] = image_mat('mural', A('gen', 'mural.jpg'), 0.92)
PAINTS = []
for k, hexc in enumerate(['#e9c46c', '#ece8df', '#9fcdb6', '#e3a79d', '#a8c3d6', '#f0dfb8', '#d7d2c4']):
    m = M['plW'].copy(); m.name = 'paint_%d' % k
    b = m.node_tree.nodes['Principled BSDF']
    src = b.inputs['Base Color'].links[0].from_socket
    vm = m.node_tree.nodes.new('ShaderNodeVectorMath'); vm.operation = 'MULTIPLY'; vm.inputs[1].default_value = tuple(c * 1.15 for c in srgb(hexc))
    m.node_tree.links.new(src, vm.inputs[0]); m.node_tree.links.new(vm.outputs['Vector'], b.inputs['Base Color'])
    m['mul'] = [c * 1.15 for c in srgb(hexc)]
    PAINTS.append(m)


# ---------- geometry builder: one mesh per (group, material) ----------
class Kit:
    def __init__(self):
        self.bms = {}

    def bm(self, group, m):
        key = (group, m.name)
        if key not in self.bms:
            self.bms[key] = (bmesh.new(), m)
        return self.bms[key][0]

    def box(self, group, m, x0, y0, z0, x1, y1, z1):
        """min/max corners in layout coordinates"""
        bm = self.bm(group, m)
        a, b = B(x0, y0, z0), B(x1, y1, z1)
        lo = Vector((min(a.x, b.x), min(a.y, b.y), min(a.z, b.z))); hi = Vector((max(a.x, b.x), max(a.y, b.y), max(a.z, b.z)))
        vs = [bm.verts.new((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
        for idx in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            bm.faces.new([vs[i] for i in idx])

    def rod(self, group, m, a, b, r, seg=12, caps=True):
        bm = self.bm(group, m)
        A_, B_ = B(*a), B(*b)
        d = B_ - A_; L = d.length
        if L < 1e-6:
            return
        rot = d.normalized().to_track_quat('Z', 'Y').to_matrix().to_4x4()
        mtx = Matrix.Translation(A_) @ rot
        r0 = [bm.verts.new(mtx @ Vector((r * math.cos(t), r * math.sin(t), 0))) for t in (2 * math.pi * i / seg for i in range(seg))]
        r1 = [bm.verts.new(mtx @ Vector((r * math.cos(t), r * math.sin(t), L))) for t in (2 * math.pi * i / seg for i in range(seg))]
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
        if caps:
            bm.faces.new(r0[::-1]); bm.faces.new(r1)

    def ball(self, group, m, p, r):
        bm = self.bm(group, m)
        res = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=r)
        bmesh.ops.translate(bm, vec=B(*p), verts=res['verts'])

    def build(self):
        out = []
        for (group, name), (bm, m) in self.bms.items():
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            _planar_uv(bm)
            me = bpy.data.meshes.new(f'{group}_{name}'); bm.to_mesh(me); bm.free()
            me.materials.append(m)
            ob = bpy.data.objects.new(f'{group}_{name}', me)
            out.append(link(ob, group))
        return out


K = Kit()

# ---------- building (store.js shell / storefront / alley) ----------
K.box('floor', M['floor'], -HW, -0.1, -HD, HW, 0, HD + T)
K.box('ceil', M['ceiling'], -HW - T, H, -HD - T, HW + T, H + 0.3, HD + T)
K.box('in', M['wall'], -HW - T, 0, -HD - T, HW + T, H, -HD)
K.box('in', M['wall'], -HW - T, 0, -HD, -HW, H, HD)
K.box('in', M['wall'], HW, 0, -HD, HW + T, H, HD)
K.box('in', M['wall'], -HW, 0, HD, FX0, H, HD + T)
K.box('in', M['wall'], FX1, 0, HD, HW, H, HD + T)
K.box('in', M['wall'], FX0, FTOP + 0.42, HD, FX1, H, HD + T)
K.box('ex', M['facade'], -HW - T, 0, HD + T, FX0, 7.2, HD + T + 0.04)
K.box('ex', M['facade'], FX1, 0, HD + T, HW + T, 7.2, HD + T + 0.04)
K.box('ex', M['facade'], FX0, FTOP + 0.42, HD + T, FX1, 7.2, HD + T + 0.04)
K.box('ex', M['facade'], -HW - T, H + 0.3, -HD - T, HW + T, 7.2, HD + T)
for x0, z0, x1, z1 in ((-HW, -HD, HW, -HD + 0.012), (-HW, -HD, -HW + 0.012, HD), (HW - 0.012, -HD, HW, HD)):
    K.box('in', M['rubber'], x0, 0, z0, x1, 0.06, z1)
z = HD + T / 2
for x in (FX0 + 0.07, FX1 - 0.07):
    K.box('in', M['steel'], x - 0.07, 0, z - 0.07, x + 0.07, FTOP, z + 0.07)
K.box('in', M['steel'], FX0, FTOP, z - 0.09, FX1, FTOP + 0.14, z + 0.09)
K.box('ex', M['shutter'], FX0, FTOP + 0.14, HD + 0.02, FX1, FTOP + 0.42, HD + T + 0.08)
K.box('in', M['stainless'], FX0, 0, HD, FX1, 0.006, HD + T)

zf = HD + T + 0.04
K.box('ex', M['alley'], -18, -0.1, zf - 0.04, 18, 0, 22)
for x0, x1, m in ((-18, -HW - T, M['plY']), (HW + T, 18, M['plW'])):
    K.box('ex', m, x0, 0, zf, x1, 7.2, zf + 0.02)
    K.box('ex', M['shutter'], x0 + 0.5, 0, zf + 0.02, x1 - 0.5, 3.0, zf + 0.06)
    K.box('ex', M['steel'], x0 + 0.44, 3.0, zf + 0.02, x1 - 0.44, 3.3, zf + 0.3)
# Saigon tube houses across the lane
x, z0 = -18.5, 13.0
for k, w in enumerate([4.4, 3.8, 4.6, 4.0, 3.6, 4.2, 4.8, 3.9, 4.3]):
    x0, x1, m, Hh = x, x + w, PAINTS[k % len(PAINTS)], 7.2 + ((k * 5) % 4) * 0.9
    K.box('exh', m, x0, 0, z0, x1, Hh, z0 + 0.3)
    K.box('exh', m, x0 + 0.02, Hh, z0, x1 - 0.02, Hh + 0.9, z0 + 0.12)
    K.box('exh', M['dark'] if k % 3 == 1 else M['shutter'], x0 + 0.35, 0, z0 - 0.02, x1 - 0.35, 2.9, z0 + 0.01)
    K.box('exh', M['steel'], x0 + 0.3, 2.9, z0 - 0.25, x1 - 0.3, 3.2, z0)
    for y in (3.45, 6.35):
        if y + 2.6 > Hh + 0.5:
            continue
        K.box('exh', m, x0 + 0.1, y - 0.16, z0 - 0.85, x1 - 0.1, y, z0)
        bx = x0 + 0.2
        while bx < x1 - 0.15:
            K.box('exh', M['steel'], bx - 0.01, y, z0 - 0.83, bx + 0.01, y + 1.0, z0 - 0.81)
            bx += 0.13
        K.box('exh', M['steel'], x0 + 0.15, y + 0.98, z0 - 0.85, x1 - 0.15, y + 1.04, z0 - 0.79)
        K.box('exh', M['steel'], x0 + 0.6, y + 0.1, z0 - 0.03, x1 - 0.6, y + 2.3, z0 + 0.01)
        K.box('exh', M['winglass'], x0 + 0.68, y + 0.18, z0 - 0.04, x1 - 0.68, y + 2.22, z0)
    x = x1 + 0.02

# ---------- ceiling: ducts, track rails, spot cans ----------
RAILS_Z, RAIL_Y = (-3.3, 0.3, 2.7), 3.95
for zz in (-2.0, 2.0):
    K.rod('ceil', M['duct'], (-HW + 0.1, 3.55, zz), (HW - 0.1, 3.55, zz), 0.3, seg=40, caps=False)
    for xx in range(-6, 7, 2):
        K.rod('ceil', M['steel'], (xx, 3.85, zz), (xx, H, zz), 0.008, 6)
        K.rod('ceil', M['steel'], (xx - 0.01, 3.55, zz), (xx + 0.01, 3.55, zz), 0.31, 40)
for zz in RAILS_Z:
    K.box('ceil', M['steel'], -6.6, RAIL_Y - 0.02, zz - 0.018, 6.6, RAIL_Y + 0.02, zz + 0.018)
    for xx in (-6, -2, 2, 6):
        K.rod('ceil', M['steel'], (xx, RAIL_Y, zz), (xx, H, zz), 0.006, 6)


def add_light(kind, name, loc, power, color, **kw):
    ld = bpy.data.lights.new(name, kind); ld.energy = power; ld.color = color
    for k, v in kw.items():
        setattr(ld, k, v)
    ob = bpy.data.objects.new(name, ld); ob.location = loc
    return link(ob, 'Lights'), ld


def spot(frm, to, power=1.0, angle=0.32, color=srgb('#ffd9b0')):
    a, b = Vector(frm), Vector(to)
    d = (b - a).normalized()
    K.rod('ceil', M['steel'], tuple(a), tuple(a + d * 0.16), 0.036, 16)
    K.rod('ceil', M['steel'], tuple(a), (a.x, RAIL_Y, a.z), 0.008, 6)
    K.rod('ceil', M['lens'], tuple(a + d * 0.155), tuple(a + d * 0.162), 0.026, 16)
    pos = B(*(a + d * 0.17)); tgt = B(*b)
    ob, ld = add_light('SPOT', 'spot', pos, 110 * power, color, spot_size=2 * angle, spot_blend=0.55, shadow_soft_size=0.03)
    ob.rotation_euler = (tgt - pos).to_track_quat('-Z', 'Y').to_euler()


def s(xx, zi, to, **o):
    spot((xx, RAIL_Y - 0.05, RAILS_Z[zi]), to, **o)


for zz in (-2.2, 0, 2.2):
    s(-5.0, 0 if zz < -1 else 2 if zz > 1 else 1, (-6.5, 1.25, zz), angle=0.4)
s(-2.6, 0, (-2.6, 1.9, -4.95), angle=0.42, power=0.85)
s(0.6, 0, (0.6, 1.9, -4.95), angle=0.42, power=0.85)
s(-5.4, 0, (-5.45, 1.6, -4.95), angle=0.36)
s(3.6, 0, (3.6, 1.4, -4.7), angle=0.45, power=0.6)
s(-1.9, 1, (-1.9, 1.15, 0.3), angle=0.3, power=1.15)
s(1.9, 1, (1.9, 1.15, 0.3), angle=0.3, power=1.15)
s(0, 1, (0, 0.8, 0.3), angle=0.36, power=0.8)
for zz in (-0.4, 1.6):
    s(5.2, 1 if zz < 0.5 else 2, (6.5, 1.25, zz), angle=0.4)
s(4.6, 2, (5.0, 1.05, 3.2), angle=0.4, power=0.6)
s(5.6, 2, (6.85, 1.4, 3.6), angle=0.35, power=0.6)
for zz in (-2.6, 1.6):                       # broad fill panels under the ducts
    ob, ld = add_light('AREA', 'fill', B(0, 3.2, zz), 420, srgb('#f2f1ee'), shape='RECTANGLE', size=12, size_y=2.4)

# ---------- fixtures ----------
FIX = {'rail-west': (-6.55, 0, 6, 1.75), 'rail-east': (6.55, 0.6, 3.2, 1.75)}
for fxx, fz, flen, fh in FIX.values():
    a, b, wx = fz - flen / 2, fz + flen / 2, -HW if fxx < 0 else HW
    K.rod('in', M['steel'], (fxx, fh, a), (fxx, fh, b), 0.016, 16)
    for zz in (a + 0.1, fz, b - 0.1):
        K.rod('in', M['steel'], (wx, fh, zz), (fxx, fh, zz), 0.012, 10)
# mirror on the west wall
K.box('in', M['steel'], -6.98, 0.05, 3.35, -6.93, 2.25, 4.45)
K.box('mirror', M['mirror'], -6.93, 0.09, 3.39, -6.925, 2.21, 4.41)
# bench + crate stool etc. (bench at -5.4, -4.0)
bx_, bz_, bw_, bd_, bh_ = -5.4, -4.0, 1.8, 0.45, 0.45
K.box('in', M['plywood'], bx_ - bw_ / 2, bh_ - 0.04, bz_ - bd_ / 2, bx_ + bw_ / 2, bh_, bz_ + bd_ / 2)
for sx in (-1, 1):
    xx = bx_ + sx * (bw_ / 2 - 0.15)
    K.box('in', M['steel'], xx - 0.015, 0, bz_ - bd_ / 2 + 0.03, xx + 0.015, bh_ - 0.04, bz_ - bd_ / 2 + 0.06)
    K.box('in', M['steel'], xx - 0.015, 0, bz_ + bd_ / 2 - 0.06, xx + 0.015, bh_ - 0.04, bz_ + bd_ / 2 - 0.03)
    K.box('in', M['steel'], xx - 0.015, bh_ - 0.07, bz_ - bd_ / 2 + 0.03, xx + 0.015, bh_ - 0.04, bz_ + bd_ / 2 - 0.03)
# mural
me = bpy.data.meshes.new('mural'); bm = bmesh.new()
vs = [bm.verts.new(B(xx, yy, -HD + 0.004)) for xx, yy in ((-1.05 - 2.65, 0.6), (-1.05 + 2.65, 0.6), (-1.05 + 2.65, 3.6), (-1.05 - 2.65, 3.6))]
f = bm.faces.new(vs); uvl = bm.loops.layers.uv.new('UVMap')
for l, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
    l[uvl].uv = uv
bm.to_mesh(me); bm.free(); me.materials.append(M['mural'])
link(bpy.data.objects.new('in_mural', me), 'in')

# neon letters
GLYPHS = {'H': (0.62, [[(0, 0), (0, 1)], [(0.62, 0), (0.62, 1)], [(0, 0.5), (0.62, 0.5)]]),
          'Ẻ': (0.56, [[(0.56, 1), (0, 1), (0, 0), (0.56, 0)], [(0, 0.5), (0.44, 0.5)],
                       [(0.13, 1.2), (0.18, 1.33), (0.3, 1.4), (0.43, 1.36), (0.46, 1.26), (0.38, 1.18), (0.29, 1.15), (0.28, 1.08)]]),
          'M': (0.78, [[(0, 0), (0, 1), (0.39, 0.42), (0.78, 1), (0.78, 0)]])}


def letters(group, text, cx, y, z, size, r, m, standz, standm):
    gap = 0.42 * size
    total = sum(GLYPHS[c][0] * size for c in text) + gap * (len(text) - 1)
    x = cx - total / 2; y0 = y - size / 2
    for c in text:
        w, strokes = GLYPHS[c]
        for st in strokes:
            pts = [(x + u * size, y0 + v * size, z) for u, v in st]
            for p0, p1 in zip(pts, pts[1:]):
                K.rod(group, m, p0, p1, r, 10)
            for p in pts:
                K.ball(group, m, p, r)
            for p in (pts[0], pts[-1]):
                K.rod(group, standm, (p[0], p[1], standz), p, max(0.004, r * 0.3), 6)
        x += w * size + gap
    return total


total = letters('neon', 'HẺM', -1.05, 3.0, -HD + 0.07, 0.52, 0.016, M['neon'], -HD, M['neonback'])
ob, ld = add_light('AREA', 'neon_out', B(-1.05, 3.0, -HD + 0.12), 14, srgb('#c8ff2e'), shape='RECTANGLE', size=total + 0.2, size_y=0.7)
ob.rotation_euler = (B(-1.05, 2.4, 0) - ob.location).to_track_quat('-Z', 'Y').to_euler()
ob, ld = add_light('AREA', 'neon_back', B(-1.05, 3.0, -HD + 0.04), 18, srgb('#c8ff2e'), shape='RECTANGLE', size=total + 0.3, size_y=0.8)
ob.rotation_euler = (B(-1.05, 3.0, -HD - 1) - ob.location).to_track_quat('-Z', 'Y').to_euler()
letters('neon', 'HẺM', 0, FTOP + 0.85, zf + 0.12, 0.46, 0.021, M['sign'], zf, M['steel'])


# rolling racks
for rxx, rz in ((-2.4, -1.1), (2.4, -1.1)):
    a, b = rz - 0.65, rz + 0.65
    K.rod('in', M['stainless'], (rxx, 1.62, a), (rxx, 1.62, b), 0.014, 12)
    for zz in (a, b):
        K.rod('in', M['stainless'], (rxx, 0.09, zz), (rxx, 1.62, zz), 0.016, 12)
        K.rod('in', M['stainless'], (rxx - 0.28, 0.09, zz), (rxx + 0.28, 0.09, zz), 0.014, 12)
        for sx in (-1, 1):
            K.rod('in', M['rubber'], (rxx + sx * 0.26, 0.04, zz - 0.0125), (rxx + sx * 0.26, 0.04, zz + 0.0125), 0.035, 16)

# sneaker cubbies (6 x 5) with LED strips
CX, CLEN, CD, CY0, CY1, COLS, ROWS = 3.6, 3.6, 0.42, 0.3, 2.9, 6, 5
t = 0.022; cx0, cx1, cz0, cz1 = CX - CLEN / 2, CX + CLEN / 2, -HD, -HD + CD
cw, ch = CLEN / COLS, (CY1 - CY0) / ROWS
K.box('in', M['steel'], cx0, CY0, cz0, cx1, CY1, cz0 + t)
for i in range(COLS + 1):
    K.box('in', M['steel'], cx0 + i * cw - t / 2, CY0, cz0, cx0 + i * cw + t / 2, CY1, cz1)
cells = []
for j in range(ROWS + 1):
    yy = CY0 + j * ch
    K.box('in', M['steel'], cx0 - t / 2, yy - t / 2, cz0, cx1 + t / 2, yy + t / 2, cz1)
    if j > 0:
        K.box('neon', M['led'], cx0, yy - t / 2 - 0.008, cz1 - 0.05, cx1, yy - t / 2, cz1 - 0.035)
        ob, ld = add_light('AREA', 'cubby_led', B(CX, yy - t / 2 - 0.012, (cz0 + cz1) / 2 + 0.03), 28, srgb('#ffcf96'), shape='RECTANGLE', size=CLEN - 0.05, size_y=0.28)
        ob.rotation_euler = (0, 0, 0)            # area lights point down (-Z) by default
for j in range(ROWS):
    for i in range(COLS):
        cells.append((cx0 + (i + 0.5) * cw, CY0 + j * ch + t / 2, (cz0 + cz1) / 2 + 0.02, i, j))


# pleated velvet curtain along z at x
def curtain(name, x, za, zb, top, seed, pitch=0.11):
    nz, ny = max(8, int((zb - za) / 0.012)), 40
    bm = bmesh.new(); rows = []
    rng = np.random.default_rng(seed)
    ph0 = rng.uniform(0, 6.28, 4)
    for jj in range(ny + 1):
        v = jj / ny; yy = 0.03 + (top - 0.03) * v; row = []
        for ii in range(nz + 1):
            zz = za + (zb - za) * ii / nz
            amp = 0.035 + 0.01 * math.sin(zz * 3 + ph0[0]) * math.cos(yy * 0.7 + ph0[1])
            ph = 2 * math.pi * (zz - za) / pitch + 0.8 * math.sin(zz * 2 + yy * 0.8 + ph0[2])
            row.append(bm.verts.new(B(x + amp * math.sin(ph), yy, zz)))
        rows.append(row)
    for jj in range(ny):
        for ii in range(nz):
            bm.faces.new((rows[jj][ii], rows[jj][ii + 1], rows[jj + 1][ii + 1], rows[jj + 1][ii]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    _planar_uv(bm)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(M['velvet'])
    for p in me.polygons:
        p.use_smooth = True
    return link(bpy.data.objects.new(name, me), 'props')


for k, (bz, opn) in enumerate(((-3.75, False), (-2.2, True))):
    bx0, bx1, za, zb, bh = 6.3 - 0.7, HW, bz - 0.75, bz + 0.75, 2.4
    for zz in (za, zb):
        K.box('in', M['wall'], bx0, 0, zz - 0.04, bx1, bh, zz + 0.04)
    K.rod('in', M['steel'], (bx0 + 0.03, bh - 0.06, za), (bx0 + 0.03, bh - 0.06, zb), 0.01, 8)
    curtain(f'curtain_{k}', bx0 + 0.05, za + 0.05, za + 0.55 if opn else zb - 0.05, bh - 0.07, k * 7, 0.07 if opn else 0.11)
    K.box('in', M['steel'], bx1 - 0.03, 0.25, bz - 0.32, bx1 - 0.01, 2.05, bz + 0.32)
    K.box('mirror', M['mirror'], bx1 - 0.035, 0.29, bz - 0.28, bx1 - 0.03, 2.01, bz + 0.28)
    K.rod('in', M['plywood'], (bx0 + 0.45, 0, bz + 0.35), (bx0 + 0.45, 0.42, bz + 0.35), 0.17, 24)
    add_light('AREA', 'booth', B((bx0 + bx1) / 2, bh - 0.02, bz), 25, srgb('#ffe2bd'), shape='SQUARE', size=0.9)

# counter + payment pad
cxx, czz, cww, cdd, chh = 5.0, 3.2, 2.4, 0.75, 1.05
K.box('in', M['block'], cxx - cww / 2, 0, czz - cdd / 2, cxx + cww / 2, chh - 0.03, czz + cdd / 2)
K.box('in', M['stainless'], cxx - cww / 2 - 0.02, chh - 0.03, czz - cdd / 2 - 0.02, cxx + cww / 2 + 0.02, chh, czz + cdd / 2 + 0.02)
K.box('in', M['rubber'], cxx - cww / 2 + 0.02, 0, czz - cdd / 2 - 0.002, cxx + cww / 2 - 0.02, 0.08, czz + cdd / 2 + 0.002)
K.box('in', M['black'], cxx - 0.62, chh + 0.04, czz - 0.06, cxx - 0.38, chh + 0.2, czz - 0.048)
K.rod('in', M['steel'], (cxx - 0.5, chh, czz - 0.02), (cxx - 0.5, chh + 0.1, czz - 0.04), 0.012, 8)
# shoebox shelf behind the counter
za, zb, xw = 3.6 - 0.7, 3.6 + 0.7, HW
mats = [M['boxBlack'], M['boxLime'], M['boxWhite'], M['boxBlack'], M['cardboard']]
kk = 0
for yy in (0.95, 1.38, 1.81):
    K.box('in', M['steel'], xw - 0.36, yy - 0.02, za, xw, yy, zb)
    zz = za + 0.06
    while zz + 0.22 < zb:
        n = 1 + (1 if (kk * 7) % 3 == 0 else 0) + (1 if kk % 4 == 1 else 0)
        for sidx in range(n):
            K.box('in', mats[(kk + sidx) % len(mats)], xw - 0.34, yy + sidx * 0.12, zz, xw - 0.02, yy + sidx * 0.12 + 0.115, zz + 0.21)
        kk += 1; zz += 0.25
# island plinth
K.box('in', M['block'], -1.2, 0, 0.3 - 0.55, 1.2, 0.75, 0.3 + 0.55)

# skate decks with the generated graphics
for i in range(8):
    xx = -5.45 - 1.3 + 2.6 * (i + 0.5) / 8
    Wd, Ld, r = 0.21, 0.81, 0.105
    bm = bmesh.new(); pts = []
    for k2 in range(13):
        a = math.pi * k2 / 12
        pts.append((r * math.cos(a), Ld / 2 - r + r * math.sin(a)))
    for k2 in range(13):
        a = math.pi + math.pi * k2 / 12
        pts.append((r * math.cos(a), -Ld / 2 + r + r * math.sin(a)))
    face = bm.faces.new([bm.verts.new((px, py, 0)) for px, py in pts])
    ext = bmesh.ops.extrude_face_region(bm, geom=[face])
    bmesh.ops.translate(bm, vec=(0, 0, 0.012), verts=[v for v in ext['geom'] if isinstance(v, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for l in f.loops:
            l[uvl].uv = ((l.vert.co.x + r) / Wd, (l.vert.co.y + Ld / 2) / Ld)
    me = bpy.data.meshes.new(f'deck_{i}'); bm.to_mesh(me); bm.free()
    me.materials.append(image_mat(f'deck_{i}', A('gen', f'deck_{i}.jpg'), 0.45))
    ob = link(bpy.data.objects.new(f'deck_{i}', me), 'props')
    ob.rotation_euler = (math.pi / 2, (1 if i % 2 else -1) * 0.015, 0)
    ob.location = B(xx, 1.6, -HD + 0.018)
    K.rod('in', M['steel'], (xx, 1.9, -HD), (xx, 1.9, -HD + 0.04), 0.006, 6)

# A-board on the alley
ab_path = os.path.join(ROOT, 'renders', 'aboard.png')        # tools/make_sign.py
abm = image_mat('aboard', ab_path, 0.85)
for sgn in (-1, 1):
    bm = bmesh.new()
    vs = [bm.verts.new((px, 0, py)) for px, py in ((-0.27, 0.09), (0.27, 0.09), (0.27, 0.91), (-0.27, 0.91))]
    f = bm.faces.new(vs); uvl = bm.loops.layers.uv.new('UVMap')
    for l, uv in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
        l[uvl].uv = uv
    me = bpy.data.meshes.new('aboard_face'); bm.to_mesh(me); bm.free(); me.materials.append(abm)
    ob = link(bpy.data.objects.new(f'aboard_{sgn}', me), 'props')
    ob.rotation_euler = (sgn * 0.18, 0, -0.35 + (0 if sgn > 0 else math.pi))
    ob.location = B(-2.7, 0, 6.1 + sgn * 0.085)
    pb = bpy.data.meshes.new('aboard_frame'); bm = bmesh.new()
    res = bmesh.ops.create_cube(bm, size=1); bmesh.ops.scale(bm, vec=(0.62, 0.02, 0.95), verts=res['verts']); bmesh.ops.translate(bm, vec=(0, 0.012, 0.475), verts=res['verts'])
    _planar_uv(bm); bm.to_mesh(pb); bm.free(); pb.materials.append(M['plywood'])
    o2 = link(bpy.data.objects.new(f'aboard_frame_{sgn}', pb), 'props')
    o2.rotation_euler = ob.rotation_euler; o2.location = ob.location

objs = K.build()

# ---------- goods (goods.js): AI models, recoloured ----------
def import_kit(name, height, rough, ratio):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=A('ai', f'{name}_sm.glb'))
    new = [o for o in bpy.data.objects if o not in before]
    ms = [o for o in new if o.type == 'MESH']
    me = ms[0]
    for o in new:
        if o is not me:
            bpy.data.objects.remove(o)
    me.data.transform(me.matrix_world); me.matrix_world = Matrix()
    if ratio < 1:
        bm = bmesh.new(); bm.from_mesh(me.data)
        bm.free()
        d = me.modifiers.new('dec', 'DECIMATE'); d.ratio = ratio
        with bpy.context.temp_override(object=me, active_object=me):
            bpy.ops.object.modifier_apply(modifier='dec')
    vs = np.array([v.co for v in me.data.vertices])
    lo, hi = vs.min(0), vs.max(0)
    sc = height / (hi[2] - lo[2])
    me.data.transform(Matrix.Scale(sc, 4) @ Matrix.Translation(Vector((-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]))))
    for p in me.data.polygons:
        p.use_smooth = True
    m = me.data.materials[0]
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    for nm in ('Metallic', 'Roughness'):
        for l in list(b.inputs[nm].links):
            m.node_tree.links.remove(l)
    b.inputs['Metallic'].default_value = 0; b.inputs['Roughness'].default_value = rough
    me.name = 'kit_' + name
    for c in list(me.users_collection):
        c.objects.unlink(me)
    coll('_kits', exclude=True).objects.link(me)
    return me


def base_image(ob):
    m = ob.data.materials[0]
    return next(n.image for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and 'normal' not in n.image.name.lower()
                and n.outputs['Color'].links and n.outputs['Color'].links[0].to_socket.name == 'Base Color')


VARIANTS = {}


def variant(kit, hexc, pick=None):
    """copy of the kit's material with the base colour recoloured (keep each pixel's brightness vs the recoloured mean)"""
    if hexc is None:
        return kit.data.materials[0]
    key = (kit.name, hexc, pick.__name__ if pick else '')
    if key in VARIANTS:
        return VARIANTS[key]
    src = base_image(kit)
    w_, h_ = src.size
    px = np.empty(w_ * h_ * 4, np.float32); src.pixels.foreach_get(px); px = px.reshape(h_, w_, 4)
    rgb = px[..., :3] ** (1 / 2.2) * 255 if src.colorspace_settings.name != 'sRGB' else px[..., :3] * 255
    rgb = px[..., :3] * 255
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722])
    sel = pick(rgb) if pick else np.ones(lum.shape, bool)
    mean = lum[sel].mean() if sel.any() else 1
    f = np.clip(lum / mean, 0.35, 1.6)[..., None]
    tgt = np.array([int(hexc[i:i + 2], 16) for i in (0, 2, 4)], np.float32)
    new = np.where(sel[..., None], np.minimum(255, tgt * f), rgb)
    out = bpy.data.images.new(f'{src.name}_{hexc}', w_, h_, alpha=False)
    out.pixels.foreach_set(np.concatenate([new / 255, np.ones((h_, w_, 1))], 2).astype(np.float32).ravel())
    out.pack()
    m = kit.data.materials[0].copy(); m.name = f'{kit.name}_{hexc}'
    for n in m.node_tree.nodes:
        if n.type == 'TEX_IMAGE' and n.image == src:
            n.image = out
    VARIANTS[key] = m
    return m


def place(kit, name, loc, rz, material=None):
    o = kit.copy(); o.data = kit.data           # shared mesh; bake.py gives each its own copy
    o.name = name; o.location = loc; o.rotation_mode = 'XYZ'; o.rotation_euler = (0, 0, rz)
    if material is not None:
        o.material_slots[0].link = 'OBJECT'; o.material_slots[0].material = material
    return link(o, 'goods')


hoodie = import_kit('hoodie', 0.95, 0.95, 0.12)
varsity = import_kit('varsity', 0.95, 0.9, 0.12)
tees = import_kit('tees', 0.15, 0.95, 0.12)
sneaker = import_kit('sneaker', 0.13, 0.7, 0.08)
mannequin = import_kit('mannequin', 1.88, 0.75, 0.2)
scooter = import_kit('scooter', 1.08, 0.45, 0.25)


def fill_rail(name, fxx, fz, flen, fh, pattern, gap, ry):
    n = int((flen - 0.2) / gap) + 1; z0_ = fz - (n - 1) * gap / 2
    for i in range(n):
        kind, hexc = pattern[i % len(pattern)]
        kit = hoodie if kind == 'h' else varsity
        loc = B(fxx + (i % 3 - 1) * 0.012, fh + 0.03 - 0.95, z0_ + i * gap)
        place(kit, f'{name}_{i}', loc, ry + ((i * 37) % 7 - 3) * 0.02 + math.pi / 2, variant(kit, hexc))


Hc = lambda h: ('h', h); Vc = lambda h: ('v', h)
fill_rail('rail_w', -6.55, 0, 6, 1.75, [Hc(None), Hc('8a8c8f'), Vc(None), Hc('e8e2d4'), Hc('b9e33a'), Vc('1d1d1f'), Hc('6f7d5c'), Hc(None), Hc('d9d4c7'), Vc(None), Hc('2c3a52')], 0.28, 0.3)
fill_rail('rail_e', 6.55, 0.6, 3.2, 1.75, [Hc('b9e33a'), Hc('e8e2d4'), Hc('8d9c7a'), Vc(None), Hc(None), Hc('c7c1b4'), Hc('8a8c8f')], 0.29, -0.3)
fill_rail('rack_a', -2.4, -1.1, 1.3, 1.62, [Hc('e8e2d4'), Vc(None), Hc(None), Hc('b9e33a'), Hc('8a8c8f')], 0.26, 0)
fill_rail('rack_b', 2.4, -1.1, 1.3, 1.62, [Hc('1d1d1f'), Hc('d9d4c7'), Vc('1d1d1f'), Hc('6f7d5c'), Hc('e8e2d4')], 0.26, 0)
for k, (hexc, dx, dz, ry) in enumerate([(None, -0.85, -0.22, 0.1), ('1d1d1f', -0.3, -0.22, -0.05), (None, 0.3, -0.22, 3.1), ('e8e2d4', 0.85, -0.22, 0.04),
                                        ('8a8c8f', -0.6, 0.24, 3.2), (None, 0, 0.24, 0.06), ('b9e33a', 0.6, 0.24, 3.1)]):
    place(tees, f'tees_{k}', B(dx, 0.75, 0.3 + dz), ry, variant(tees, hexc))


def grey(rgb):
    mx, mn, av = rgb.max(2), rgb.min(2), rgb.mean(2)
    return ((mx - mn) / np.maximum(mx, 1) < 0.16) & (av > 50) & (av < 190)


def suede(rgb):
    mx, mn, av = rgb.max(2), rgb.min(2), rgb.mean(2)
    return ((mx - mn) / np.maximum(mx, 1) < 0.13) & (av > 95) & (av < 205)


place(mannequin, 'mq_1', B(-1.9, 0, 0.3), 0.35)
place(mannequin, 'mq_2', B(1.9, 0, 0.3), -0.35, variant(mannequin, 'b9e33a', grey))
SHOE = [None, 'b9e33a', 'ff4fa3', '3b6cff', '1d1d1f', 'c9a77c', '8a8c8f', 'e8653a']
for k, (cx_, cy_, cz_, i, j) in enumerate(cells):
    hexc = SHOE[(k * 5 + j) % len(SHOE)]
    place(sneaker, f'shoe_{k}', B(cx_, cy_, cz_), ((i + j) % 2) * math.pi, variant(sneaker, hexc, suede if hexc else None))
place(scooter, 'scooter', B(2.9, 0, 7.3), -1.25)


# ---------- Poly Haven props (glTF) ----------
def import_ph(name, height, loc, rz, drop=()):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=A('models', name, f'{name}.gltf'))
    new = [o for o in bpy.data.objects if o not in before]
    for o in [o for o in new if any(d in o.name for d in drop)]:
        new.remove(o); bpy.data.objects.remove(o)
    ms = [o for o in new if o.type == 'MESH']
    pts = [o.matrix_world @ Vector(c) for o in ms for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    sc = height / (hi.z - lo.z) if height else 1.0
    m = Matrix.Translation(loc) @ Matrix.Rotation(rz, 4, 'Z') @ Matrix.Scale(sc, 4) @ Matrix.Translation(Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)))
    for o in ms:
        o.matrix_world = m @ o.matrix_world
        for c in list(o.users_collection):
            c.objects.unlink(o)
        link(o, 'props')
        o.name = f'ph_{name}_{o.name}'
    for o in new:
        if o.type != 'MESH':
            bpy.data.objects.remove(o)
    return ms


import_ph('potted_plant_02', 1.7, B(-6.55, 0, -4.55), 0.4, drop=('dirt',))
import_ph('potted_plant_04', 1.25, B(-6.5, 0, 4.5), 1.2)
import_ph('potted_plant_02', 1.3, B(-5.6, 0, 6.1), 2.0, drop=('dirt',))
import_ph('plastic_crate_01', None, B(-4.9, 0, 6.3), 0.2)
import_ph('plastic_crate_01', None, B(-4.9, 0.26, 6.3), -0.15)
import_ph('metal_stool_02', None, B(-3.75, 0, 6.85), 0.6)
import_ph('exterior_aircon_unit', None, B(-10.5, 2.4, 5.62), 0)
import_ph('exterior_aircon_unit', None, B(9.6, 3.6, 5.62), 0)
import_ph('boombox', None, B(-5.4 + 0.55, 0.45, -4.0), 0.25)

# ---------- sun + sky ----------
for o in bpy.data.objects:
    if o.name.startswith('exh_'):
        o.visible_shadow = False

el, az = math.radians(30), math.radians(62)        # late sun down the alley, travelling into the shop (Blender +Y)
d = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), -math.sin(el)))
sd = bpy.data.lights.new('sun', 'SUN'); sd.energy = 22.0; sd.angle = math.radians(0.6); sd.color = (1.0, 0.78, 0.55)
so = bpy.data.objects.new('sun', sd); so.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); link(so, 'Lights')
world = bpy.data.worlds.new('sky'); scene.world = world; world.use_nodes = True
nt = world.node_tree; L_ = nt.links.new; bg = nt.nodes['Background']
env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(A('hdri', 'german_town_street_2k.hdr'))
clamp = nt.nodes.new('ShaderNodeVectorMath'); clamp.operation = 'MINIMUM'; clamp.inputs[1].default_value = (20, 20, 20)
lp = nt.nodes.new('ShaderNodeLightPath')
st = nt.nodes.new('ShaderNodeMapRange'); st.inputs['To Min'].default_value = 0.8; st.inputs['To Max'].default_value = 1.6
L_(env.outputs['Color'], clamp.inputs[0]); L_(clamp.outputs['Vector'], bg.inputs['Color'])
L_(lp.outputs['Is Camera Ray'], st.inputs['Value']); L_(st.outputs['Result'], bg.inputs['Strength'])

# ---------- the walk: in from the alley, a slow look round, one lap of the shop ----------
# layout (x, z) where you stand, layout (x, y, z) what you look at
WALK = [
    ((-0.3, 10.2), (0.0, 2.5, 0.0)),        # in the alley, the shopfront and the neon sign
    ((-0.2, 6.6), (0.0, 1.8, -3.0)),        # at the threshold
    ((-0.2, 4.2), (-0.4, 1.6, -5.0)),       # one step in: the whole shop, mural and neon at the back
    ((-1.0, 3.6), (-6.4, 1.4, 1.0)),        # turn left: the hoodie rail
    ((-3.4, 2.4), (-6.4, 1.3, -1.2)),       # walk along the rail
    ((-4.0, -0.6), (-5.5, 1.5, -4.8)),      # the skate corner, decks and bench
    ((-3.4, -2.6), (-1.0, 2.2, -5.0)),      # the mural and the HẺM neon
    ((1.5, -1.7), (3.6, 1.5, -5.0)),        # the lit sneaker wall
    ((2.2, -2.8), (6.4, 1.3, -3.0)),        # fitting rooms
    ((4.0, -0.9), (6.6, 1.3, 0.6)),         # new-in rail
    ((3.0, 0.6), (5.6, 1.2, 3.4)),          # the counter and shoebox shelf
    ((1.8, 2.8), (0.0, 0.9, 0.3)),          # back to the island: mannequins and tee stacks
    ((0.6, 3.6), (-1.0, 1.7, -5.0)),        # last look across the shop to the neon
]
KEYS = [((B(x, 0, zz).x, B(x, 0, zz).y), tuple(B(tx, ty, tz))) for (x, zz), (tx, ty, tz) in WALK]
cam, key_frames = make_camera(scene, KEYS, N_FRAMES, eye=EYE, lens=24, res=(1920, 1080))
HOTSPOTS = [
    {'id': 'hoodie', 'title': 'Box Hoodie Wash Black', 'text': '690.000đ · M L XL', 'at': tuple(B(-6.3, 1.3, -0.4)), 'from': 0.12, 'to': 0.4},
    {'id': 'varsity', 'title': 'Varsity Hẻm Green', 'text': '1.290.000đ · M L XL', 'at': tuple(B(-6.3, 1.35, -2.1)), 'from': 0.15, 'to': 0.45},
    {'id': 'deck', 'title': 'Deck 8.25" Hẻm Series', 'text': '890.000đ · 8.0 8.25', 'at': tuple(B(-5.45, 1.7, -4.9)), 'from': 0.3, 'to': 0.55},
    {'id': 'sneaker', 'title': 'Chunk Skate Low', 'text': '1.890.000đ · 39-44', 'at': tuple(B(3.6, 1.6, -4.7)), 'from': 0.45, 'to': 0.7},
    {'id': 'new-in', 'title': 'Box Hoodie Sage', 'text': '690.000đ · M L XL', 'at': tuple(B(6.3, 1.3, 0.6)), 'from': 0.6, 'to': 0.82},
    {'id': 'look', 'title': 'Full look: hoodie + cargo', 'text': '2.490.000đ · M L', 'at': tuple(B(-1.75, 1.3, 0.55)), 'from': 0.8, 'to': 1.0},
    {'id': 'tees', 'title': 'Heavy Tee 280gsm', 'text': '350.000đ · S M L XL', 'at': tuple(B(0, 0.9, 0.3)), 'from': 0.8, 'to': 1.0},
]
seen = write_frames_json(scene, cam, key_frames, HOTSPOTS, os.path.join(ROOT, 'web', 'frames.json'), VERSION)
print('BUILD objects', len(bpy.data.objects), 'keys', key_frames)
print('BUILD missing images', missing_images())
print('BUILD hotspots visible frames', seen)
bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
print('BUILD saved', BLEND)
