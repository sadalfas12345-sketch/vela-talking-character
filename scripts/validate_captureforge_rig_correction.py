"""Replay and render the corrected generalized CaptureForge fit."""
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\USER\talking-character-demo")
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, r"C:\Users\USER\captureforge")

import captureforge_anatomical_rig as corrected
import validate_captureforge_control_fit as validation
from captureforge.face import autofit

validation.CAL = ROOT / "verification/captureforge-facial-rig-test/rig-construction-correction"
autofit.face_geometry = corrected.face_geometry
autofit.bone_specs = corrected.bone_specs
autofit.skin_weights = corrected.skin_weights
autofit.build_faceforge_rig = corrected.build_faceforge_rig

cases = {
    "female": {"glb": ROOT / "assets/tripo/vela-photoreal/generated-original.glb", "goal1": ROOT / "verification/goal1-generalization-run/cross-character-accuracy/female/refined/raycast-report.json"},
    "male": {"glb": ROOT / "assets/tripo/generalization-male-20261105/generated-original.glb", "goal1": ROOT / "verification/goal1-generalization-run/cross-character-accuracy/male/refined/raycast-report.json"},
}
for label, cfg in cases.items():
    validation.run(label, cfg)
