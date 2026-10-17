"""Bake HẺM for the real-time page. The shop is big (14 x 10 m, 4.2 m high), so unlike the lounge the colour is not baked in:
architecture = sharp tiling albedo (UV0) x baked light (lightmap, UV1), the clothes = their own texture x light baked per vertex,
small scanned props = full colour bake. Run: blender -b scene.blend -P blender/bake_lightmap.py -- [--samples 256] [--scale 1.0]
-> web3d/assets/hem.glb, live.glb (neon, mirror, plants), env.hdr, sky.hdr, walk.json"""
import bpy, bmesh, json, math, os, sys, time
import numpy as np
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cycles_gpu import use_gpu
from common import A, ROOT

OUT = os.path.join(ROOT, 'web3d', 'assets')
os.makedirs(os.path.join(OUT, 'tex'), exist_ok=True)
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
arg = lambda k, d: type(d)(ARGS[ARGS.index(k) + 1]) if k in ARGS else d
SAMPLES, SCALE = arg('--samples', 256), arg('--scale', 1.0)
LSTORE = 1 / 6          # lightmaps hold light / 6 (the sunny lane reaches ~5)
STORE = 1 / 2           # colour bakes and vertex light hold radiance / 2
H = 4.2

scene = bpy.context.scene
use_gpu(scene)
t0 = time.time()
log = lambda *a: print('BAKE %5.0fs' % (time.time() - t0), *a, flush=True)
src = [o for o in scene.objects if o.type == 'MESH' and o.visible_get()]
named = lambda *pre: [o for o in src if o.name.startswith(pre)]


def realize(ob, name):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.transform(ob.matrix_world)
    if ob.matrix_world.determinant() < 0:
        me.flip_normals()
    for i, s in enumerate(ob.material_slots):          # object-linked recolours become the mesh's own
        me.materials[i] = s.material
    new = bpy.data.objects.new(name, me)
    new.visible_shadow = ob.visible_shadow             # the houses across the lane let the sun through
    scene.collection.objects.link(new)
    ob.hide_render = True                               # the copy stands in for it from now on
    return new


def drop_faces(ob, keep):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f)], context='FACES')
    bm.to_mesh(ob.data); bm.free()


def join(objs, name):
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, selected_objects=objs):
            bpy.ops.object.join()
    objs[0].name = objs[0].data.name = name
    return objs[0]


def select(objs):
    for o in scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def smart_uv(ob, margin):
    lm = ob.data.uv_layers.new(name='LM'); ob.data.uv_layers.active = lm
    select([ob])
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode='OBJECT')


def planar_lm(ob):
    me = ob.data; uv = me.uv_layers.new(name='LM')
    xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    for li, l in enumerate(me.loops):
        c = me.vertices[l.vertex_index].co
        uv.data[li].uv = ((c.x - x0) / (x1 - x0) * 0.996 + 0.002, (c.y - y0) / (y1 - y0) * 0.996 + 0.002)


def keep_uvs(ob, names):
    for u in [u for u in ob.data.uv_layers if u.name not in names]:
        ob.data.uv_layers.remove(u)


def bsdf(m):
    return next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)


# ---------- what goes where ----------
interior = lambda f: -7.01 <= f.calc_center_median().x <= 7.01 and -5.26 <= f.calc_center_median().y <= 5.01
not_bottom = lambda f: not (f.normal.z < -0.9 and f.calc_center_median().z < 0.02)
P_ALLEY = Vector((0, -8.5, 1.6))
from_alley = lambda f: f.normal.dot(P_ALLEY - f.calc_center_median()) > 0

ATLAS = []          # (object, lightmap size, denoise sigma)
floor = realize(scene.objects['floor_floor'], 'lf_floor')
drop_faces(floor, lambda f: f.normal.z > 0.9)
planar_lm(floor); ATLAS.append((floor, 4096, 1.4))

alley = realize(scene.objects['ex_alley'], 'lm_alley')
drop_faces(alley, lambda f: f.normal.z > 0.9)
planar_lm(alley); ATLAS.append((alley, 2048, 1.2))

walls = realize(scene.objects['in_wall'], 'lm_walls')
drop_faces(walls, lambda f: interior(f) and not_bottom(f) and f.calc_center_median().z < H - 0.001)
smart_uv(walls, 0.002); ATLAS.append((walls, 4096, 1.6))

ceil = [realize(o, 'c_' + o.name) for o in named('ceil_') if o.name != 'ceil_lens']
drop_faces(ceil[[o.name for o in ceil].index('c_ceil_ceiling')], lambda f: f.normal.z < -0.9 and interior(f))
ceil = join(ceil, 'lm_ceil'); smart_uv(ceil, 0.003); ATLAS.append((ceil, 2048, 1.2))

