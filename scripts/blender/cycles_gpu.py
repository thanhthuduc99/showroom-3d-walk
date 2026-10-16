import bpy


def use_gpu(scene):
    """Cycles device choice is a user preference, not stored in the .blend: set it on every headless run."""
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
        except Exception:
            continue
        if any(d.type == kind for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == kind
            scene.cycles.device = 'GPU'
            print('GPU', kind, [d.name for d in prefs.devices if d.use])
            return
    print('GPU none, falling back to CPU')
