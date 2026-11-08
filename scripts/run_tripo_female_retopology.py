"""Run the approved single female Tripo v3 retopology task.

The API key is read only from TRIPO_API_KEY and is never logged or written.
"""
import json
import os
import sys
import time
import urllib.request
import requests
from pathlib import Path

BASE = "https://openapi.tripo3d.ai/v3"
ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "assets/tripo/vela-photoreal/generated-original.glb"
OUT = ROOT / "verification/tripo-female-retopology-v3"

def api(method, path, payload=None):
    key = os.environ.get("TRIPO_API_KEY")
    if not key:
        raise SystemExit("TRIPO_API_KEY is not configured")
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read())

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    presign = api("POST", "/files/presign", {"format": "glb"})
    if presign.get("code") != 0:
        raise RuntimeError(presign)
    token = presign["data"]["file_token"]
    upload_url = presign["data"]["presigned_url"]
    with INPUT.open("rb") as stream:
        response = requests.put(upload_url, data=stream, headers={"Content-Type": "application/octet-stream"}, timeout=600)
        if response.status_code not in (200, 201, 204):
            raise RuntimeError(f"upload failed: {response.status_code}")
    print("uploaded input", INPUT.stat().st_size)
    task = api("POST", "/mesh/decimate", {
        "input": token,
        "model": "v3.0",
        "quad": True,
        "smart_uv": True,
        "bake": True,
        "face_limit": 10000,
    })
    if task.get("code") != 0:
        raise RuntimeError(task)
    task_id = task["data"]["task_id"]
    (OUT / "task-metadata.json").write_text(json.dumps({"task_id": task_id, "settings": {"model": "v3.0", "quad": True, "smart_uv": True, "bake": True, "face_limit": 10000}, "input": str(INPUT)}, indent=2) + "\n", encoding="utf-8")
    print("task submitted", task_id)
    while True:
        status = api("GET", f"/tasks/{task_id}")
        data = status.get("data", status)
        print("status", data.get("status"), "progress", data.get("progress"))
        if data.get("status") in ("success", "failed", "cancelled", "error"):
            if data.get("status") != "success":
                raise RuntimeError(status)
            model_url = data.get("output", {}).get("model_url")
            if not model_url:
                raise RuntimeError("successful task has no model_url")
            with urllib.request.urlopen(model_url, timeout=300) as response:
                (OUT / "female-retopology-v3.glb").write_bytes(response.read())
            (OUT / "task-result.json").write_text(json.dumps({"task_id": task_id, "status": data.get("status"), "progress": data.get("progress"), "output_keys": sorted(data.get("output", {}).keys())}, indent=2) + "\n", encoding="utf-8")
            print("downloaded", OUT / "female-retopology-v3.glb")
            return
        time.sleep(5)

if __name__ == "__main__":
    main()
