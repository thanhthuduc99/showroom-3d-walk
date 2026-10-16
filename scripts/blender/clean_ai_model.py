"""Clean an AI-made GLB (e.g. from tools/fal3d.py) into one object ready to drop into the scene, plus a studio still for review.
Join, decimate, longest horizontal axis on X, scaled to a real length in metres, base at z = 0, centred, matte material.
Run: blender -b -P blender/clean_ai_model.py -- <in.glb> <length_m> [--tris=150000] [--rough=0.5] [--albedo=0.86] [--shoe]
  --shoe    put the tall end (heel collar) at -X so the toe points along +X
-> assets/ai/hero_clean.blend (object 'hero') + renders/look/hero_studio.png"""
import bpy, os, sys, math
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import A, ROOT
from cycles_gpu import use_gpu

ARGS = sys.argv[sys.argv.index('--') + 1:]
POS = [a for a in ARGS if not a.startswith('--')]
OPT = {a[2:].split('=')[0]: (a.split('=', 1)[1] if '=' in a else True) for a in ARGS if a.startswith('--')}
SRC, LENGTH = os.path.abspath(POS[0]), float(POS[1])
TARGET_TRIS = int(OPT.get('tris', 150000))
ROUGH, ALBEDO = float(OPT.get('rough', 0.5)), float(OPT.get('albedo', 0.86))

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
for o in bpy.context.scene.objects:
    o.select_set(o in meshes)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
ob = bpy.context.view_layer.objects.active
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in list(bpy.context.scene.objects):
    if o is not ob:
        bpy.data.objects.remove(o)

tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
print('CLEAN raw tris', tris, 'mats', [m.name for m in ob.data.materials])
if tris > TARGET_TRIS:
    mod = ob.modifiers.new('dec', 'DECIMATE'); mod.ratio = TARGET_TRIS / tris
    bpy.ops.object.modifier_apply(modifier=mod.name)


def bounds():
    vs = [v.co for v in ob.data.vertices]
    return Vector([min(v[i] for v in vs) for i in range(3)]), Vector([max(v[i] for v in vs) for i in range(3)])


lo, hi = bounds()
size = hi - lo
print('CLEAN size before', [round(s, 3) for s in size])
if size.y > size.x:                      # longest horizontal axis on X
    ob.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Z'))
if 'shoe' in OPT:                        # the heel side has the tall collar: put it at -X
    lo, hi = bounds()
    mid = (lo.x + hi.x) / 2
    vs = ob.data.vertices
    top_lo = max((v.co.z for v in vs if v.co.x < mid), default=0)
    top_hi = max((v.co.z for v in vs if v.co.x >= mid), default=0)
    if top_hi > top_lo:
        ob.data.transform(Matrix.Rotation(math.pi, 4, 'Z'))
lo, hi = bounds()
s = LENGTH / (hi.x - lo.x)
c = (lo + hi) / 2
ob.data.transform(Matrix.Scale(s, 4) @ Matrix.Translation(Vector((-c.x, -c.y, -lo.z))))
lo, hi = bounds()
print('CLEAN size after', [round(v, 3) for v in (hi - lo)])
ob.name = ob.data.name = 'hero'
for p in ob.data.polygons:
    p.use_smooth = True

for m in ob.data.materials:
    if not (m and m.node_tree):
        continue
    nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not b:
        continue
    for name in ('Metallic', 'Roughness'):           # AI PBR maps tend to read as shiny plastic: flatten them
        for l in list(b.inputs[name].links):
            nt.links.remove(l)
    b.inputs['Metallic'].default_value = 0.0
    b.inputs['Roughness'].default_value = ROUGH
    b.inputs['Specular IOR Level'].default_value = 0.45
    # keep white below paper white so it holds detail under the sun
    src = b.inputs['Base Color'].links[0].from_socket if b.inputs['Base Color'].links else None
    if src:
        vm = nt.nodes.new('ShaderNodeVectorMath'); vm.operation = 'MULTIPLY'; vm.inputs[1].default_value = (ALBEDO, ALBEDO, ALBEDO)
        nt.links.new(src, vm.inputs[0]); nt.links.new(vm.outputs['Vector'], b.inputs['Base Color'])

for im in bpy.data.images:
    if im.source in ('FILE', 'GENERATED') or im.packed_file:
        im.pack()
os.makedirs(A('ai'), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=A('ai', 'hero_clean.blend'), compress=True)

# studio still for review: grey sweep, 3 area lights. The rig was tuned on a 0.285 m sneaker, k scales it.
scene = bpy.context.scene
k = LENGTH / 0.285
bpy.ops.mesh.primitive_plane_add(size=6 * k)
fm = bpy.data.materials.new('sweep'); fm.use_nodes = True
fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.35, 0.35, 0.36, 1)
bpy.context.active_object.data.materials.append(fm)
for name, loc, e, size in (('key', (0.6, -0.8, 0.9), 60, 0.6), ('fill', (-0.7, -0.4, 0.5), 15, 1.0), ('rim', (-0.3, 0.8, 0.7), 35, 0.4)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = e * k * k; ld.size = size * k
    lo_ = bpy.data.objects.new(name, ld); lo_.location = Vector(loc) * k
    lo_.rotation_euler = (Vector((0, 0, 0.05 * k)) - lo_.location).to_track_quat('-Z', 'Y').to_euler()
    scene.collection.objects.link(lo_)
cd = bpy.data.cameras.new('cam'); cd.lens = 70
cam = bpy.data.objects.new('cam', cd); cam.location = Vector((0.75, -0.55, 0.42)) * k
cam.rotation_euler = (Vector((0.0, 0.0, 0.06 * k)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene.collection.objects.link(cam); scene.camera = cam
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.15
scene.render.engine = 'CYCLES'; use_gpu(scene)
scene.cycles.samples = 128
scene.render.resolution_x, scene.render.resolution_y = 1200, 800
scene.view_settings.view_transform = 'AgX'
scene.render.filepath = os.path.join(ROOT, 'renders', 'look', 'hero_studio.png')
bpy.ops.render.render(write_still=True)
print('CLEAN done', A('ai', 'hero_clean.blend'))
