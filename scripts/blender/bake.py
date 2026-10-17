"""Bake the lounge for real-time WebGL (the Finely Crafted way): Cycles bakes the full diffuse look (colour x light, sun,
bounce, lamp pools) into textures, the browser shows them unlit and adds only reflections and glass on top.
Run: blender -b scene.blend -P blender/bake.py -- [--samples 256] [--scale 1.0]   (or double-click bake.cmd)
-> web3d/assets/lounge.glb (baked meshes + baked textures, draco), web3d/assets/live.glb (glass, bottles, lamps, plant),
   web3d/assets/env.hdr (room panorama for reflections), web3d/assets/walk.json (camera per frame + hotspots)"""
import bpy, bmesh, json, math, os, sys, time
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(ROOT, 'web3d', 'assets')
os.makedirs(OUT, exist_ok=True)
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
arg = lambda k, d: type(d)(ARGS[ARGS.index(k) + 1]) if k in ARGS else d
SAMPLES, SCALE = arg('--samples', 512), arg('--scale', 1.0)      # scale < 1 shrinks every bake for quick tests
STORE = 1 / 2                                                       # stored = radiance / 2 (sRGB 8-bit), web multiplies by 2
sys.path.insert(0, HERE)
from cycles_gpu import use_gpu

scene = bpy.context.scene
use_gpu(scene)
t0 = time.time()
log = lambda *a: print('BAKE %5.0fs' % (time.time() - t0), *a, flush=True)
# ---- EDIT for a new room: interior bounds, which objects get baked, which stay live ----
X0, X1, Y0, Y1, H = -3.5, 3.5, -3.0, 3.2, 3.2       # room interior (Blender metres), as in build_scene.py