fix = [realize(o, 'f_' + o.name) for o in named('in_', 'deck_', 'aboard', 'curtain_') if o.name != 'in_wall']
for o in fix:
    drop_faces(o, not_bottom)
fix = join(fix, 'lm_fix'); smart_uv(fix, 0.002); ATLAS.append((fix, 4096, 1.0))

ext = [realize(o, 'e_' + o.name) for o in named('ex_') if o.name != 'ex_alley']
for o in ext:
    drop_faces(o, from_alley)
ext = join(ext, 'lm_ext'); smart_uv(ext, 0.002); ATLAS.append((ext, 2048, 1.0))
houses = [realize(o, 'h_' + o.name) for o in named('exh_')]
for o in houses:
    drop_faces(o, from_alley)
houses = join(houses, 'lm_houses'); smart_uv(houses, 0.003); ATLAS.append((houses, 2048, 1.0))

PROPS = [realize(o, 'bp_' + o.name[3:]) for o in named('ph_') if not any(k in o.name for k in ('potted_plant', 'metal_stool'))]
GOODS = [realize(o, 'vc_' + o.name) for o in named('rail_', 'rack_', 'tees_', 'mq_', 'shoe_', 'scooter')]
LIVE = named('neon_', 'ceil_lens', 'mirror_', 'ph_potted_plant', 'ph_metal_stool')
log('atlases', [(o.name, s, len(o.data.polygons), len(o.data.materials)) for o, s, _ in ATLAS])
log('props', len(PROPS), 'goods', len(GOODS), 'live', len(LIVE))

# ---------- bake ----------
scene.render.engine = 'CYCLES'
scene.cycles.use_denoising = False
bk = scene.render.bake
bk.margin = 8
bk.use_clear = True
# Cycles divides the diffuse light by the diffuse colour when the colour pass is off: fully metallic means 0 / 0
for m in bpy.data.materials:
    b = bsdf(m) if m.use_nodes else None
    if b and not b.inputs['Metallic'].links and b.inputs['Metallic'].default_value > 0.9:
        b.inputs['Metallic'].default_value = 0.9


def gauss(a, sigma):
    r = int(sigma * 3 + 0.5)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2); k /= k.sum()
    for axis in (0, 1):
        p = np.pad(a, [(r, r) if i == axis else (0, 0) for i in range(a.ndim)], mode='edge')
        a = sum(w * np.take(p, np.arange(j, j + a.shape[axis]), axis=axis) for j, w in enumerate(k))
    return a


def denoise(lin, sigma):
    mask = (lin.sum(axis=2, keepdims=True) > 0).astype(np.float32)
    soft = gauss(lin * mask, 2.0) / np.maximum(gauss(mask, 2.0), 1e-4)
    lin = np.where(lin > soft * 2.5 + 0.02, soft, lin)
    return gauss(lin * mask, sigma) / np.maximum(gauss(mask, sigma), 1e-4) * mask


def to_png(lin, store, name):
    size = lin.shape[0]
    v = np.clip(lin * store, 0, 1)
    s = np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)
    s += (np.random.default_rng(1).random(s.shape) - 0.5) / 255
    out = bpy.data.images.new(name, size, size, alpha=False)
    out.pixels.foreach_set(np.concatenate([np.clip(s, 0, 1), np.ones((size, size, 1))], axis=2).astype(np.float32).ravel())
    out.filepath_raw = os.path.join(OUT, 'tex', name + '.png'); out.file_format = 'PNG'; out.save(); out.pack()
    return out


