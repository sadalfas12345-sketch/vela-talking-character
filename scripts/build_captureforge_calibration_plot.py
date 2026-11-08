"""Build compact plots from the CaptureForge response-map calibration outputs."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"C:\Users\USER\talking-character-demo")
CAL = ROOT / "verification/captureforge-facial-rig-test/control-calibration"
REGIONS = ("eyebrows", "eyelids", "cheeks", "lips", "mouth_corners", "jaw")


def main():
    reports = {}
    for label in ("female", "male"):
        reports[label] = {
            "fit": json.loads((CAL / label / "validation/validation-report.json").read_text()),
            "definition": json.loads((CAL / label / "control-definition.json").read_text()),
        }

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), dpi=160)
    x = np.arange(len(REGIONS))
    width = 0.18
    colors = {"female": "#b45f06", "male": "#1155cc"}
    for offset, label in enumerate(("female", "male")):
        data = reports[label]["fit"]["region_metrics"]
        expected = [data[r]["mean_expected_magnitude_norm"] for r in REGIONS]
        actual = [data[r]["mean_actual_magnitude_norm"] for r in REGIONS]
        axes[0].bar(x + (offset - 0.5) * width, expected, width, color="#cccccc", label=f"{label} reference" if offset == 0 else None)
        axes[0].bar(x + (offset + 0.5) * width, actual, width, color=colors[label], label=f"{label} actual")
    axes[0].set_xticks(x, [r.replace("_", "\n") for r in REGIONS])
    axes[0].set_ylabel("Mean displacement / interocular width")
    axes[0].set_title("Reference motion versus evaluated rig motion")
    axes[0].legend(fontsize=8)
    axes[0].grid(axis="y", alpha=0.25)

    names = []
    female_vals = []
    male_vals = []
    for label, vals in (("female", female_vals), ("male", male_vals)):
        definition = reports[label]["definition"]
        groups = {}
        for d in definition["dofs"]:
            groups.setdefault(d["bone"], []).append(d["name"])
        rows = json.loads((CAL / label / "control-tests.json").read_text())
        by_dof = {}
        for row in rows:
            by_dof.setdefault(row["dof"], []).append(float(row["max_landmark_motion"]))
        if label == "female":
            names = list(groups)
        vals.extend([max(float(v) for n in groups[b] for v in by_dof[n]) for b in groups])
    bx = np.arange(len(names))
    axes[1].bar(bx - 0.2, female_vals, 0.4, label="female", color=colors["female"])
    axes[1].bar(bx + 0.2, male_vals, 0.4, label="male", color=colors["male"])
    axes[1].set_xticks(bx, names, rotation=65, ha="right", fontsize=7)
    axes[1].set_ylabel("Largest landmark response in test units")
    axes[1].set_title("Maximum response by facial bone")
    axes[1].legend(fontsize=8)
    axes[1].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    out = CAL / "control-response-summary.png"
    fig.savefig(out, bbox_inches="tight")
    print(out)


if __name__ == "__main__":
    main()
