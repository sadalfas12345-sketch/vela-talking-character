"""Run the existing Plan A5 spring solver on selected reference frames.

This is an orchestration and provenance wrapper. It does not alter the source
GLBs, targets, graph connectivity, attachment triangles, or solver code.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "scripts" / "solve_plan_a5_subcutaneous.py"
DATA = ROOT / "verification" / "plan-a5-subcutaneous-run"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="female,male")
    parser.add_argument("--frames", default="0,45,97,99")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "verification" / "reference-expression-replay")
    parser.add_argument("--support-ratio", type=float, default=0.1)
    parser.add_argument("--max-iterations", type=int, default=20)
    parser.add_argument("--inner-iterations", type=int, default=60)
    parser.add_argument("--max-backtracks", type=int, default=20)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    frames = [int(item.strip()) for item in args.frames.split(",") if item.strip()]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "models": models,
        "frames": frames,
        "outputDir": str(args.output_dir),
        "supportRatio": args.support_ratio,
        "maxIterations": args.max_iterations,
        "innerIterations": args.inner_iterations,
        "maxBacktracks": args.max_backtracks,
        "resume": args.resume,
    }
    records = []
    for model in models:
        graph = DATA / f"{model}-subcutaneous-r050.npz"
        targets = DATA / f"{model}-targets-r050.npz"
        for frame in frames:
            output = args.output_dir / f"{model}-frame{frame:03d}.json"
            if args.resume and output.exists():
                records.append({"model": model, "frame": frame, "status": "already-present", "output": str(output)})
                continue
            command = [
                sys.executable, str(RUN), "--graph", str(graph), "--targets", str(targets),
                "--output", str(output), "--frame", str(frame), "--support-ratio", str(args.support_ratio),
                "--max-iterations", str(args.max_iterations), "--inner-iterations", str(args.inner_iterations),
                "--max-backtracks", str(args.max_backtracks),
            ]
            started = time.perf_counter()
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            record = {
                "model": model,
                "frame": frame,
                "timeSeconds": frame / 24.0,
                "command": [str(value) for value in command],
                "returnCode": int(completed.returncode),
                "runtimeSeconds": time.perf_counter() - started,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
                "status": "completed" if completed.returncode == 0 else "failed",
                "output": str(output),
                "positions": str(output.with_name(output.stem + "-positions.npz")),
            }
            if output.exists():
                try:
                    report = json.loads(output.read_text(encoding="utf-8"))
                    record["solverStatus"] = "failed" if report.get("failure") else "converged"
                    record["failure"] = report.get("failure")
                    record["landmarks"] = report.get("landmarks")
                    record["components"] = report.get("components")
                except json.JSONDecodeError:
                    record["solverStatus"] = "invalid-report"
            records.append(record)
            manifest = {"schema": "vela-reference-expression-replay-v1", "settings": settings, "records": records}
            (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(record), flush=True)
    manifest = {"schema": "vela-reference-expression-replay-v1", "settings": settings, "records": records}
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if any(record.get("status") == "failed" for record in records):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
