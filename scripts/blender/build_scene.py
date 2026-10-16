"""Worked example (Hollow Oak lounge): build the room, the camera walk and web/frames.json, save scene.blend.
Run: blender -b -P blender/build_scene.py
For a new room keep the structure and replace the ROOM / PROPS / LIGHT / CAMERA / HOTSPOTS sections.
Needs: python tools/fetch_ph.py (Poly Haven assets below) and python tools/make_label.py (bottle labels).
The hero (assets/ai/hero_clean.blend from clean_ai_model.py) is optional: the build skips it when missing."""
import bpy, math, os, sys
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import (A, ROOT, coll, link, mat, pbr, glass, image_mat, noise_rough, boxes, box, lathe, arc_solid, flutes,
                    append_ph, dup, join, bevel_mod, missing_images)
from walk import make_camera, write_frames_json

N_FRAMES = 287          # aim for <= ~7 px of image shift between neighbour frames (see references/pitfalls.md)
VERSION = "r1"          # web asset folder: bump on every re-render so immutable caches never serve old frames
RES = (1600, 900)       # render size; rendered frames are stretched on screens wider than this
EYE = 1.50
X0, X1, Y0, Y1, H = -3.5, 3.5, -3.0, 3.2, 3.2
WIN = (0.3, 2.5, 0.45, 2.85)          # window in the left wall: y0, y1, z0, z1
BAR_C, R_FRONT, R_BACK, BAR_A = (0.0, 7.6), 6.0, 5.4, 0.36
BARREL = (0.0, -0.3)
LID_Z = 0.837
WARM = (1.0, 0.72, 0.45)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
BLEND = os.path.join(ROOT, 'scene.blend')
bpy.ops.wm.save_as_mainfile(filepath=BLEND)       # saved first so appended texture paths resolve

# ---------- materials ----------
M = {
    'floor': pbr('concrete', 'smooth_concrete_floor', scale=0.45, grey=(0.20, 0.20, 0.205), rough=(0.10, 0.34), bump=0.25),
    'wall': pbr('plaster', 'white_plaster_02', scale=0.5, grey=(0.52, 0.52, 0.51), rough=(0.80, 0.95), bump=0.12, var=0.35),
    'walnut': pbr('walnut', 'black_walnut_veneer_01', scale=1.2, tint=(0.36, 0.27, 0.21), rough=(0.38, 0.55), bump=0.3),
    'slat': pbr('slat_walnut', 'black_walnut_veneer_01', scale=1.0, tint=(0.28, 0.21, 0.17), rough=(0.5, 0.7), bump=0.2),
    'top': noise_rough(mat('solid_surface', (0.80, 0.79, 0.76), 0.22), 0.18, 0.3, 2.0),
    'black_metal': noise_rough(mat('black_metal', (0.025, 0.025, 0.026), 0.4, 0.85), 0.32, 0.48, 6.0),
    'black_matte': mat('black_matte', (0.018, 0.018, 0.018), 0.85),
    'plenum': mat('plenum', (0.012, 0.012, 0.012), 0.95),
    'shade_out': noise_rough(mat('shade_black', (0.02, 0.02, 0.02), 0.45, 0.2), 0.38, 0.52, 8.0),
    'shade_in': mat('shade_inner', (0.55, 0.36, 0.16), 0.35),
    'bulb': mat('bulb', (1, 1, 1), 0.3, inputs={'Emission Color': (1.0, 0.70, 0.42, 1), 'Emission Strength': 3.0}),
    'glass': glass('glass', (0.98, 0.99, 0.98)),
    'whiskey': glass('whiskey', (0.92, 0.50, 0.16), ior=1.33),
    'cork': mat('stopper_wood', (0.24, 0.13, 0.06), 0.55),
    'label_cream': image_mat('label_cream', A('tex', 'label_cream.png'), 0.75),
    'label_kraft': image_mat('label_kraft', A('tex', 'label_kraft.png'), 0.8),
}

