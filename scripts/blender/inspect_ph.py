"""Print what each downloaded Poly Haven .blend contains: objects, sizes, materials. Run: blender -b -P blender/inspect_ph.py"""
import bpy, glob, os
from mathutils import Vector

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'ph')
for path in sorted(glob.glob(os.path.join(ROOT, '*', '*.blend'))):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = src.objects
    print('==', os.path.basename(path))
    for ob in dst.objects:
        if ob is None:
            continue
        if ob.type == 'MESH':
            pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            lo = [min(p[i] for p in pts) for i in range(3)]
            hi = [max(p[i] for p in pts) for i in range(3)]
            print(f'  {ob.name:32s} parent={ob.parent.name if ob.parent else "-":20s} size={[round(h - l, 3) for l, h in zip(lo, hi)]} '
                  f'min={[round(v, 3) for v in lo]} tris={sum(len(p.vertices) - 2 for p in ob.data.polygons)} '
                  f'mats={[m.name for m in ob.data.materials if m]}')
        else:
            print(f'  {ob.name:32s} type={ob.type}')
    for ob in dst.objects:
        if ob:
            bpy.data.objects.remove(ob)
