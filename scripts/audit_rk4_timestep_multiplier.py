"""Compare larger RK4 timesteps against the validated full-island baseline.

This is an audit only. It reuses the existing Warp RK4 implementation and
compares the final resident GPU state for one deterministic held-pinch/release
trajectory at several timestep multipliers.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

from rk4_warp_gpu import (
    WarpSimulation,
    geometry_metrics,
    js_rng,
    load_fixture,
    random_pinch,
)


def run_case(fixture: dict, factor: float, pinch: dict, device: str, hold_seconds: float, release_seconds: float):
    case_fixture = dict(fixture)
    case_fixture["stable_dt"] = float(fixture["stable_dt"]) * factor
    simulator = WarpSimulation(case_fixture, device)
    gravity = pinch["direction"] * 9.81
    held = None
    total_steps = 0
    started = time.perf_counter()
    for phase in range(1, 5):
        target = pinch["origin"] + (pinch["target"].astype(np.float64) - pinch["origin"]) * (phase / 4.0)
        segment = (pinch["ids"], pinch["weights"], target.astype(np.float32), pinch["velocity"], pinch["kp"], pinch["kd"])
        positions, velocities, _, _, steps = simulator.advance(hold_seconds, gravity, segment, graph_chunk=16)
        held = (positions, velocities)
        total_steps += steps
    released_positions, released_velocities, _, _, steps = simulator.advance(release_seconds, gravity, None, graph_chunk=16)
    total_steps += steps
    return {
        "factor": factor,
        "stableDt": case_fixture["stable_dt"],
        "steps": total_steps,
        "runtimeMs": (time.perf_counter() - started) * 1000.0,
        "heldGeometry": geometry_metrics(case_fixture, held[0]),
        "releasedGeometry": geometry_metrics(case_fixture, released_positions),
        "heldPositions": held[0],
        "heldVelocities": held[1],
        "releasedPositions": released_positions,
        "releasedVelocities": released_velocities,
    }


def compact(case: dict, reference: dict, fixture: dict) -> dict:
    released_delta = case["releasedPositions"] - reference["releasedPositions"]
    velocity_delta = case["releasedVelocities"] - reference["releasedVelocities"]
    return {
        "factor": case["factor"],
        "stableDt": case["stableDt"],
        "steps": case["steps"],
        "runtimeMs": case["runtimeMs"],
        "heldGeometry": case["heldGeometry"],
        "releasedGeometry": case["releasedGeometry"],
        "releasedPositionMaxDeltaSource": float(np.max(np.linalg.norm(released_delta, axis=1), initial=0.0)),
        "releasedPositionRmsDeltaSource": float(np.sqrt(np.mean(np.sum(released_delta * released_delta, axis=1)))),
        "releasedPositionMaxDeltaNormalizedFace": float(np.max(np.linalg.norm(released_delta, axis=1), initial=0.0) / max(fixture["face_scale"], 1.0e-12)),
        "releasedVelocityMaxDeltaSourcePerSecond": float(np.max(np.linalg.norm(velocity_delta, axis=1), initial=0.0)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="verification/island-spring-pinch/gpu-fixtures/manifest.json")
    parser.add_argument("--model", choices=["female", "male"], required=True)
    parser.add_argument("--domain", default="full")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=20261113)
    parser.add_argument("--hold-seconds", type=float, default=1.0 / 60.0)
    parser.add_argument("--release-seconds", type=float, default=0.02)
    parser.add_argument("--pinch-kp", type=float, default=0.1)
    parser.add_argument("--pinch-kd", type=float, default=0.01)
    parser.add_argument("--factors", default="1,12,24")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    fixture = load_fixture(manifest_path, args.model, args.domain)
    factors = [float(value) for value in args.factors.split(",") if value.strip()]
    if not factors or any(value <= 0.0 for value in factors):
        raise ValueError("--factors must contain positive values")
    pinch = random_pinch(fixture, js_rng(args.seed + 100), args.pinch_kp, args.pinch_kd)
    cases = [run_case(fixture, factor, pinch, args.device, args.hold_seconds, args.release_seconds) for factor in factors]
    reference = cases[0]
    report = {
        "schema": "vela-rk4-timestep-multiplier-audit-v1",
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": args.model,
        "domain": args.domain,
        "vertices": fixture["vertex_count"],
        "seed": args.seed,
        "holdSeconds": args.hold_seconds,
        "releaseSeconds": args.release_seconds,
        "pinchKp": args.pinch_kp,
        "pinchKd": args.pinch_kd,
        "pinchFace": pinch["ids"].astype(int).tolist(),
        "pinchDirection": pinch["directionName"],
        "pinchMagnitudeSource": pinch["magnitude"],
        "baselineFactor": reference["factor"],
        "cases": [compact(case, reference, fixture) for case in cases],
        "allFinite": all(np.isfinite(case["releasedPositions"]).all() and np.isfinite(case["releasedVelocities"]).all() for case in cases),
        "zeroFlipsAndCollapses": all(
            case["heldGeometry"]["orientationFlips"] == 0
            and case["releasedGeometry"]["orientationFlips"] == 0
            and case["heldGeometry"]["collapsedTriangles"] == 0
            and case["releasedGeometry"]["collapsedTriangles"] == 0
            for case in cases
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps({"output": str(output), "model": args.model, "factors": factors}, indent=2))


if __name__ == "__main__":
    main()