# ---------- room shell ----------
T = 0.2
box('floor', (X1 - X0 + 2 * T, Y1 - Y0 + 2 * T, T), (0, (Y0 + Y1) / 2, -T / 2), M['floor'])
box('plenum', (X1 - X0 + 2 * T, Y1 - Y0 + 2 * T, 0.1), (0, (Y0 + Y1) / 2, H + 0.05), M['plenum'])
wy0, wy1, wz0, wz1 = WIN
boxes('walls', [
    ((X1 - X0 + 2 * T, T, H), (0, Y1 + T / 2, H / 2)),                                   # back
    ((X1 - X0 + 2 * T, T, H), (0, Y0 - T / 2, H / 2)),                                   # front
    ((T, Y1 - Y0 + 2 * T, H), (X1 + T / 2, (Y0 + Y1) / 2, H / 2)),                       # right
    ((T, wy0 - (Y0 - T), H), (X0 - T / 2, (Y0 - T + wy0) / 2, H / 2)),                   # left, before the window
    ((T, Y1 + T - wy1, H), (X0 - T / 2, (wy1 + Y1 + T) / 2, H / 2)),                     # left, after the window
    ((T, wy1 - wy0, wz0), (X0 - T / 2, (wy0 + wy1) / 2, wz0 / 2)),                       # sill wall
    ((T, wy1 - wy0, H - wz1), (X0 - T / 2, (wy0 + wy1) / 2, (wz1 + H) / 2)),             # head wall
], M['wall'])

# black window frame, no glass (a pane would block the sun with caustics off)
F, D = 0.05, 0.06
fx = X0 - T + 0.07
frame = [((D, F, wz1 - wz0), (fx, wy0 + F / 2, (wz0 + wz1) / 2)), ((D, F, wz1 - wz0), (fx, wy1 - F / 2, (wz0 + wz1) / 2)),
         ((D, wy1 - wy0, F), (fx, (wy0 + wy1) / 2, wz0 + F / 2)), ((D, wy1 - wy0, F), (fx, (wy0 + wy1) / 2, wz1 - F / 2)),
         ((D, wy1 - wy0, 0.035), (fx, (wy0 + wy1) / 2, 2.2))]
for k in (1, 2):
    frame.append(((D, 0.035, wz1 - wz0), (fx, wy0 + (wy1 - wy0) * k / 3, (wz0 + wz1) / 2)))
boxes('window_frame', frame, M['black_metal'], bevel=0.003)

# dark walnut slatted ceiling: 45 mm slats, 45 mm gaps, running front to back
slats = []
x = X0 + 0.05
while x < X1 - 0.03:
    slats.append(((0.045, Y1 - Y0, 0.035), (x, (Y0 + Y1) / 2, H - 0.06 - 0.0175)))
    x += 0.09
boxes('ceiling_slats', slats, M['slat'], bevel=0.003)

# ---------- curved bar ----------
a0, a1 = -BAR_A, BAR_A
bevel_mod(arc_solid('bar_toe', BAR_C, R_BACK + 0.05, R_FRONT - 0.07, a0 + 0.01, a1 - 0.01, 0.0, 0.10, M['black_matte']))
bevel_mod(arc_solid('bar_body', BAR_C, R_BACK, R_FRONT - 0.005, a0, a1, 0.10, 1.04, M['black_matte']))
flutes('bar_flutes', BAR_C, R_FRONT, a0, a1, 0.10, 1.04, 0.045, M['walnut'])
bevel_mod(arc_solid('bar_top', BAR_C, R_BACK - 0.02, R_FRONT + 0.05, a0 - 0.008, a1 + 0.008, 1.04, 1.08, M['top']), 0.004, 3)


def on_arc(r, a, z=0.0):
    return (BAR_C[0] + r * math.sin(a), BAR_C[1] - r * math.cos(a), z)


# ---------- back bar shelves ----------
SH_Y = Y1 - 0.135
uprights = []
for ux in (-1.35, -0.45, 0.45, 1.35):
    for uy in (Y1 - 0.255, Y1 - 0.015):
        uprights.append(((0.025, 0.025, 1.36), (ux, uy, 1.12 + 0.68)))
SHELF_Z = (1.35, 1.78, 2.21)
plates = [((2.75, 0.27, 0.012), (0, SH_Y, z)) for z in SHELF_Z]
boxes('shelf_frame', uprights + plates, M['black_metal'], bevel=0.002)

# ---------- glassware (simple turned shapes, the realism comes from the glass shader) ----------
def rocks_glass(name):
    prof = [(0, 0.0), (0.038, 0.0), (0.041, 0.002), (0.043, 0.088), (0.0425, 0.090), (0.0395, 0.090), (0.0375, 0.016), (0, 0.016)]
    return lathe(name, prof, (0, 0, 0), M['glass'], '_tpl_glass', segments=48)


