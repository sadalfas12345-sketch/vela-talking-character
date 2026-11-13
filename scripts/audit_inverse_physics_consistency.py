"""Compare the inverse-expression energy with the calibrated GPU RK4 model."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph-json", type=Path, required=True)
    p.add_argument("--rk4-report", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    graph = json.loads(args.graph_json.read_text(encoding="utf-8"))
    rk4 = json.loads(args.rk4_report.read_text(encoding="utf-8"))
    result = {
        "schema": "vela-inverse-physics-consistency-audit-v1",
        "inverseModel": {
            "coordinateUnits": "source mesh units",
            "surfaceSpringCoefficient": "1.0 implicit energy coefficient",
            "surfaceSpringCount": graph["originalEdgeSprings"],
            "virtualSpringCount": graph["virtualSeamSprings"],
            "virtualZeroRestSprings": graph.get("virtualSpringZeroRestCount"),
            "supportSpringCount": "from subcutaneous graph; abstract anchor springs",
            "mass": "not used in static inverse equilibrium",
            "damping": "not used in static inverse equilibrium",
            "gravity": "not used in frame-45 expression probe",
            "timeIntegration": "none; nonlinear static force-balance relaxation",
        },
        "gpuRk4Model": {
            "sourceMetersPerUnit": rk4["architecture"]["sourceMetersPerUnit"],
            "surfaceModulusBaselinePa": rk4["massPolicy"]["surfaceModulusBaselinePa"],
            "innerModulusBaselinePa": rk4["massPolicy"]["innerModulusBaselinePa"],
            "massDistribution": "triangle-area-derived SI masses",
            "damping": "physical velocity damping",
            "gravity": "present in calibrated tests",
            "integrator": rk4["architecture"]["integrator"],
            "crossIslandSprings": rk4["architecture"]["crossIslandSprings"],
            "fixedInnerAnchors": rk4["architecture"]["fixedInnerAnchors"],
        },
        "differences": [
            {"item": "spring coefficient", "inverse": "unit coefficient", "rk4": "30 kPa baseline converted through source scale and area model", "intentional": False, "action": "must be reconciled before claiming RK4-equivalent forces"},
            {"item": "units", "inverse": "source units", "rk4": "SI force and acceleration with sourceMetersPerUnit=0.30", "intentional": False, "action": "inverse force coefficients are not yet SI-calibrated"},
            {"item": "mass and damping", "inverse": "absent from static equilibrium", "rk4": "area-derived mass and damping", "intentional": True, "action": "valid only for a static force-control probe, not dynamic equivalence"},
            {"item": "virtual seams", "inverse": f"{graph['virtualSeamSprings']} virtual seam springs retained", "rk4": "zero cross-island springs in calibrated architecture", "intentional": False, "action": "do not compare force magnitudes until domain and seam policy are aligned"},
            {"item": "support springs", "inverse": "abstract support graph from Plan A5", "rk4": "fixed inner-anchor support with calibrated physical stiffness", "intentional": False, "action": "map support stiffness and rest lengths before next optimizer run"},
        ],
        "conclusion": "The initial inverse result is a valid diagnostic of the current static A5 graph, but it is not numerically comparable to the calibrated GPU RK4 force system until units, spring coefficients, support springs, and virtual-seam policy are aligned.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "differences": len(result["differences"])}))


if __name__ == "__main__":
    main()
