"""Prepare the Vela reference views and optionally submit one Tripo H3.1 task."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import requests
from PIL import Image

API = "https://openapi.tripo3d.ai/v3"
MODEL = "v3.1-20260211"
TEXTURE_QUALITY = "extreme"
GEOMETRY_QUALITY = "detailed"
ESTIMATED_CREDITS = 70
VIEW_BOXES = {
    "front": (0.015, 0.66, 0.15, 0.998),
    "right": (0.14, 0.66, 0.265, 0.998),
    "left": (0.26, 0.66, 0.355, 0.998),
    "back": (0.35, 0.66, 0.47, 0.998),
}


def crop_views(reference: Path, work: Path) -> dict[str, Path]:
    source = Image.open(reference).convert("RGB")
    width, height = source.size
    work.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    for name, (x0, y0, x1, y1) in VIEW_BOXES.items():
        crop = source.crop((round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height)))
        corners = [crop.getpixel(point) for point in ((0, 0), (crop.width - 1, 0), (0, crop.height - 1), (crop.width - 1, crop.height - 1))]
        background = tuple(round(statistics.median(pixel[channel] for pixel in corners)) for channel in range(3))
        scale = 500 / crop.height
        crop = crop.resize((round(crop.width * scale), 500), Image.Resampling.LANCZOS)
        frame = Image.new("RGB", (512, 512), background)
        frame.paste(crop, ((512 - crop.width) // 2, 6))
        path = work / f"{name}.png"
        frame.save(path)
        result[name] = path
    return result


def api_headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def json_response(response: requests.Response) -> dict:
    response.raise_for_status()
    data = response.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Tripo API code {data.get('code')}: {data.get('message', 'unknown error')}")
    return data["data"]


def query_balance(session: requests.Session) -> tuple[float, float]:
    data = json_response(session.get(f"{API}/account/balance", timeout=30))
    return float(data["balance"]), float(data["frozen"])


def upload_view(session: requests.Session, path: Path) -> str:
    with path.open("rb") as stream:
        response = session.post(f"{API}/files", files={"file": (path.name, stream, "image/png")}, timeout=90)
    return str(json_response(response)["file_token"])


def poll_task(session: requests.Session, task_id: str, work: Path) -> dict:
    task_path = work / "task.json"
    deadline = time.monotonic() + 2400
    while time.monotonic() < deadline:
        data = json_response(session.get(f"{API}/tasks/{task_id}", timeout=45))
        task_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        status = data.get("status")
        print(f"TASK_STATUS={status} PROGRESS={data.get('progress', 'n/a')}", flush=True)
        if status == "success":
            return data
        if status in {"failed", "cancelled"}:
            raise RuntimeError(f"Tripo task ended with status {status}: {data.get('error', data.get('message', 'no details'))}")
        time.sleep(5)
    raise TimeoutError("Timed out polling Tripo task; task ID is preserved for inspection and will not be resubmitted.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, default=Path.home() / "tripo-work")
    parser.add_argument("--output", type=Path, default=Path("assets/tripo/vela-reference-original.glb"))
    parser.add_argument("--submit", action="store_true", help="Submit exactly one paid H3.1 multiview generation after checking balance.")
    args = parser.parse_args()

    key = os.environ.get("TRIPO_API_KEY", "")
    if not key.startswith("tsk_"):
        print("TRIPO_API_KEY is missing or is not a Tripo API key. Expected a key beginning tsk_.", file=sys.stderr)
        return 2

    views = crop_views(args.reference, args.work_dir / "views")
    print(f"REFERENCE_SIZE={Image.open(args.reference).size}; FOUR_ISOLATED_VIEWS=512x512")
    session = requests.Session()
    session.headers.update(api_headers(key))
    key = ""  # Do not retain or print the credential after configuring the session.
    try:
        balance, frozen = query_balance(session)
    except Exception as error:
        print(f"PREFLIGHT_FAILED={type(error).__name__}: {error}", file=sys.stderr)
        return 3
    print(f"MODEL={MODEL}; TEXTURE={TEXTURE_QUALITY}; GEOMETRY={GEOMETRY_QUALITY}")
    print(f"AVAILABLE_CREDITS={balance:.2f}; FROZEN_CREDITS={frozen:.2f}; ESTIMATED_TASK_CREDITS={ESTIMATED_CREDITS}; ESTIMATED_REMAINING={balance - ESTIMATED_CREDITS:.2f}")
    if not args.submit:
        print("PREFLIGHT_ONLY; no generation task submitted")
        return 0
    if balance - frozen < ESTIMATED_CREDITS:
        print("INSUFFICIENT_AVAILABLE_CREDITS; no task submitted", file=sys.stderr)
        return 4

    marker = args.work_dir / "generation-submission.json"
    if marker.exists():
        print(f"SUBMISSION_MARKER_EXISTS={marker}; refusing to risk a duplicate paid task", file=sys.stderr)
        return 5

    tokens = {view: upload_view(session, path) for view, path in views.items()}
    payload = {
        "inputs": [{view: tokens[view]} for view in ("front", "left", "back", "right")],
        "model": MODEL,
        "texture": True,
        "pbr": True,
        "texture_quality": TEXTURE_QUALITY,
        "geometry_quality": GEOMETRY_QUALITY,
        "face_limit": 500000,
    }
    marker.write_text(json.dumps({"state": "submission_started", "model": MODEL, "estimated_credits": ESTIMATED_CREDITS, "submitted_at": time.time()}, indent=2), encoding="utf-8")
    # This POST is intentionally made once. If its outcome is ambiguous, inspect account usage and task history before any retry.
    try:
        data = json_response(session.post(f"{API}/generation/multiview-to-model", json=payload, timeout=120))
    except Exception as error:
        marker.write_text(json.dumps({"state": "submission_outcome_uncertain_or_failed", "error_type": type(error).__name__, "error": str(error)}, indent=2), encoding="utf-8")
        print(f"SUBMISSION_ERROR={type(error).__name__}: {error}; do not resubmit until account usage is checked", file=sys.stderr)
        return 6

    task_id = str(data["task_id"])
    marker.write_text(json.dumps({"state": "task_created", "task_id": task_id, "model": MODEL, "estimated_credits": ESTIMATED_CREDITS}, indent=2), encoding="utf-8")
    print(f"TASK_ID={task_id}", flush=True)
    task = poll_task(session, task_id, args.work_dir)
    model_url = task.get("output", {}).get("model_url")
    if not model_url:
        raise RuntimeError("Successful task response did not include output.model_url")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    download = requests.get(model_url, timeout=180)
    download.raise_for_status()
    args.output.write_bytes(download.content)
    marker.write_text(json.dumps({"state": "model_downloaded", "task_id": task_id, "output": str(args.output.resolve()), "credits_consumed": task.get("credits_consumed")}, indent=2), encoding="utf-8")
    after, frozen_after = query_balance(session)
    print(f"MODEL_SAVED={args.output.resolve()}; FILE_BYTES={args.output.stat().st_size}")
    print(f"ACTUAL_CREDITS_CONSUMED={task.get('credits_consumed', 'reported by API after balance update')}; AVAILABLE_AFTER={after:.2f}; FROZEN_AFTER={frozen_after:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