def whiskey_bottle(name, label):
    parts = [boxes(name, [((0.082, 0.082, 0.175), (0, 0, 0.0875))], M['glass'], '_tpl_glass', bevel=0.011)]
    parts.append(lathe(name + '_neck', [(0, 0.170), (0.017, 0.170), (0.0165, 0.226), (0.0195, 0.229), (0.0195, 0.236), (0, 0.236)],
                       (0, 0, 0), M['glass'], '_tpl_glass', 32))
    parts.append(boxes(name + '_liquid', [((0.072, 0.072, 0.128), (0, 0, 0.012 + 0.064))], M['whiskey'], '_tpl_glass', bevel=0.007))
    parts.append(lathe(name + '_stopper', [(0, 0.232), (0.022, 0.232), (0.023, 0.236), (0.023, 0.258), (0.020, 0.262), (0, 0.262)],
                       (0, 0, 0), M['cork'], '_tpl_glass', 32))
    lw, lh = 0.058, 0.0746                               # flat part of the bevelled face, label art is 7:9
    lab = boxes(name + '_label', [((lw, 0.0008, lh), (0, -0.0418, 0.088))], M[label], '_tpl_glass')
    uv = lab.data.uv_layers.active.data
    for poly in lab.data.polygons:                       # map the front face 0..1 across the label art
        for li in poly.loop_indices:
            co = lab.data.vertices[lab.data.loops[li].vertex_index].co
            uv[li].uv = ((co.x + lw / 2) / lw, (co.z - 0.088 + lh / 2) / lh)
    parts.append(lab)
    return join(name, parts)


coll('_tpl_glass')                                       # visible while building (join needs it), excluded right after
TPL = {'glass': rocks_glass('tpl_rocks'), 'bottle_cream': whiskey_bottle('tpl_bottle_cream', 'label_cream'),
       'bottle_kraft': whiskey_bottle('tpl_bottle_kraft', 'label_kraft')}
for t in TPL.values():
    for c in list(t.users_collection):
        c.objects.unlink(t)
    coll('_tpl_glass').objects.link(t)
bpy.context.view_layer.layer_collection.children['_tpl_glass'].exclude = True

ph_bottles = append_ph('wine_bottles_01', '1k')
WINE = [ph_bottles[k] for k in ('wine_bottles_01_bordeaux', 'wine_bottles_01_burgundy', 'wine_bottles_01_alsace')]

rng = np.random.default_rng(12)
# top two shelves: bottles, bottom shelf: rows of rocks glasses
for si, z in enumerate(SHELF_Z):
    top = z + 0.006
    if si == 0:
        for gx in list(np.arange(-1.25, -0.55, 0.11)) + list(np.arange(0.55, 1.25, 0.11)):
            dup(TPL['glass'], f'glass_{si}_{gx:.2f}', (gx, SH_Y + rng.uniform(-0.03, 0.03), top), rng.uniform(0, 6.28))
        for k, bx in enumerate((-0.25, -0.09, 0.09, 0.25)):
            src = TPL['bottle_cream'] if k % 2 == 0 else TPL['bottle_kraft']
            dup(src, f'bottle_{si}_{k}', (bx, SH_Y, top), rng.uniform(-0.15, 0.15))
    else:
        xs = [-1.22, -1.06, -0.90, -0.70, -0.25, -0.08, 0.10, 0.27, 0.70, 0.88, 1.05, 1.22]
        for k, bx in enumerate(xs):
            pick = (k + si) % 4
            src = WINE[k % 3] if pick == 3 else (TPL['bottle_cream'] if pick % 2 == 0 else TPL['bottle_kraft'])
            dup(src, f'bottle_{si}_{k}', (bx + rng.uniform(-0.015, 0.015), SH_Y + rng.uniform(-0.02, 0.02), top), rng.uniform(-0.2, 0.2))

# a few glasses and a bottle on the bar top
for k, (a, off) in enumerate(((-0.22, 0.10), (-0.19, 0.20), (0.05, 0.12), (0.24, 0.18))):
    p = on_arc(R_FRONT - 0.25 - off * 0.3, a, 1.08)
    dup(TPL['glass'], f'bar_glass_{k}', p, rng.uniform(0, 6.28))