def bake_image(ob, size, color, samples):
    size = max(128, int(size * SCALE))
    img = bpy.data.images.new('bake_' + ob.name, size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    for m in ob.data.materials:
        n = m.node_tree.nodes.new('ShaderNodeTexImage'); n.name = 'BAKE_TARGET'; n.image = img
        m.node_tree.nodes.active = n
    select([ob])
    bk.target = 'IMAGE_TEXTURES'
    bk.use_pass_direct = bk.use_pass_indirect = True; bk.use_pass_color = color
    scene.cycles.samples = samples
    bpy.ops.object.bake(type='DIFFUSE', uv_layer='LM')
    for m in ob.data.materials:
        m.node_tree.nodes.remove(m.node_tree.nodes['BAKE_TARGET'])
    px = np.empty(size * size * 4, np.float32); img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(size, size, 4)[..., :3]


LMAP = {}
for ob, size, sigma in ATLAS:
    lin = denoise(bake_image(ob, size, False, SAMPLES * 2), sigma)
    lit = lin[lin.sum(2) > 0]
    log('baked', ob.name, 'light p50 %.2f p99 %.2f max %.1f' % (np.percentile(lit, 50), np.percentile(lit, 99), lit.max()))
    LMAP[ob.name] = to_png(lin, LSTORE, ob.name)

BAKED = {}
for ob in PROPS:
    keep_uvs(ob, [ob.data.uv_layers[0].name]); ob.data.uv_layers[0].name = 'LM'
    lin = denoise(bake_image(ob, 1024 if 'aircon' not in ob.name else 512, True, SAMPLES), 0.8)
    BAKED[ob.name] = to_png(lin, STORE, ob.name)
    log('baked', ob.name)

for ob in GOODS:                     # light per vertex: the garment's own texture keeps all the detail
    me = ob.data
    for ca in list(me.color_attributes):
        me.color_attributes.remove(ca)
    ca = me.color_attributes.new('LIGHT', 'FLOAT_COLOR', 'POINT')
    me.color_attributes.active_color = ca; me.color_attributes.render_color_index = 0
select(GOODS)
bk.target = 'VERTEX_COLORS'
bk.use_pass_direct = bk.use_pass_indirect = True; bk.use_pass_color = False
scene.cycles.samples = SAMPLES * 2
bpy.ops.object.bake(type='DIFFUSE')
allv = []; allv_by = []
for ob in GOODS:
    ca = ob.data.color_attributes['LIGHT']
    v = np.empty(len(ca.data) * 4, np.float32); ca.data.foreach_get('color', v); v = v.reshape(-1, 4)
    allv.append(v[:, :3].copy()); allv_by.append(allv[-1])
    v[:, :3] = np.clip(v[:, :3] * STORE, 0, 1); v[:, 3] = 1
    ca.data.foreach_set('color', v.ravel())
allv = np.concatenate(allv)
log('baked goods per vertex, light p50 %.2f p99 %.2f' % (np.percentile(allv, 50), np.percentile(allv, 99)))
for ob, v in zip(GOODS[::10], allv_by[::10]):
    log('  ', ob.name, 'p50 %.3f p90 %.3f' % (np.percentile(v, 50), np.percentile(v, 90)))

# ---------- web materials ----------
def srgb2lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


TILES = {}


def tile(m, size):
    """The material's albedo as one tile, the same maths as common.pbr (grey / tint) and the paint multiply."""
    if m.name in TILES:
        return TILES[m.name]
    p = json.loads(m['pbr'])
    im = bpy.data.images.load(A('tex', f"{p['tex']}_Diffuse.jpg"), check_existing=True)
    w, h = im.size
    raw = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(raw); raw = raw.reshape(h, w, 4)[..., :3]
    lin = srgb2lin(raw); W = np.array([0.2126, 0.7152, 0.0722], np.float32)
    col = lin
    if p['grey']:
        mean = float((raw @ W).mean())
        soft = mean * (1 - p['var']) + (lin @ W) * p['var']
        col = soft[..., None] * (np.array(p['grey']) / mean)
    if p['tint']:
        col = col * np.array(p['tint'])
    if 'mul' in m:
        col = col * np.array(list(m['mul']))
    v = np.clip(col, 0, 1)
    s = np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)
    out = bpy.data.images.new('alb_' + m.name, w, h, alpha=False)
    out.pixels.foreach_set(np.concatenate([s, np.ones((h, w, 1))], 2).astype(np.float32).ravel())
    out.scale(size, size); out.pack()
    TILES[m.name] = (out, p['scale'])
    return TILES[m.name]


def web_mat(name, base=None, color=(1, 1, 1, 1), emit=None, base_uv='UVMap', emit_uv='LM'):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']; L = nt.links.new
    b.inputs['Base Color'].default_value = color
    b.inputs['Roughness'].default_value = 1.0
    for img_, sock, uvn in ((base, 'Base Color', base_uv), (emit, 'Emission Color', emit_uv)):
        if img_ is None:
            continue
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = img_
        u = nt.nodes.new('ShaderNodeUVMap'); u.uv_map = uvn
        L(u.outputs['UV'], t.inputs['Vector']); L(t.outputs['Color'], b.inputs[sock])
    if emit is not None:
        b.inputs['Emission Strength'].default_value = 1.0
    return m