def realize(ob):
    """Own mesh data, modifiers and transform applied, so each object can carry its own bake UVs and image."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.transform(ob.matrix_world)
    if ob.matrix_world.determinant() < 0:   # mirrored copies (the left sneaker) come out inside-out
        me.flip_normals()
    new = bpy.data.objects.new(ob.name + '_b', me)
    scene.collection.objects.link(new)
    return new


def drop_faces(ob, keep):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f)], context='FACES')
    bm.to_mesh(ob.data); bm.free()


def join(objs, name):
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, selected_objects=objs):
        bpy.ops.object.join()
    objs[0].name = objs[0].data.name = name
    return objs[0]


def only_uv(ob, name):
    """Make `name` the single UV map (it becomes TEXCOORD_0 in glTF)."""
    me = ob.data
    for uv in [u for u in me.uv_layers if u.name != name]:
        me.uv_layers.remove(uv)


def smart_uv(ob, margin):
    me = ob.data
    lm = me.uv_layers.new(name='LM')
    me.uv_layers.active = lm
    for o in scene.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')


# ---------- what gets baked ----------
src = {o.name: o for o in scene.objects if o.type == 'MESH' and o.visible_get()}   # templates live in excluded collections
ARCH = ['walls', 'plenum', 'ceiling_slats', 'window_frame', 'bar_toe', 'bar_body', 'bar_flutes', 'bar_top', 'shelf_frame']   # joined into one 4096 atlas (floor gets its own)
PROPS = [n for n in src if n.startswith(('barrel_', 'stool_', 'sneaker_'))]     # scanned/AI props: baked through their own UVs
LIVE = ('glass_', 'bottle_', 'bar_glass', 'bar_bottle', 'hero_bottle', 'shade', 'cord_', 'bulb_', 'plant_')   # not baked: glass, lamps, alpha leaves
jobs = []                                   # (object, image size)

floor = realize(src['floor'])
drop_faces(floor, lambda f: f.normal.z > 0.9)                 # only the walkable top is ever seen
me = floor.data; uv = me.uv_layers.new(name='LM')
for p in me.polygons:
    for li in p.loop_indices:
        c = me.vertices[me.loops[li].vertex_index].co
        uv.data[li].uv = ((c.x - (X0 - 0.2)) / 7.4, (c.y - (Y0 - 0.2)) / 6.6)
only_uv(floor, 'LM'); floor.name = floor.data.name = 'bk_floor'
jobs.append((floor, 4096))

room = [realize(src[n]) for n in ARCH]
inside = lambda f: X0 - 0.01 <= f.calc_center_median().x <= X1 + 0.01 and Y0 - 0.01 <= f.calc_center_median().y <= Y1 + 0.01
drop_faces(room[0], lambda f: inside(f) and f.calc_center_median().z < H + 0.001)   # wall faces looking into the room
drop_faces(room[1], lambda f: f.normal.z < -0.9)                                    # plenum underside
drop_faces(room[2], lambda f: f.normal.z < 0.9)                                     # slat tops sit against the plenum
room = join(room, 'bk_room')
smart_uv(room, 0.002)
only_uv(room, 'LM')
jobs.append((room, 4096))

for n in PROPS:
    ob = realize(src[n])
    only_uv(ob, 'UVMap')                    # Poly Haven and the AI sneaker come with their own non-overlapping atlas
    ob.data.uv_layers['UVMap'].name = 'LM'
    ob.name = ob.data.name = 'bk_' + n
    size = 2048 if n.startswith(('sneaker', 'barrel_wine_barrel_01')) and not n.endswith(('bung',)) else 1024
    jobs.append((ob, size))
log('prepared', len(jobs), 'bake jobs', [(j.name, s) for j, s in jobs])

# ---------- bake ----------
scene.render.engine = 'CYCLES'
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = False
bake = scene.render.bake
bake.use_pass_direct = bake.use_pass_indirect = bake.use_pass_color = True
bake.margin = 8
bake.use_clear = True
for o in list(src.values()):                # the originals keep lighting the bakes but hide from camera-only stuff
    pass


def gauss(a, sigma):
    r = int(sigma * 3 + 0.5)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2); k /= k.sum()
    for axis in (0, 1):
        p = np.pad(a, [(r, r) if i == axis else (0, 0) for i in range(a.ndim)], mode='edge')
        a = sum(w * np.take(p, np.arange(j, j + a.shape[axis]), axis=axis) for j, w in enumerate(k))
    return a


def denoise(lin, sigma=0.8):
    """Cycles does not denoise bakes: clamp fireflies, then a light blur that never mixes in the empty gutter texels."""
    mask = (lin.sum(axis=2, keepdims=True) > 0).astype(np.float32)
    soft = gauss(lin * mask, 2.0) / np.maximum(gauss(mask, 2.0), 1e-4)
    lin = np.where(lin > soft * 2.5 + 0.02, soft, lin)
    return gauss(lin * mask, sigma) / np.maximum(gauss(mask, sigma), 1e-4) * mask


stats = {}
for ob, size in jobs:
    size = max(256, int(size * SCALE))
    img = bpy.data.images.new('bake_' + ob.name, size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    for m in ob.data.materials:
        node = m.node_tree.nodes.new('ShaderNodeTexImage'); node.name = 'BAKE_TARGET'; node.image = img
        m.node_tree.nodes.active = node
    src_ob = src.get(ob.name[3:])
    hidden = []
    for o in scene.objects:                 # the realized copy replaces its original while it bakes
        if o.type == 'MESH' and o.name in src and (o.name == ob.name[3:] or (ob.name == 'bk_room' and o.name in ARCH) or (ob.name == 'bk_floor' and o.name == 'floor')):
            o.hide_render = True; hidden.append(o)
    for o in scene.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    scene.cycles.samples = SAMPLES * 4 if ob.name in ('bk_floor', 'bk_room') else SAMPLES   # big smooth surfaces show grain first
    bpy.ops.object.bake(type='DIFFUSE', uv_layer='LM')
    for o in hidden:
        o.hide_render = False
    for m in ob.data.materials:
        m.node_tree.nodes.remove(m.node_tree.nodes['BAKE_TARGET'])
    px = np.empty(size * size * 4, np.float32); img.pixels.foreach_get(px)
    lin = denoise(px.reshape(size, size, 4)[..., :3], 1.6 if ob.name == 'bk_room' else 0.8)   # plaster walls: smooth out bake grain
    stats[ob.name] = (float(np.percentile(lin[lin.sum(2) > 0], 99)), float(lin.max()))
    v = np.clip(lin * STORE, 0, 1)
    srgb = np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)
    srgb += (np.random.default_rng(1).random(srgb.shape) - 0.5) / 255
    out = bpy.data.images.new('tex_' + ob.name, size, size, alpha=False)
    out.pixels.foreach_set(np.concatenate([np.clip(srgb, 0, 1), np.ones((size, size, 1))], axis=2).astype(np.float32).ravel())
    out.filepath_raw = os.path.join(OUT, 'tex', ob.name + '.png'); os.makedirs(os.path.dirname(out.filepath_raw), exist_ok=True)
    out.file_format = 'PNG'; out.save(); out.pack()
    bpy.data.images.remove(img)
    if ob.name in ('bk_floor', 'bk_room'):
        # the web material: just the baked picture
        m = bpy.data.materials.new('baked_' + ob.name); m.use_nodes = True
        t = m.node_tree.nodes.new('ShaderNodeTexImage'); t.image = out
        m.node_tree.links.new(t.outputs['Color'], m.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
        ob.data.materials.clear(); ob.data.materials.append(m)
    else:
        # props keep their own metal/roughness/normal maps for real-time reflections; the baked look rides in emission
        for k, m in enumerate(ob.data.materials):
            m = m.copy(); m.name = 'baked_' + ob.name + ('_%d' % k if k else '')
            b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            t = m.node_tree.nodes.new('ShaderNodeTexImage'); t.image = out
            m.node_tree.links.new(t.outputs['Color'], b.inputs['Emission Color'])
            b.inputs['Emission Strength'].default_value = 1.0
            ob.data.materials[k] = m
    log('baked', ob.name, size, 'p99 %.2f max %.1f' % stats[ob.name])

# ---------- export ----------
def export(objs, name, draco=True):
    for o in scene.objects:
        o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]
    path = os.path.join(OUT, name)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_image_format='WEBP',
                              export_image_quality=88, export_draco_mesh_compression_enable=draco, export_draco_mesh_compression_level=6,
                              export_cameras=False, export_lights=False, export_apply=True, export_yup=True, export_materials='EXPORT')
    log('exported', name, os.path.getsize(path) // 1024, 'KB')


for ob, _ in jobs:                          # 150k-triangle AI sneakers: the baked picture carries the detail, 15 % of the mesh is plenty
    if ob.name.startswith('bk_sneaker'):
        d = ob.modifiers.new('web', 'DECIMATE'); d.ratio = 0.15
export([ob for ob, _ in jobs], 'lounge.glb')
live = [o for n, o in src.items() if n.startswith(LIVE)]
export(live, 'live.glb')

# ---------- camera walk, hotspots ----------
three = lambda v: [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]
C = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))
cam = scene.camera
frames = []
for f in range(scene.frame_start, scene.frame_end + 1):
    scene.frame_set(f)
    q = (C @ cam.matrix_world.to_3x3()).to_quaternion()
    frames.append({'p': three(cam.matrix_world.translation), 'q': [round(q.x, 6), round(q.y, 6), round(q.z, 6), round(q.w, 6)]})
meta = json.load(open(os.path.join(ROOT, 'web', 'frames.json'), encoding='utf-8'))   # written by build_scene.py
spots = []
for h in meta['hotspots']:
    spots.append({**{k: h[k] for k in ('id', 'title', 'text', 'from', 'to')}, 'vis': [int(u is not None) for u in h['uv']]})   # occlusion per frame, from build_all
for s, h in zip(spots, meta['hotspots']):
    s['at'] = three(h['at'])
hfov = 2 * math.degrees(math.atan(cam.data.sensor_width / 2 / cam.data.lens))
json.dump({'frames': frames, 'hfov': round(hfov, 3), 'keys': meta['keys'], 'hotspots': spots}, open(os.path.join(OUT, 'walk.json'), 'w'))
log('walk', len(frames), 'frames, hfov %.2f' % hfov)

# ---------- room panorama for reflections ----------
cd = bpy.data.cameras.new('probe'); cd.type = 'PANO'
try:
    cd.panorama_type = 'EQUIRECTANGULAR'
except AttributeError:
    cd.cycles.panorama_type = 'EQUIRECTANGULAR'
probe = bpy.data.objects.new('probe', cd); scene.collection.objects.link(probe)
probe.location = (0.0, 0.2, 1.3); probe.rotation_euler = (math.radians(90), 0, 0)
scene.camera = probe
r = scene.render
r.resolution_x, r.resolution_y, r.resolution_percentage = 1024, 512, 100
scene.cycles.samples = 128; scene.cycles.use_denoising = True
r.image_settings.file_format = 'HDR'
r.filepath = os.path.join(OUT, 'env.hdr')
r.use_overwrite = True; r.use_placeholder = False
bpy.ops.render.render(write_still=True)
log('env', os.path.getsize(r.filepath) // 1024, 'KB')
log('done')
