"""Render settings, applied on every launch (GPU choice is a user preference, not saved in the .blend).
Run: blender -b scene.blend -P blender/render_setup.py [-o //out/f###] (-f N | -a) [-- --exposure E] [--look | --preview] [--seed S]
  --look     50 % size, 128 samples (look-dev stills)
  --preview  25 % size, 16 samples (path check)
  --seed S   another noise seed, for the seed test (flicker ceiling)
Resolution comes from the .blend (set by build_scene.py, also written to web/frames.json): change it there, not here."""
import bpy, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cycles_gpu import use_gpu

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
use_gpu(scene)
c = scene.cycles
c.samples, c.use_adaptive_sampling, c.adaptive_threshold, c.adaptive_min_samples = 512, True, 0.01, 64
c.use_denoising, c.denoiser = True, 'OPENIMAGEDENOISE'
c.denoising_input_passes, c.denoising_prefilter = 'RGB_ALBEDO_NORMAL', 'ACCURATE'
for k, v in (('denoising_quality', 'HIGH'), ('denoising_use_gpu', True)):
    if hasattr(c, k):
        setattr(c, k, v)
c.seed, c.use_animated_seed = 0, False
c.max_bounces, c.diffuse_bounces, c.glossy_bounces = 12, 4, 4
c.transmission_bounces, c.transparent_max_bounces, c.volume_bounces = 12, 16, 0
c.caustics_reflective = c.caustics_refractive = False
c.blur_glossy, c.sample_clamp_indirect = 1.0, 8
c.film_exposure = 1.0
r = scene.render
r.resolution_percentage = 100
r.filter_size = 1.5
r.use_persistent_data = True
r.use_motion_blur = False
r.image_settings.file_format = 'PNG'
r.image_settings.color_depth = '8'
r.filepath = '//frames/f###'
r.use_overwrite = False
r.use_placeholder = True
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = float(ARGS[ARGS.index('--exposure') + 1]) if '--exposure' in ARGS else 0.0

if '--look' in ARGS:
    r.resolution_percentage, c.samples, c.adaptive_min_samples = 50, 128, 32
    r.use_overwrite = True; r.use_placeholder = False
if '--preview' in ARGS:
    r.resolution_percentage, c.samples, c.adaptive_min_samples = 25, 16, 8
    r.use_overwrite = True; r.use_placeholder = False
if '--seed' in ARGS:
    c.seed = int(ARGS[ARGS.index('--seed') + 1])
    r.use_overwrite = True; r.use_placeholder = False
print('RENDER setup', r.resolution_x * r.resolution_percentage // 100, 'x', r.resolution_y * r.resolution_percentage // 100,
      'samples', c.samples, 'exposure', scene.view_settings.exposure)
