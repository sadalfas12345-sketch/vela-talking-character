"""Measure the corrected generalized CaptureForge response on both models."""
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\USER\talking-character-demo")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, r"C:\Users\USER\captureforge")

import captureforge_anatomical_rig as corrected
import measure_captureforge_control_response as measured
from captureforge.face import autofit

measured.OUT = ROOT / "verification/captureforge-facial-rig-test/rig-construction-correction"
autofit.face_geometry = corrected.face_geometry
autofit.bone_specs = corrected.bone_specs
autofit.skin_weights = corrected.skin_weights
autofit.build_faceforge_rig = corrected.build_faceforge_rig

for label, cfg in measured.CASES.items():
    measured.run(label, cfg)
