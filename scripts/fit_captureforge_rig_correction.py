"""Fit the existing 121-frame motion to corrected response maps."""
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\USER\talking-character-demo")
sys.path.insert(0, str(ROOT / "scripts"))
import fit_captureforge_control_map as fit

fit.OUT = ROOT / "verification/captureforge-facial-rig-test/rig-construction-correction"
for label in ("female", "male"):
    fit.fit_one(label)