dup(TPL['bottle_cream'], 'bar_bottle', on_arc(R_FRONT - 0.35, -0.05, 1.08), 0.3)

# ---------- pendants ----------
PENDANTS = []
for px in (-1.25, 0.0, 1.25):
    y = BAR_C[1] - math.sqrt((R_FRONT - 0.3) ** 2 - px ** 2)
    z = 2.30
    out = [(0.200, 0.0), (0.198, 0.03), (0.190, 0.07), (0.172, 0.11), (0.140, 0.145), (0.095, 0.168), (0.045, 0.178), (0.022, 0.18),
           (0.022, 0.215), (0.012, 0.22)]
    inn = [(r * 0.985, zz - 0.0015) for r, zz in out[:7]]
    lathe(f'shade_{px:+.2f}', out, (px, y, z), M['shade_out'], 'Lamps', 64, caps=False)
    lathe(f'shade_in_{px:+.2f}', inn, (px, y, z), M['shade_in'], 'Lamps', 64, caps=False)
    lathe(f'cord_{px:+.2f}', [(0, 0.22), (0.003, 0.22), (0.003, H - z), (0, H - z)], (px, y, z), M['black_matte'], 'Lamps', 12)
    bulb = lathe(f'bulb_{px:+.2f}', [(0, 0.03)] + [(0.034 * math.sin(t), 0.065 + 0.034 * math.cos(t)) for t in np.linspace(0.3, math.pi, 10)],
                 (px, y, z), M['bulb'], 'Lamps', 24)
    bulb.visible_shadow = False
    ld = bpy.data.lights.new(f'pendant_{px:+.2f}', 'POINT'); ld.energy = 22; ld.shadow_soft_size = 0.03; ld.color = WARM
    lo = bpy.data.objects.new(ld.name, ld); lo.location = (px, y, z + 0.065); link(lo, 'Lights')
    PENDANTS.append((px, y, z))

# ---------- Poly Haven furniture ----------
def place_group(objs, prefix, offset, rot_z=0.0, scale=1.0):
    """Linked duplicates of a multi-part asset, keeping each part's offset inside the group."""
    m = Matrix.Translation(Vector(offset)) @ Matrix.Rotation(rot_z, 4, 'Z') @ Matrix.Scale(scale, 4)
    for name, ob in objs.items():
        d = ob.copy(); d.name = prefix + name; d.matrix_world = m @ ob.matrix_world
        link(d, 'Props')


place_group(append_ph('wine_barrel_01', '2k'), 'barrel_', (BARREL[0], BARREL[1], 0), 0.5)

stool = append_ph('metal_stool_01', '1k')['metal_stool_01']
for k, a in enumerate((-0.27, -0.135, 0.0, 0.135, 0.27)):
    p = on_arc(R_FRONT + 0.42, a)
    dup(stool, f'stool_{k}', p, a + rng.uniform(-0.25, 0.25))

plant = {k: v for k, v in append_ph('potted_plant_02', '1k').items() if not k.endswith('_dirt')}   # _dirt is a spill on the floor
place_group(plant, 'plant_', (2.9, 2.75, 0), 0.4, 1.55)

# ---------- hero: AI sneakers (optional) + bottle on the barrel ----------
HERO = A('ai', 'hero_clean.blend')
if os.path.exists(HERO):
    with bpy.data.libraries.load(HERO, link=False) as (src, dst):
        dst.objects = ['hero']
    shoe = dst.objects[0]
    coll('_tpl_hero', exclude=True).objects.link(shoe)
    toe = math.radians(-158)
    perp = Vector((math.cos(toe + math.pi / 2), math.sin(toe + math.pi / 2), 0))
    fwd = Vector((math.cos(toe), math.sin(toe), 0))
    c = Vector((BARREL[0], BARREL[1], LID_Z)) + Vector((0.03, 0.02, 0))
    # clean_ai_model.py puts the toe at local +X, so the toe ends up pointing along `toe` (towards the last camera)
    dup(shoe, 'sneaker_R', c - perp * 0.062, toe + math.radians(4))
    dup(shoe, 'sneaker_L', c + perp * 0.062 + fwd * 0.025, toe - math.radians(5), (1, -1, 1))    # mirrored copy
