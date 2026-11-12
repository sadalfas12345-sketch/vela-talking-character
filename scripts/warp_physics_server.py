"""Local browser bridge for the validated VELA Warp RK4 backend.

The browser remains responsible for loading and rendering the original GLB.
This service owns one selected original mesh island on the RTX device and
streams evaluated positions back at frame boundaries. No vertex array is
copied between host and device per RK4 substep.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import numpy as np
import websockets

from rk4_warp_gpu import WarpSimulation, load_array, load_fixture


class Session:
    def __init__(self, manifest_path: Path, model: str, domain: str, device: str, kp: float, kd: float):
        manifest = json.loads(manifest_path.read_text())
        records = manifest["models"][model]
        requested_domain = domain
        if domain not in records and domain.startswith("island-"):
            try:
                requested_source_island = int(domain.split("-", 1)[1])
            except ValueError:
                requested_source_island = None
            full_record = records.get("full")
            if full_record and full_record.get("sourceIslandId") == requested_source_island:
                domain = "full"
        if domain not in records:
            available = ", ".join(sorted(records))
            raise ValueError(f"GPU fixture domain {requested_domain!r} is unavailable for {model}; available: {available}")
        record = records[domain]
        if "globalVertexIds" not in record["files"]:
            raise RuntimeError("GPU fixture is missing globalVertexIds; rerun --export-gpu-fixtures")
        self.fixture = load_fixture(manifest_path, model, domain)
        self.device = device
        self.model = model
        self.domain = domain
        self.kp = float(kp)
        self.kd = float(kd)
        self.sim = WarpSimulation(self.fixture, device)
        self.sim.reset()
        self.global_ids = load_array(manifest_path.parent / record["files"]["globalVertexIds"], np.uint32)
        if len(self.global_ids) != self.fixture["vertex_count"]:
            raise RuntimeError("globalVertexIds length does not match fixture vertex count")
        self.global_to_local = {int(value): index for index, value in enumerate(self.global_ids)}
        self.pinch = None
        self.gravity = np.zeros(3, dtype=np.float64)

    def axes(self):
        values = self.fixture["anatomical_axes"]
        return {
            "up": np.asarray(values["up"], dtype=np.float64),
            "right": np.asarray(values["right"], dtype=np.float64),
            "front": np.asarray(values["front"], dtype=np.float64),
        }

    def set_pinch(self, message):
        if message is None:
            self.pinch = None
            return
        global_ids = [int(value) for value in message["ids"]]
        try:
            local_ids = np.asarray([self.global_to_local[value] for value in global_ids], dtype=np.int32)
        except KeyError as error:
            raise ValueError(f"pinch vertex {error.args[0]} is not in the selected original island") from error
        weights = np.asarray(message["weights"], dtype=np.float32)
        if len(local_ids) != 3 or len(weights) != 3 or abs(float(np.sum(weights)) - 1.0) > 1.0e-4:
            raise ValueError("pinch requires three barycentric IDs and weights summing to one")
        target = np.asarray(message["target"], dtype=np.float32)
        velocity = np.asarray(message.get("velocity", [0.0, 0.0, 0.0]), dtype=np.float32)
        if target.shape != (3,) or velocity.shape != (3,):
            raise ValueError("pinch target and velocity must be 3-vectors")
        self.pinch = (local_ids, weights, target, velocity, self.kp, self.kd)

    def state_packet(self, runtime_ms, steps, seconds):
        positions = self.sim.positions.numpy().reshape(-1, 3).astype(np.float32, copy=False)
        return {
            "type": "state",
            "model": self.model,
            "domain": self.domain,
            "runtimeMs": runtime_ms,
            "steps": steps,
            "seconds": seconds,
            "vertexCount": self.fixture["vertex_count"],
            "sourceMetersPerUnit": self.fixture["meters"],
            "positionsBytes": int(positions.nbytes),
        }, positions.tobytes(order="C")


async def handler(websocket, manifest_path: Path, device: str, default_kp: float, default_kd: float):
    session = None
    async for raw in websocket:
        try:
            message = json.loads(raw)
            message_type = message.get("type")
            if message_type == "init":
                session = Session(
                    manifest_path,
                    str(message.get("model", "female")),
                    str(message.get("domain", "full")),
                    device,
                    float(message.get("kp", default_kp)),
                    float(message.get("kd", default_kd)),
                )
                await websocket.send(json.dumps({
                    "type": "ready",
                    "model": session.model,
                    "domain": session.domain,
                    "vertexCount": session.fixture["vertex_count"],
                    "globalVertexIds": session.global_ids.tolist(),
                    "stableDt": session.fixture["stable_dt"],
                    "anatomicalAxes": session.fixture["anatomical_axes"],
                }))
                continue
            if session is None:
                raise ValueError("send init before control messages")
            if message_type == "gravity":
                session.gravity = np.asarray(message.get("value", [0.0, 0.0, 0.0]), dtype=np.float64)
                await websocket.send(json.dumps({"type": "ack", "command": "gravity"}))
            elif message_type == "pinch":
                session.set_pinch(message)
                await websocket.send(json.dumps({"type": "ack", "command": "pinch"}))
            elif message_type == "release":
                session.set_pinch(None)
                await websocket.send(json.dumps({"type": "ack", "command": "release"}))
            elif message_type == "reset":
                session.sim.reset()
                session.set_pinch(None)
                await websocket.send(json.dumps({"type": "ack", "command": "reset"}))
            elif message_type == "tick":
                seconds = float(message.get("seconds", 0.0))
                if not np.isfinite(seconds) or seconds < 0.0:
                    raise ValueError("tick seconds must be finite and nonnegative")
                _, _, _, runtime_ms, steps = session.sim.advance(seconds, session.gravity, session.pinch)
                header, payload = session.state_packet(runtime_ms, steps, seconds)
                await websocket.send(json.dumps(header))
                await websocket.send(payload)
            elif message_type == "ping":
                await websocket.send(json.dumps({"type": "pong"}))
            else:
                raise ValueError(f"unknown command {message_type!r}")
        except Exception as error:
            await websocket.send(json.dumps({"type": "error", "message": str(error)}))


async def main_async(args):
    manifest_path = Path(args.manifest).resolve()
    async with websockets.serve(
        lambda websocket: handler(websocket, manifest_path, args.device, args.kp, args.kd),
        args.host,
        args.port,
        max_size=8 * 1024 * 1024,
    ):
        print(json.dumps({"phase": "warp-server-ready", "host": args.host, "port": args.port, "device": args.device}), flush=True)
        await asyncio.Future()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="verification/island-spring-pinch/gpu-fixtures/manifest.json")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--kp", type=float, default=0.1)
    parser.add_argument("--kd", type=float, default=0.01)
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
