import asyncio
import json
from pathlib import Path

import numpy as np
import websockets
from rk4_warp_gpu import cpu_simulate, load_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'verification' / 'island-spring-pinch' / 'gpu-fixtures'


async def main():
    manifest = json.loads((FIXTURES / 'manifest.json').read_text())
    record = manifest['models']['male']['full']
    neutral = np.fromfile(FIXTURES / record['files']['neutral'], dtype=np.float32).reshape(-1, 3)
    faces = np.fromfile(FIXTURES / record['files']['faces'], dtype=np.uint32).reshape(-1, 3)
    global_ids = np.fromfile(FIXTURES / record['files']['globalVertexIds'], dtype=np.uint32)
    triangle = faces[0]
    ids = [int(global_ids[index]) for index in triangle]
    point = (neutral[triangle[0]] + neutral[triangle[1]] + neutral[triangle[2]]) / 3.0
    target = point + np.array([0.002, 0.0, 0.0], dtype=np.float32)
    fixture = load_fixture(FIXTURES / 'manifest.json', 'male', 'full')
    cpu_positions, _, _, cpu_runtime = cpu_simulate(
        fixture, 0.001, np.zeros(3),
        (triangle.astype(np.int32), np.full(3, 1 / 3, dtype=np.float32), target, np.zeros(3, dtype=np.float32), 90.0, 0.08),
    )
    async with websockets.connect('ws://127.0.0.1:8765', max_size=8 * 1024 * 1024) as socket:
        await socket.send(json.dumps({'type': 'init', 'model': 'male', 'domain': 'island-35', 'kp': 90, 'kd': 0.08}))
        ready = json.loads(await socket.recv())
        await socket.send(json.dumps({'type': 'tick', 'seconds': 0.0, 'gravity': [0, 0, 0]}))
        header = json.loads(await socket.recv())
        before = np.frombuffer(await socket.recv(), dtype=np.float32).reshape(-1, 3).copy()
        await socket.send(json.dumps({'type': 'pinch', 'ids': ids, 'weights': [1 / 3, 1 / 3, 1 / 3], 'target': target.tolist(), 'velocity': [0, 0, 0]}))
        await socket.recv()
        await socket.send(json.dumps({'type': 'tick', 'seconds': 0.001, 'gravity': [0, 0, 0]}))
        held_header = json.loads(await socket.recv())
        held = np.frombuffer(await socket.recv(), dtype=np.float32).reshape(-1, 3).copy()
        await socket.send(json.dumps({'type': 'release'}))
        await socket.recv()
        await socket.send(json.dumps({'type': 'tick', 'seconds': 0.001, 'gravity': [0, 0, 0]}))
        released_header = json.loads(await socket.recv())
        released = np.frombuffer(await socket.recv(), dtype=np.float32).reshape(-1, 3).copy()
    report = {
        'ready': {key: ready[key] for key in ('model', 'domain', 'vertexCount')},
        'triangleGlobalIds': ids,
        'held': {'runtimeMs': held_header['runtimeMs'], 'steps': held_header['steps'], 'maxDisplacementSource': float(np.linalg.norm(held - before, axis=1).max())},
        'released': {'runtimeMs': released_header['runtimeMs'], 'steps': released_header['steps'], 'maxDisplacementSource': float(np.linalg.norm(released - held, axis=1).max())},
        'cpuReference': {'runtimeMs': cpu_runtime, 'maxDisplacementSource': float(np.linalg.norm(cpu_positions - before, axis=1).max()), 'finite': bool(np.isfinite(cpu_positions).all())},
    }
    (ROOT / 'verification' / 'island-spring-pinch' / 'gpu-browser-male-full-bridge-pinch.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


asyncio.run(main())