else:
    print('BUILD no hero model at', HERO, '(skipped)')
hero_bottle = dup(TPL['bottle_cream'], 'hero_bottle', (BARREL[0] + 0.15, BARREL[1] + 0.13, LID_Z), math.radians(-40))

# ---------- light ----------
el, az = math.radians(17), math.radians(-28)
d = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), -math.sin(el)))
sd = bpy.data.lights.new('sun', 'SUN'); sd.energy = 7.0; sd.angle = math.radians(0.6); sd.color = (1.0, 0.74, 0.47)
so = bpy.data.objects.new('sun', sd); so.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); link(so, 'Lights')

pd = bpy.data.lights.new('window_portal', 'AREA'); pd.shape = 'RECTANGLE'; pd.size = wy1 - wy0; pd.size_y = wz1 - wz0
try:
    pd.cycles.is_portal = True
except AttributeError:
    pd.energy = 0
po = bpy.data.objects.new('window_portal', pd); po.location = (X0 - T / 2, (wy0 + wy1) / 2, (wz0 + wz1) / 2)
po.rotation_euler = Vector((1, 0, 0)).to_track_quat('-Z', 'Y').to_euler(); link(po, 'Lights')

world = bpy.data.worlds.new('sky'); scene.world = world; world.use_nodes = True
nt = world.node_tree; L = nt.links.new
bg = nt.nodes['Background']
env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(A('hdri', 'lonely_road_afternoon_puresky_2k.hdr'))
clamp = nt.nodes.new('ShaderNodeVectorMath'); clamp.operation = 'MINIMUM'; clamp.inputs[1].default_value = (25, 25, 25)   # drop the HDRI's own sun
lp = nt.nodes.new('ShaderNodeLightPath')
strength = nt.nodes.new('ShaderNodeMapRange'); strength.inputs['To Min'].default_value = 1.0; strength.inputs['To Max'].default_value = 3.0
L(env.outputs['Color'], clamp.inputs[0]); L(clamp.outputs['Vector'], bg.inputs['Color'])
L(lp.outputs['Is Camera Ray'], strength.inputs['Value']); L(strength.outputs['Result'], bg.inputs['Strength'])

# ---------- camera walk ----------
# (x, y) where you stand, (x, y, z) what you look at
KEYS = [((0.25, -2.65), (0.0, 3.2, 1.30)),
        ((-0.45, -2.15), (-0.15, 3.2, 1.22)),
        ((-1.00, -1.60), (0.35, 1.2, 0.95)),
        ((-0.95, -1.25), (0.03, -0.28, 0.88))]
cam, key_frames = make_camera(scene, KEYS, N_FRAMES, eye=EYE, lens=24, res=RES)

# ---------- hotspots -> web/frames.json ----------
# at = 3D anchor of the dot, from/to = scroll progress (0..1) where the dot may show
HOTSPOTS = [
    {"id": "sneakers", "title": "The Blanc 01", "text": "Hand-lasted white calf leather on a stitched cupsole. Made to wear, not to keep in the box.",
     "at": (BARREL[0] + 0.0, BARREL[1] - 0.03, LID_Z + 0.07), "from": 0.45, "to": 1.0},
    {"id": "whiskey", "title": "Single Barrel No. 12", "text": "One cask, 212 bottles. Charred oak, dried apricot and a long, warm finish.",
     "at": (BARREL[0] + 0.15, BARREL[1] + 0.13, LID_Z + 0.16), "from": 0.55, "to": 1.0},
    {"id": "backbar", "title": "The Back Bar", "text": "Every Hollow Oak release since day one, on black steel shelves made in the studio next door.",
     "at": (0.17, SH_Y - 0.05, 1.95), "from": 0.07, "to": 0.5},
]
seen = write_frames_json(scene, cam, key_frames, HOTSPOTS, os.path.join(ROOT, 'web', 'frames.json'), VERSION)

# ---------- report + save ----------
tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in bpy.data.objects if o.type == 'MESH' and o.users_collection and not o.users_collection[0].name.startswith('_tpl'))
print('BUILD objects', len(bpy.data.objects), 'scene tris (excl. templates)', tris, 'keys', key_frames)
print('BUILD missing images', missing_images())          # must be [] or the render shows pink surfaces
print('BUILD hotspot visible frames', seen)
bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
print('BUILD saved', BLEND)
