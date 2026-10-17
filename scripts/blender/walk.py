"""Camera walk at eye height + hotspot projection -> web/frames.json. Imported by build_scene.py.

keys: [((x, y), (tx, ty, tz)), ...]  where you stand (metres, Z up) and what you look at.
Position is a Catmull-Rom through the stand points. The gaze is interpolated as yaw / pitch / distance:
interpolating the look-at points instead makes the camera dip to the floor whenever the head turns > ~90 degrees.
Frames are spaced by walking cost (metres + 0.7 m per radian of head turn), with a soft landing on the last quarter."""
import json, math, os
import bpy
import numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from common import link

TURN_COST = 0.7          # 1 radian of head turn counts as 0.7 m of walking


def catmull(pts, t):
    n = len(pts); i = min(int(t), n - 2); u = t - i
    p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, n - 1)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)


def ease(u):
    """Linear, then a soft landing over the last quarter (the hero shot lingers)."""
    a = 1 / (1 - 1.5 * 0.0625)
    return a * u if u < 0.75 else a * 0.75 + a * (u - 0.75) - 1.5 * a * (u - 0.75) ** 2


def walk(keys, n, eye):
    """n camera shots (position, view direction) and the frame index nearest to each key."""
    pos = [np.array([x, y, eye]) for (x, y), _ in keys]
    look = []
    for (x, y), (tx, ty, tz) in keys:
        dx, dy, dz = tx - x, ty - y, tz - eye
        look.append([math.atan2(dy, dx), math.atan2(dz, math.hypot(dx, dy)), math.sqrt(dx * dx + dy * dy + dz * dz)])
    look = np.array(look); look[:, 0] = np.unwrap(look[:, 0]); look = list(look)
    ts = np.linspace(0, len(keys) - 1, 20000)
    P = np.array([catmull(pos, t) for t in ts]); Lk = np.array([catmull(look, t) for t in ts])
    dirs = np.stack([np.cos(Lk[:, 1]) * np.cos(Lk[:, 0]), np.cos(Lk[:, 1]) * np.sin(Lk[:, 0]), np.sin(Lk[:, 1])], 1)
    step = np.linalg.norm(np.diff(P, axis=0), axis=1) + TURN_COST * np.arccos(np.clip((dirs[1:] * dirs[:-1]).sum(1), -1, 1))
    cost = np.concatenate([[0], np.cumsum(step)])
    idx = [min(np.searchsorted(cost, ease(i / (n - 1)) * cost[-1]), len(ts) - 1) for i in range(n)]
    shots = [(P[j], dirs[j]) for j in idx]
    key_frames = [int(np.argmin([abs(j - np.searchsorted(ts, k)) for j in idx])) for k in range(len(keys))]
    return shots, key_frames


def make_camera(scene, keys, n, eye=1.5, lens=24.0, res=(1600, 900)):
    """Camera keyframed on every frame (rotation set per frame, no Track-To). Returns the key frame indices."""
    cd = bpy.data.cameras.new('cam'); cd.lens = lens; cd.sensor_width = 36; cd.clip_start = 0.05
    cam = bpy.data.objects.new('cam', cd); link(cam, 'Cameras'); scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = res
    shots, key_frames = walk(keys, n, eye)
    scene.frame_start, scene.frame_end = 0, n - 1
    prev = None
    for f, (p, dvec) in enumerate(shots):
        cam.location = Vector(p)
        q = Vector(dvec).to_track_quat('-Z', 'Y')
        e = q.to_euler('XYZ', prev) if prev else q.to_euler()      # compatible euler: no 360 degree flips between frames
        cam.rotation_euler = e; prev = e.copy()
        cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
    for fc in cam.animation_data.action.fcurves if hasattr(cam.animation_data.action, 'fcurves') else []:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    return cam, key_frames


def write_frames_json(scene, cam, key_frames, hotspots, out_path, version):
    """Project each hotspot anchor into every frame: uv in 0..1 (top-left origin), None when off screen or hidden.
    hotspots: [{"id", "title", "text", "at": (x, y, z), "from": p0, "to": p1}], p = scroll progress 0..1."""
    n = scene.frame_end - scene.frame_start + 1
    out = []
    for h in hotspots:
        h = dict(h); at = Vector(h.pop('at')); uv = []
        for f in range(n):
            scene.frame_set(f)
            co = world_to_camera_view(scene, cam, at)
            ok = co.z > 0 and 0.03 < co.x < 0.97 and 0.04 < co.y < 0.96
            if ok:                                               # something in front of the anchor: hide the dot
                o = cam.matrix_world.translation; v = at - o
                hit, loc, *_ = scene.ray_cast(bpy.context.evaluated_depsgraph_get(), o, v.normalized(), distance=v.length)
                ok = not hit or (loc - at).length < 0.06
            uv.append([round(co.x, 4), round(1 - co.y, 4)] if ok else None)
        h['uv'] = uv
        h['at'] = [round(c, 4) for c in at]          # Blender coordinates, used by bake.py for the real-time page
        out.append(h)
    scene.frame_set(0)
    meta = {"count": n, "width": scene.render.resolution_x, "height": scene.render.resolution_y, "v": version,
            "keys": key_frames, "hotspots": out}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(meta, fh)
    return {h['id']: sum(u is not None for u in h['uv']) for h in out}