for ob, _, _ in ATLAS:
    me = ob.data
    keep_uvs(ob, ['UVMap', 'LM'])
    if 'UVMap' not in me.uv_layers:
        uv = me.uv_layers.new(name='UVMap')
    # glTF TEXCOORD_0 must be the albedo UVs: rebuild the order UVMap, LM
    if me.uv_layers[0].name != 'UVMap':
        tmp = me.uv_layers.new(name='LM2'); tmp.data.foreach_set('uv', np.array([d.uv[:] for d in me.uv_layers['LM'].data]).ravel())
        me.uv_layers.remove(me.uv_layers['LM']); tmp.name = 'LM'
    scale_of = {}
    for i, m in enumerate(me.materials):
        b = bsdf(m)
        if 'pbr' in m:
            img_, sc = tile(m, 2048 if m.name in ('wall', 'floor', 'alley') else 1024)
            new = web_mat(f'w_{ob.name}_{m.name}', img_, emit=LMAP[ob.name]); scale_of[i] = sc
        else:
            t = next((n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.outputs['Color'].links
                      and n.outputs['Color'].links[0].to_socket.name == 'Base Color'), None)
            if t is not None:
                new = web_mat(f'w_{ob.name}_{m.name}', t.image, emit=LMAP[ob.name])
            else:
                new = web_mat(f'w_{ob.name}_{m.name}', color=tuple(b.inputs['Base Color'].default_value), emit=LMAP[ob.name])
        me.materials[i] = new
    uv = me.uv_layers['UVMap'].data
    for p in me.polygons:                       # planar metre UVs -> tile repeats, per material
        sc = scale_of.get(p.material_index)
        if sc:
            for li in p.loop_indices:
                uv[li].uv = uv[li].uv * sc
for ob in PROPS:
    me = ob.data
    img_ = BAKED[ob.name]
    for i in range(len(me.materials)):
        me.materials[i] = web_mat(f'w_{ob.name}_{i}', img_, base_uv='LM')
for ob in GOODS:
    me = ob.data
    keep_uvs(ob, [me.uv_layers[0].name])
    for i, m in enumerate(me.materials):
        name = 'g_' + m.name
        if name not in bpy.data.materials:
            t = next(n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.outputs['Color'].links
                     and n.outputs['Color'].links[0].to_socket.name == 'Base Color')
            im = t.image.copy(); im.name = name
            if ob.name.startswith('vc_shoe'):
                im.scale(512, 512)
            im.pack()
            web_mat(name, im, base_uv=me.uv_layers[0].name)
        me.materials[i] = bpy.data.materials[name]


# ---------- export ----------
def export(objs, name, colors=False):
    select(objs)
    path = os.path.join(OUT, name)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_image_format='WEBP',
                              export_image_quality=88, export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
                              export_cameras=False, export_lights=False, export_apply=True, export_yup=True, export_materials='EXPORT',
                              export_vertex_color='ACTIVE' if colors else 'NONE')
    log('exported', name, os.path.getsize(path) // 1024, 'KB')


export([o for o, _, _ in ATLAS] + PROPS, 'hem.glb')
export(GOODS, 'goods.glb', colors=True)
for m in bpy.data.materials:                     # live things keep their real materials (metallic restored for the mirror)
    if m.name in ('mirror', 'stainless', 'duct'):
        bsdf(m).inputs['Metallic'].default_value = 1.0
export(LIVE, 'live.glb')

# ---------- camera walk, hotspots ----------
three = lambda v: [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]
C = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))
cam = scene.camera
frames = []
for f in range(scene.frame_start, scene.frame_end + 1):
    scene.frame_set(f)
    q = (C @ cam.matrix_world.to_3x3()).to_quaternion()
    frames.append({'p': three(cam.matrix_world.translation), 'q': [round(q.x, 6), round(q.y, 6), round(q.z, 6), round(q.w, 6)]})
meta = json.load(open(os.path.join(ROOT, 'web', 'frames.json'), encoding='utf-8'))
spots = [{**{k: h[k] for k in ('id', 'title', 'text', 'from', 'to')}, 'vis': [int(u is not None) for u in h['uv']], 'at': three(h['at'])}
         for h in meta['hotspots']]
hfov = 2 * math.degrees(math.atan(cam.data.sensor_width / 2 / cam.data.lens))
json.dump({'frames': frames, 'hfov': round(hfov, 3), 'keys': meta['keys'], 'hotspots': spots}, open(os.path.join(OUT, 'walk.json'), 'w'))
log('walk', len(frames), 'frames, hfov %.2f' % hfov)

# ---------- sky (seen above the lane) and the shop panorama for reflections ----------
sky = bpy.data.images.load(A('hdri', 'german_town_street_2k.hdr'))
sky.scale(1024, 512)
sky.filepath_raw = os.path.join(OUT, 'sky.hdr'); sky.file_format = 'HDR'; sky.save()
log('sky', os.path.getsize(sky.filepath_raw) // 1024, 'KB')
cd = bpy.data.cameras.new('probe'); cd.type = 'PANO'
try:
    cd.panorama_type = 'EQUIRECTANGULAR'
except AttributeError:
    cd.cycles.panorama_type = 'EQUIRECTANGULAR'
probe = bpy.data.objects.new('probe', cd); scene.collection.objects.link(probe)
probe.location = (0.0, 0.0, 1.5); probe.rotation_euler = (math.radians(90), 0, 0)
for o in scene.objects:                          # the panorama sees the real scene, not the bake copies
    if o.type == 'MESH':
        o.hide_render = o.name.startswith(('lf_', 'lm_', 'bp_', 'vc_'))
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
