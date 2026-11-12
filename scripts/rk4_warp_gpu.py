"""GPU-resident RK4 benchmark for the existing VELA Hookean spring model.

The fixture manifest is exported by calibrate_realtime_rk4.mjs.  This script
does not rebuild the facial domain or change the physical equations: it runs
the same edge springs, inner-anchor springs, damping, gravity, and barycentric
pinch controller using Warp kernels on CUDA.  The NumPy implementation is the
Float64 comparison reference.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import warp as wp


wp.init()


@wp.kernel
def acceleration_kernel(
    positions: wp.array(dtype=wp.float32),
    velocities: wp.array(dtype=wp.float32),
    accelerations: wp.array(dtype=wp.float32),
    forces: wp.array(dtype=wp.float32),
    masses: wp.array(dtype=wp.float32),
    anchors: wp.array(dtype=wp.float32),
    surface_offsets: wp.array(dtype=wp.int32),
    surface_neighbors: wp.array(dtype=wp.int32),
    surface_rest: wp.array(dtype=wp.float32),
    support_offsets: wp.array(dtype=wp.int32),
    support_neighbors: wp.array(dtype=wp.int32),
    support_rest: wp.array(dtype=wp.float32),
    support_k: wp.array(dtype=wp.float32),
    pinch_ids: wp.array(dtype=wp.int32),
    pinch_weights: wp.array(dtype=wp.float32),
    pinch_target: wp.array(dtype=wp.float32),
    pinch_velocity: wp.array(dtype=wp.float32),
    gravity_x: wp.float32,
    gravity_y: wp.float32,
    gravity_z: wp.float32,
    source_meters_per_unit: wp.float32,
    surface_k: wp.float32,
    damping: wp.float32,
    pinch_kp: wp.float32,
    pinch_kd: wp.float32,
    use_pinch: wp.int32,
):
    i = wp.tid()
    i3 = i * 3
    xi = positions[i3]
    yi = positions[i3 + 1]
    zi = positions[i3 + 2]
    f_x = wp.float32(0.0)
    f_y = wp.float32(0.0)
    f_z = wp.float32(0.0)

    for p in range(surface_offsets[i], surface_offsets[i + 1]):
        j = surface_neighbors[p]
        j3 = j * 3
        dx = positions[j3] - xi
        dy = positions[j3 + 1] - yi
        dz = positions[j3 + 2] - zi
        length = wp.sqrt(dx * dx + dy * dy + dz * dz)
        if length > wp.float32(1.0e-12):
            q = surface_k * ((length - surface_rest[p]) * source_meters_per_unit) / length
            f_x += q * dx
            f_y += q * dy
            f_z += q * dz

    for p in range(support_offsets[i], support_offsets[i + 1]):
        anchor_index = support_neighbors[p] * 3
        dx = anchors[anchor_index] - xi
        dy = anchors[anchor_index + 1] - yi
        dz = anchors[anchor_index + 2] - zi
        length = wp.sqrt(dx * dx + dy * dy + dz * dz)
        if length > wp.float32(1.0e-12):
            q = support_k[p] * ((length - support_rest[p]) * source_meters_per_unit) / length
            f_x += q * dx
            f_y += q * dy
            f_z += q * dz

    if use_pinch != 0:
        id0 = pinch_ids[0]
        id1 = pinch_ids[1]
        id2 = pinch_ids[2]
        id03 = id0 * 3
        id13 = id1 * 3
        id23 = id2 * 3
        q_x = pinch_weights[0] * positions[id03] + pinch_weights[1] * positions[id13] + pinch_weights[2] * positions[id23]
        q_y = pinch_weights[0] * positions[id03 + 1] + pinch_weights[1] * positions[id13 + 1] + pinch_weights[2] * positions[id23 + 1]
        q_z = pinch_weights[0] * positions[id03 + 2] + pinch_weights[1] * positions[id13 + 2] + pinch_weights[2] * positions[id23 + 2]
        q_vx = pinch_weights[0] * velocities[id03] + pinch_weights[1] * velocities[id13] + pinch_weights[2] * velocities[id23]
        q_vy = pinch_weights[0] * velocities[id03 + 1] + pinch_weights[1] * velocities[id13 + 1] + pinch_weights[2] * velocities[id23 + 1]
        q_vz = pinch_weights[0] * velocities[id03 + 2] + pinch_weights[1] * velocities[id13 + 2] + pinch_weights[2] * velocities[id23 + 2]
        p_x = pinch_kp * ((pinch_target[0] - q_x) * source_meters_per_unit) + pinch_kd * ((pinch_velocity[0] - q_vx) * source_meters_per_unit)
        p_y = pinch_kp * ((pinch_target[1] - q_y) * source_meters_per_unit) + pinch_kd * ((pinch_velocity[1] - q_vy) * source_meters_per_unit)
        p_z = pinch_kp * ((pinch_target[2] - q_z) * source_meters_per_unit) + pinch_kd * ((pinch_velocity[2] - q_vz) * source_meters_per_unit)
        if i == id0:
            f_x += pinch_weights[0] * p_x
            f_y += pinch_weights[0] * p_y
            f_z += pinch_weights[0] * p_z
        if i == id1:
            f_x += pinch_weights[1] * p_x
            f_y += pinch_weights[1] * p_y
            f_z += pinch_weights[1] * p_z
        if i == id2:
            f_x += pinch_weights[2] * p_x
            f_y += pinch_weights[2] * p_y
            f_z += pinch_weights[2] * p_z

    f_x += masses[i] * gravity_x - damping * velocities[i3] * source_meters_per_unit
    f_y += masses[i] * gravity_y - damping * velocities[i3 + 1] * source_meters_per_unit
    f_z += masses[i] * gravity_z - damping * velocities[i3 + 2] * source_meters_per_unit
    forces[i3] = f_x
    forces[i3 + 1] = f_y
    forces[i3 + 2] = f_z
    inv_mass_scale = wp.float32(1.0) / (masses[i] * source_meters_per_unit)
    accelerations[i3] = f_x * inv_mass_scale
    accelerations[i3 + 1] = f_y * inv_mass_scale
    accelerations[i3 + 2] = f_z * inv_mass_scale


@wp.kernel
def rk4_stage_kernel(
    positions: wp.array(dtype=wp.float32),
    velocities: wp.array(dtype=wp.float32),
    acceleration: wp.array(dtype=wp.float32),
    out_positions: wp.array(dtype=wp.float32),
    out_velocities: wp.array(dtype=wp.float32),
    factor: wp.float32,
):
    i = wp.tid()
    j = i * 3
    out_positions[j] = positions[j] + velocities[j] * factor
    out_positions[j + 1] = positions[j + 1] + velocities[j + 1] * factor
    out_positions[j + 2] = positions[j + 2] + velocities[j + 2] * factor
    out_velocities[j] = velocities[j] + acceleration[j] * factor
    out_velocities[j + 1] = velocities[j + 1] + acceleration[j + 1] * factor
    out_velocities[j + 2] = velocities[j + 2] + acceleration[j + 2] * factor


@wp.kernel
def rk4_combine_kernel(
    positions: wp.array(dtype=wp.float32),
    velocities: wp.array(dtype=wp.float32),
    a1: wp.array(dtype=wp.float32),
    a2: wp.array(dtype=wp.float32),
    a3: wp.array(dtype=wp.float32),
    a4: wp.array(dtype=wp.float32),
    out_positions: wp.array(dtype=wp.float32),
    out_velocities: wp.array(dtype=wp.float32),
    h: wp.float32,
):
    i = wp.tid()
    j = i * 3
    out_positions[j] = positions[j] + h * (velocities[j] + wp.float32(2.0) * (velocities[j] + a1[j] * h * wp.float32(0.5)) + wp.float32(2.0) * (velocities[j] + a2[j] * h * wp.float32(0.5)) + (velocities[j] + a3[j] * h)) / wp.float32(6.0)
    out_positions[j + 1] = positions[j + 1] + h * (velocities[j + 1] + wp.float32(2.0) * (velocities[j + 1] + a1[j + 1] * h * wp.float32(0.5)) + wp.float32(2.0) * (velocities[j + 1] + a2[j + 1] * h * wp.float32(0.5)) + (velocities[j + 1] + a3[j + 1] * h)) / wp.float32(6.0)
    out_positions[j + 2] = positions[j + 2] + h * (velocities[j + 2] + wp.float32(2.0) * (velocities[j + 2] + a1[j + 2] * h * wp.float32(0.5)) + wp.float32(2.0) * (velocities[j + 2] + a2[j + 2] * h * wp.float32(0.5)) + (velocities[j + 2] + a3[j + 2] * h)) / wp.float32(6.0)
    out_velocities[j] = velocities[j] + h * (a1[j] + wp.float32(2.0) * a2[j] + wp.float32(2.0) * a3[j] + a4[j]) / wp.float32(6.0)
    out_velocities[j + 1] = velocities[j + 1] + h * (a1[j + 1] + wp.float32(2.0) * a2[j + 1] + wp.float32(2.0) * a3[j + 1] + a4[j + 1]) / wp.float32(6.0)
    out_velocities[j + 2] = velocities[j + 2] + h * (a1[j + 2] + wp.float32(2.0) * a2[j + 2] + wp.float32(2.0) * a3[j + 2] + a4[j + 2]) / wp.float32(6.0)


def load_array(path: Path, dtype: np.dtype) -> np.ndarray:
    return np.fromfile(path, dtype=dtype)


def load_fixture(manifest_path: Path, model: str, domain: str) -> dict:
    manifest = json.loads(manifest_path.read_text())
    record = manifest["models"][model][domain]
    directory = manifest_path.parent
    arrays = {
        "neutral": load_array(directory / record["files"]["neutral"], np.float64),
        "anchors": load_array(directory / record["files"]["anchors"], np.float64),
        "masses": load_array(directory / record["files"]["masses"], np.float64),
        "edge_a": load_array(directory / record["files"]["edgeA"], np.uint32),
        "edge_b": load_array(directory / record["files"]["edgeB"], np.uint32),
        "edge_rest": load_array(directory / record["files"]["edgeRest"], np.float64),
        "support_a": load_array(directory / record["files"]["supportA"], np.uint32),
        "support_b": load_array(directory / record["files"]["supportB"], np.uint32),
        "support_rest": load_array(directory / record["files"]["supportRest"], np.float64),
        "support_k": load_array(directory / record["files"]["supportK"], np.float64),
        "faces": load_array(directory / record["files"]["faces"], np.uint32).reshape(-1, 3),
    }
    arrays["vertex_count"] = int(record["vertexCount"])
    arrays["meters"] = float(manifest["sourceMetersPerUnit"])
    arrays["surface_k"] = float(record["surfaceK"])
    arrays["damping"] = float(record["damping"])
    arrays["stable_dt"] = float(record["stableDt"])
    arrays["face_scale"] = float(record["faceScale"])
    arrays["model"] = model
    arrays["domain"] = domain
    arrays["anatomical_axes"] = record.get("anatomicalAxes", {"right": [1.0, 0.0, 0.0], "up": [0.0, 1.0, 0.0], "front": [0.0, 0.0, 1.0]})
    return arrays


def load_node_reference(reference_manifest: dict, reference_path: Path, model: str, domain: str, stage: str):
    record = reference_manifest["models"].get(model, {}).get(domain)
    if not record:
        return None
    stage_record = record["stages"].get(stage)
    if not stage_record:
        return None
    count = int(record["vertexCount"])
    positions = np.fromfile(reference_path.parent / stage_record["positions"], dtype=np.float64).reshape(count, 3)
    velocities = np.fromfile(reference_path.parent / stage_record["velocities"], dtype=np.float64).reshape(count, 3)
    return positions, velocities, None, float(stage_record["runtimeMs"])


def csr_from_edges(vertex_count: int, edge_a: np.ndarray, edge_b: np.ndarray, rest: np.ndarray):
    counts = np.bincount(np.concatenate((edge_a, edge_b)), minlength=vertex_count)
    offsets = np.zeros(vertex_count + 1, dtype=np.int32)
    offsets[1:] = np.cumsum(counts, dtype=np.int64)
    cursor = offsets[:-1].copy()
    neighbors = np.empty(len(edge_a) * 2, dtype=np.int32)
    rests = np.empty(len(edge_a) * 2, dtype=np.float32)
    for a, b, r in zip(edge_a, edge_b, rest):
        neighbors[cursor[a]] = b; rests[cursor[a]] = r; cursor[a] += 1
        neighbors[cursor[b]] = a; rests[cursor[b]] = r; cursor[b] += 1
    return offsets, neighbors, rests


def csr_from_support(vertex_count: int, support_a: np.ndarray, support_b: np.ndarray, rest: np.ndarray, stiffness: np.ndarray):
    counts = np.bincount(support_a, minlength=vertex_count)
    offsets = np.zeros(vertex_count + 1, dtype=np.int32)
    offsets[1:] = np.cumsum(counts, dtype=np.int64)
    cursor = offsets[:-1].copy()
    neighbors = np.empty(len(support_a), dtype=np.int32)
    rests = np.empty(len(support_a), dtype=np.float32)
    ks = np.empty(len(support_a), dtype=np.float32)
    for a, b, r, k in zip(support_a, support_b, rest, stiffness):
        neighbors[cursor[a]] = b; rests[cursor[a]] = r; ks[cursor[a]] = k; cursor[a] += 1
    return offsets, neighbors, rests, ks


def make_pinch(fixture: dict):
    face = fixture["faces"][len(fixture["faces"]) // 2]
    ids = face.astype(np.int32)
    weights = np.full(3, 1.0 / 3.0, dtype=np.float32)
    neutral = fixture["neutral"].reshape(-1, 3)
    origin = neutral[face].mean(axis=0)
    target = origin.copy()
    target[1] += fixture["face_scale"] * 0.001
    return ids, weights, target.astype(np.float32), np.zeros(3, dtype=np.float32)


def cpu_acceleration(fixture: dict, positions: np.ndarray, velocities: np.ndarray, gravity: np.ndarray, pinch=None):
    n = fixture["vertex_count"]
    force = np.zeros((n, 3), dtype=np.float64)
    a = fixture["edge_a"].astype(np.int64)
    b = fixture["edge_b"].astype(np.int64)
    delta = positions[b] - positions[a]
    lengths = np.linalg.norm(delta, axis=1)
    valid = lengths > 1.0e-12
    q = np.zeros_like(lengths)
    q[valid] = fixture["surface_k"] * ((lengths[valid] - fixture["edge_rest"][valid]) * fixture["meters"]) / lengths[valid]
    spring_force = delta * q[:, None]
    np.add.at(force, a, spring_force)
    np.add.at(force, b, -spring_force)
    sa = fixture["support_a"].astype(np.int64)
    sb = fixture["support_b"].astype(np.int64)
    sdelta = fixture["anchors"].reshape(-1, 3)[sb] - positions[sa]
    slengths = np.linalg.norm(sdelta, axis=1)
    svalid = slengths > 1.0e-12
    sq = np.zeros_like(slengths)
    sq[svalid] = fixture["support_k"][svalid] * ((slengths[svalid] - fixture["support_rest"][svalid]) * fixture["meters"]) / slengths[svalid]
    np.add.at(force, sa, sdelta * sq[:, None])
    if pinch is not None:
        ids, weights, target, target_velocity, kp, kd = pinch
        point = np.sum(positions[ids] * weights[:, None], axis=0)
        point_velocity = np.sum(velocities[ids] * weights[:, None], axis=0)
        applied = kp * ((target - point) * fixture["meters"]) + kd * ((target_velocity - point_velocity) * fixture["meters"])
        np.add.at(force, ids, weights[:, None] * applied[None, :])
    force += fixture["masses"][:, None] * gravity[None, :] - fixture["damping"] * velocities * fixture["meters"]
    return force / (fixture["masses"][:, None] * fixture["meters"]), force


def cpu_step(fixture: dict, positions: np.ndarray, velocities: np.ndarray, h: float, gravity: np.ndarray, pinch=None):
    a1, _ = cpu_acceleration(fixture, positions, velocities, gravity, pinch)
    x2 = positions + velocities * h * 0.5
    v2 = velocities + a1 * h * 0.5
    a2, _ = cpu_acceleration(fixture, x2, v2, gravity, pinch)
    x3 = positions + v2 * h * 0.5
    v3 = velocities + a2 * h * 0.5
    a3, _ = cpu_acceleration(fixture, x3, v3, gravity, pinch)
    x4 = positions + v3 * h
    v4 = velocities + a3 * h
    a4, _ = cpu_acceleration(fixture, x4, v4, gravity, pinch)
    return (
        positions + h * (velocities + 2.0 * v2 + 2.0 * v3 + v4) / 6.0,
        velocities + h * (a1 + 2.0 * a2 + 2.0 * a3 + a4) / 6.0,
    )


def cpu_simulate(fixture: dict, seconds: float, gravity: np.ndarray, pinch=None, initial_positions=None, initial_velocities=None):
    positions = (fixture["neutral"].reshape(-1, 3) if initial_positions is None else initial_positions).copy()
    velocities = (np.zeros_like(positions) if initial_velocities is None else initial_velocities).copy()
    h0 = fixture["stable_dt"]
    elapsed = 0.0
    started = time.perf_counter()
    while elapsed < seconds - 1.0e-15:
        h = min(h0, seconds - elapsed)
        positions, velocities = cpu_step(fixture, positions, velocities, h, gravity, pinch)
        elapsed += h
    _, forces = cpu_acceleration(fixture, positions, velocities, gravity, pinch)
    return positions, velocities, forces, (time.perf_counter() - started) * 1000.0


class WarpSimulation:
    def __init__(self, fixture: dict, device: str):
        self.fixture = fixture
        self.device = device
        n = fixture["vertex_count"]
        neutral = fixture["neutral"].astype(np.float32)
        self.positions = wp.array(neutral, dtype=wp.float32, device=device)
        self.velocities = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.out_positions = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.out_velocities = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.a1 = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.a2 = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.a3 = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.a4 = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.x2 = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.x3 = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.x4 = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.v2 = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.v3 = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.v4 = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.forces = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.accel = wp.zeros(n * 3, dtype=wp.float32, device=device)
        self.masses = wp.array(fixture["masses"].astype(np.float32), dtype=wp.float32, device=device)
        self.anchors = wp.array(fixture["anchors"].astype(np.float32), dtype=wp.float32, device=device)
        sa_o, sa_n, sa_r = csr_from_edges(n, fixture["edge_a"], fixture["edge_b"], fixture["edge_rest"])
        sp_o, sp_n, sp_r, sp_k = csr_from_support(n, fixture["support_a"], fixture["support_b"], fixture["support_rest"], fixture["support_k"])
        self.surface_offsets = wp.array(sa_o, dtype=wp.int32, device=device)
        self.surface_neighbors = wp.array(sa_n, dtype=wp.int32, device=device)
        self.surface_rest = wp.array(sa_r, dtype=wp.float32, device=device)
        self.support_offsets = wp.array(sp_o, dtype=wp.int32, device=device)
        self.support_neighbors = wp.array(sp_n, dtype=wp.int32, device=device)
        self.support_rest = wp.array(sp_r, dtype=wp.float32, device=device)
        self.support_k = wp.array(sp_k, dtype=wp.float32, device=device)
        self.pinch_ids = wp.zeros(3, dtype=wp.int32, device=device)
        self.pinch_weights = wp.zeros(3, dtype=wp.float32, device=device)
        self.pinch_target = wp.zeros(3, dtype=wp.float32, device=device)
        self.pinch_velocity = wp.zeros(3, dtype=wp.float32, device=device)
        self.neutral_host = fixture["neutral"].reshape(-1, 3).copy()
        self.n = n

    def reset(self, initial_positions=None, initial_velocities=None):
        start_positions = self.neutral_host if initial_positions is None else initial_positions
        start_velocities = np.zeros_like(self.neutral_host) if initial_velocities is None else initial_velocities
        self.positions.assign(np.asarray(start_positions, dtype=np.float32).reshape(-1))
        self.velocities.assign(np.asarray(start_velocities, dtype=np.float32).reshape(-1))

    def set_pinch(self, pinch):
        if pinch is None:
            self.use_pinch = 0
            return
        ids, weights, target, velocity, _, _ = pinch
        self.pinch_ids.assign(ids)
        self.pinch_weights.assign(weights)
        self.pinch_target.assign(target)
        self.pinch_velocity.assign(velocity)
        self.use_pinch = 1

    def launch_acceleration(self, positions, velocities, out_acceleration, gravity, pinch):
        wp.launch(
            acceleration_kernel,
            dim=self.n,
            inputs=[positions, velocities, out_acceleration, self.forces, self.masses, self.anchors,
                    self.surface_offsets, self.surface_neighbors, self.surface_rest,
                    self.support_offsets, self.support_neighbors, self.support_rest, self.support_k,
                    self.pinch_ids, self.pinch_weights, self.pinch_target, self.pinch_velocity,
                    float(gravity[0]), float(gravity[1]), float(gravity[2]), float(self.fixture["meters"]),
                    float(self.fixture["surface_k"]), float(self.fixture["damping"]),
                    float(pinch[4]) if pinch is not None else 0.0,
                    float(pinch[5]) if pinch is not None else 0.0, self.use_pinch],
            device=self.device,
        )

    def _launch_step(self, h, gravity, pinch):
        self.launch_acceleration(self.positions, self.velocities, self.a1, gravity, pinch)
        wp.launch(rk4_stage_kernel, dim=self.n, inputs=[self.positions, self.velocities, self.a1, self.x2, self.v2, float(h * 0.5)], device=self.device)
        self.launch_acceleration(self.x2, self.v2, self.a2, gravity, pinch)
        wp.launch(rk4_stage_kernel, dim=self.n, inputs=[self.positions, self.velocities, self.a2, self.x3, self.v3, float(h * 0.5)], device=self.device)
        self.launch_acceleration(self.x3, self.v3, self.a3, gravity, pinch)
        wp.launch(rk4_stage_kernel, dim=self.n, inputs=[self.positions, self.velocities, self.a3, self.x4, self.v4, float(h)], device=self.device)
        self.launch_acceleration(self.x4, self.v4, self.a4, gravity, pinch)
        wp.launch(rk4_combine_kernel, dim=self.n, inputs=[self.positions, self.velocities, self.a1, self.a2, self.a3, self.a4, self.out_positions, self.out_velocities, float(h)], device=self.device)
        self.positions, self.out_positions = self.out_positions, self.positions
        self.velocities, self.out_velocities = self.out_velocities, self.velocities

    def advance(self, seconds, gravity, pinch=None):
        """Advance the resident GPU state without resetting or reading per substep."""
        h0 = self.fixture["stable_dt"]
        elapsed = 0.0
        steps = 0
        started = time.perf_counter()
        self.set_pinch(pinch)
        while elapsed < seconds - 1.0e-15:
            h = min(h0, seconds - elapsed)
            self._launch_step(h, gravity, pinch)
            elapsed += h
            steps += 1
        self.launch_acceleration(self.positions, self.velocities, self.accel, gravity, pinch)
        wp.synchronize_device(self.device)
        runtime_ms = (time.perf_counter() - started) * 1000.0
        positions = self.positions.numpy().reshape(-1, 3).astype(np.float64)
        velocities = self.velocities.numpy().reshape(-1, 3).astype(np.float64)
        forces = self.forces.numpy().reshape(-1, 3).astype(np.float64)
        return positions, velocities, forces, runtime_ms, steps

    def step(self, h, gravity, pinch):
        self._launch_step(h, gravity, pinch)

    def capture_chunk(self, h, gravity, pinch, chunk_steps):
        self.set_pinch(pinch)
        try:
            wp.capture_begin(device=self.device)
            for _ in range(chunk_steps):
                self._launch_step(h, gravity, pinch)
            graph = wp.capture_end(device=self.device)
            return graph, None
        except Exception as exc:
            try:
                wp.capture_end(device=self.device)
            except Exception:
                pass
            return None, str(exc)

    def simulate(self, seconds, gravity, pinch=None, use_cuda_graph=False, graph_chunk=16,
                 initial_positions=None, initial_velocities=None):
        self.reset(initial_positions, initial_velocities)
        h0 = self.fixture["stable_dt"]
        elapsed = 0.0
        steps = 0
        started = time.perf_counter()
        self.set_pinch(pinch)
        graph = None
        graph_error = None
        if use_cuda_graph and h0 > 0.0:
            graph, graph_error = self.capture_chunk(h0, gravity, pinch, max(1, graph_chunk))
        while elapsed < seconds - 1.0e-15:
            remaining = seconds - elapsed
            if graph is not None and remaining >= h0 * graph_chunk - 1.0e-15:
                wp.capture_launch(graph)
                elapsed += h0 * graph_chunk
                steps += graph_chunk
            else:
                h = min(h0, remaining)
                self._launch_step(h, gravity, pinch)
                elapsed += h
                steps += 1
        self.set_pinch(pinch)
        self.launch_acceleration(self.positions, self.velocities, self.accel, gravity, pinch)
        wp.synchronize_device(self.device)
        runtime_ms = (time.perf_counter() - started) * 1000.0
        positions = self.positions.numpy().reshape(-1, 3).astype(np.float64)
        velocities = self.velocities.numpy().reshape(-1, 3).astype(np.float64)
        forces = self.forces.numpy().reshape(-1, 3).astype(np.float64)
        return positions, velocities, forces, runtime_ms, steps, graph_error


def energy_metrics(fixture, positions, velocities):
    a = fixture["edge_a"].astype(np.int64); b = fixture["edge_b"].astype(np.int64)
    lengths = np.linalg.norm(positions[b] - positions[a], axis=1)
    surface = 0.5 * fixture["surface_k"] * np.sum(((lengths - fixture["edge_rest"]) * fixture["meters"]) ** 2)
    sa = fixture["support_a"].astype(np.int64); sb = fixture["support_b"].astype(np.int64)
    slengths = np.linalg.norm(fixture["anchors"].reshape(-1, 3)[sb] - positions[sa], axis=1)
    support = 0.5 * np.sum(fixture["support_k"] * ((slengths - fixture["support_rest"]) * fixture["meters"]) ** 2)
    kinetic = 0.5 * np.sum(fixture["masses"] * np.sum((velocities * fixture["meters"]) ** 2, axis=1))
    return {"surfacePotentialJ": float(surface), "supportPotentialJ": float(support), "kineticJ": float(kinetic), "mechanicalJ": float(surface + support + kinetic)}


def geometry_metrics(fixture, positions):
    a = fixture["edge_a"].astype(np.int64); b = fixture["edge_b"].astype(np.int64)
    lengths = np.linalg.norm(positions[b] - positions[a], axis=1)
    strain = np.abs(lengths - fixture["edge_rest"]) / np.maximum(fixture["edge_rest"], 1.0e-12)
    faces = fixture["faces"].astype(np.int64)
    neutral = fixture["neutral"].reshape(-1, 3)
    n0 = np.cross(neutral[faces[:, 1]] - neutral[faces[:, 0]], neutral[faces[:, 2]] - neutral[faces[:, 0]])
    n1 = np.cross(positions[faces[:, 1]] - positions[faces[:, 0]], positions[faces[:, 2]] - positions[faces[:, 0]])
    areas = np.linalg.norm(n1, axis=1) * 0.5
    neutral_areas = np.linalg.norm(n0, axis=1) * 0.5
    flips = int(np.count_nonzero(np.sum(n0 * n1, axis=1) < 0.0))
    collapses = int(np.count_nonzero(areas / np.maximum(neutral_areas, 1.0e-18) < 1.0e-3))
    return {"maxEdgeStrain": float(np.max(strain, initial=0.0)), "p95EdgeStrain": float(np.quantile(strain, 0.95) if len(strain) else 0.0), "orientationFlips": flips, "collapsedTriangles": collapses, "minAreaRatio": float(np.min(areas / np.maximum(neutral_areas, 1.0e-18), initial=1.0))}


def compare(cpu, gpu, fixture, label):
    cpu_positions, cpu_velocities, cpu_forces, cpu_runtime = cpu
    gpu_positions, gpu_velocities, gpu_forces, gpu_runtime, gpu_steps, graph_error = gpu
    pos_delta = gpu_positions - cpu_positions
    vel_delta = gpu_velocities - cpu_velocities
    force_delta = None if cpu_forces is None else gpu_forces - cpu_forces
    return {
        "label": label,
        "cpuRuntimeMs": cpu_runtime,
        "gpuRuntimeMs": gpu_runtime,
        "speedup": cpu_runtime / max(gpu_runtime, 1.0e-12),
        "gpuSteps": gpu_steps,
        "cudaGraphError": graph_error,
        "positionMaxErrorSource": float(np.max(np.linalg.norm(pos_delta, axis=1), initial=0.0)),
        "positionRmsErrorSource": float(np.sqrt(np.mean(np.sum(pos_delta * pos_delta, axis=1)))),
        "positionMaxErrorNormalizedFace": float(np.max(np.linalg.norm(pos_delta, axis=1), initial=0.0) / max(fixture["face_scale"], 1.0e-12)),
        "velocityMaxErrorSourcePerSecond": float(np.max(np.linalg.norm(vel_delta, axis=1), initial=0.0)),
        "forceMaxErrorN": None if force_delta is None else float(np.max(np.linalg.norm(force_delta, axis=1), initial=0.0)),
        "cpuEnergy": energy_metrics(fixture, cpu_positions, cpu_velocities),
        "gpuEnergy": energy_metrics(fixture, gpu_positions, gpu_velocities),
        "gpuGeometry": geometry_metrics(fixture, gpu_positions),
        "cpuGeometry": geometry_metrics(fixture, cpu_positions),
    }


def selected_domains(manifest, requested):
    out = []
    for item in requested:
        model, domain = item.split(":", 1)
        if model not in manifest["models"] or domain not in manifest["models"][model]:
            raise ValueError(f"Unknown fixture domain {item}")
        out.append((model, domain))
    return out


def js_rng(seed):
    """Match the LCG used by calibrate_realtime_rk4.mjs exactly."""
    state = int(seed) & 0xFFFFFFFF

    def random():
        nonlocal state
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        return (state + 0.5) / 4294967296.0

    return random


def random_pinch(fixture, random, kp, kd):
    faces = fixture["faces"]
    face_index = min(int(random() * len(faces)), len(faces) - 1)
    ids = faces[face_index].astype(np.int32)
    u, v = random(), random()
    if u + v > 1.0:
        u, v = 1.0 - u, 1.0 - v
    weights = np.asarray([1.0 - u - v, u, v], dtype=np.float32)
    neutral = fixture["neutral"].reshape(-1, 3)
    origin = np.sum(neutral[ids] * weights[:, None], axis=0)
    direction_names = ("down", "up", "left", "right", "forward", "backward")
    direction_name = direction_names[min(int(random() * len(direction_names)), len(direction_names) - 1)]
    axes = fixture["anatomical_axes"]
    direction_map = {
        "down": -np.asarray(axes["up"], dtype=np.float64),
        "up": np.asarray(axes["up"], dtype=np.float64),
        "left": -np.asarray(axes["right"], dtype=np.float64),
        "right": np.asarray(axes["right"], dtype=np.float64),
        "forward": np.asarray(axes["front"], dtype=np.float64),
        "backward": -np.asarray(axes["front"], dtype=np.float64),
    }
    direction = direction_map[direction_name]
    magnitude = fixture["face_scale"] * (0.002 + random() * 0.01)
    target = origin + direction * magnitude
    return {
        "ids": ids,
        "weights": weights,
        "origin": origin,
        "target": target.astype(np.float32),
        "direction": direction,
        "directionName": direction_name,
        "magnitude": magnitude,
        "velocity": (direction * magnitude * 4.0).astype(np.float32),
        "kp": kp,
        "kd": kd,
    }


def point_state(positions, velocities, pinch, target=None):
    ids = pinch["ids"]
    weights = pinch["weights"].astype(np.float64)
    point = np.sum(positions[ids] * weights[:, None], axis=0)
    point_velocity = np.sum(velocities[ids] * weights[:, None], axis=0)
    target = pinch["target"].astype(np.float64) if target is None else np.asarray(target, dtype=np.float64)
    target_velocity = pinch["velocity"].astype(np.float64)
    return point, point_velocity, float(np.linalg.norm(target - point))


def gpu_random_stress(fixture, count, seed, hold_seconds, release_seconds, kp, kd, device, use_cuda_graph, graph_chunk):
    random = js_rng(seed)
    simulator = WarpSimulation(fixture, device)
    results = []
    started = time.perf_counter()
    for sequence in range(count):
        pinch = random_pinch(fixture, random, kp, kd)
        positions = fixture["neutral"].reshape(-1, 3).copy()
        velocities = np.zeros_like(positions)
        held_geometry = None
        held_complete = True
        peak_force = 0.0
        peak_tracking_error = 0.0
        invalid = False
        for phase in range(1, 5):
            phase_target = pinch["origin"] + (pinch["target"].astype(np.float64) - pinch["origin"]) * (phase / 4.0)
            segment_pinch = (pinch["ids"], pinch["weights"], phase_target.astype(np.float32), pinch["velocity"], kp, kd)
            gravity = pinch["direction"] * 9.81
            positions, velocities, forces, runtime_ms, steps, graph_error = simulator.simulate(
                hold_seconds, gravity, segment_pinch, use_cuda_graph, graph_chunk, positions, velocities
            )
            held_geometry = geometry_metrics(fixture, positions)
            held_complete = bool(held_complete and graph_error is None and np.isfinite(positions).all() and np.isfinite(velocities).all())
            point, point_velocity, tracking_error = point_state(positions, velocities, pinch, phase_target)
            applied = kp * ((phase_target.astype(np.float64) - point) * fixture["meters"])
            applied += kd * ((pinch["velocity"].astype(np.float64) - point_velocity) * fixture["meters"])
            peak_force = max(peak_force, float(np.linalg.norm(applied)))
            peak_tracking_error = max(peak_tracking_error, tracking_error * fixture["meters"])
            invalid = invalid or held_geometry["orientationFlips"] > 0 or held_geometry["collapsedTriangles"] > 0
        release_gravity = pinch["direction"] * 9.81
        release = simulator.simulate(release_seconds, release_gravity, None, use_cuda_graph, graph_chunk, positions, velocities)
        release_positions, release_velocities, _, release_runtime, release_steps, release_graph_error = release
        released_geometry = geometry_metrics(fixture, release_positions)
        invalid = invalid or released_geometry["orientationFlips"] > 0 or released_geometry["collapsedTriangles"] > 0
        results.append({
            "sequence": sequence,
            "face": pinch["ids"].astype(int).tolist(),
            "direction": pinch["directionName"],
            "magnitudeSource": pinch["magnitude"],
            "held": held_geometry,
            "released": released_geometry,
            "heldComplete": held_complete,
            "releaseComplete": bool(release_graph_error is None and np.isfinite(release_positions).all() and np.isfinite(release_velocities).all()),
            "wallClockExceeded": False,
            "recoveredDisplacementSource": float(np.max(np.linalg.norm(release_positions - fixture["neutral"].reshape(-1, 3), axis=1), initial=0.0)),
            "peakForceN": peak_force,
            "peakTrackingErrorMeters": peak_tracking_error,
            "releaseRuntimeMs": release_runtime,
            "releaseSteps": release_steps,
            "valid": bool(not invalid and release_graph_error is None and np.isfinite(release_positions).all()),
        })
    return {
        "count": count,
        "seed": seed,
        "holdSeconds": hold_seconds,
        "releaseSeconds": release_seconds,
        "valid": all(item["valid"] for item in results),
        "results": results,
        "runtimeMs": (time.perf_counter() - started) * 1000.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="verification/island-spring-pinch/gpu-fixtures/manifest.json")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seconds", type=float, default=0.001)
    parser.add_argument("--domains", default="female:micro,female:screen,female:full,male:micro,male:screen,male:full")
    parser.add_argument("--output", default="verification/island-spring-pinch/rk4-warp-gpu-benchmark.json")
    parser.add_argument("--cpu-reference-manifest", default="verification/island-spring-pinch/gpu-cpu-references/manifest.json")
    parser.add_argument("--pinch-kp", type=float, default=1.0)
    parser.add_argument("--pinch-kd", type=float, default=1.0)
    parser.add_argument("--cuda-graph", action="store_true")
    parser.add_argument("--graph-chunk", type=int, default=16)
    parser.add_argument("--stress-count", type=int, default=0)
    parser.add_argument("--stress-seed", type=int, default=20261111)
    parser.add_argument("--stress-hold-seconds", type=float, default=1.0 / 60.0)
    parser.add_argument("--stress-release-seconds", type=float, default=0.05)
    parser.add_argument("--stress-output", default="verification/island-spring-pinch/rk4-warp-gpu-stress.json")
    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    reference_path = Path(args.cpu_reference_manifest)
    reference_manifest = json.loads(reference_path.read_text()) if reference_path.exists() else None
    domains = selected_domains(manifest, [x.strip() for x in args.domains.split(",") if x.strip()])
    gravity_results = []
    pinch_results = []
    for model, domain in domains:
        fixture = load_fixture(manifest_path, model, domain)
        axes = fixture["anatomical_axes"]
        gravity = -9.81 * np.asarray(axes["up"], dtype=np.float64)
        cpu = cpu_simulate(fixture, args.seconds, gravity)
        gpu_sim = WarpSimulation(fixture, args.device)
        gpu = gpu_sim.simulate(args.seconds, gravity, use_cuda_graph=args.cuda_graph, graph_chunk=max(1, args.graph_chunk))
        gravity_record = {"model": model, "domain": domain, "vertices": fixture["vertex_count"], "numpyFloat64": compare(cpu, gpu, fixture, "gravity")}
        node_reference = load_node_reference(reference_manifest, reference_path, model, domain, "gravity") if reference_manifest and abs(args.pinch_kp - 0.1) < 1.0e-12 and abs(args.pinch_kd - 0.01) < 1.0e-12 else None
        if node_reference is not None:
            gravity_record["nodeFloat64Reference"] = compare(node_reference, gpu, fixture, "gravity")
        gravity_results.append(gravity_record)

        ids, weights, target, target_velocity = make_pinch(fixture)
        pinch = (ids, weights, target, target_velocity, args.pinch_kp, args.pinch_kd)
        hold_seconds = args.seconds
        cpu_hold = cpu_simulate(fixture, hold_seconds, gravity, pinch)
        gpu_hold = gpu_sim.simulate(hold_seconds, gravity, pinch, use_cuda_graph=args.cuda_graph, graph_chunk=max(1, args.graph_chunk))
        cpu_release = cpu_simulate(fixture, hold_seconds, gravity, None, cpu_hold[0], cpu_hold[1])
        # Release starts from the held GPU state, matching the CPU release initial state.
        gpu_sim.positions.assign(gpu_hold[0].astype(np.float32).reshape(-1))
        gpu_sim.velocities.assign(gpu_hold[1].astype(np.float32).reshape(-1))
        elapsed = 0.0
        started = time.perf_counter()
        gpu_sim.set_pinch(None)
        while elapsed < hold_seconds - 1.0e-15:
            h = min(fixture["stable_dt"], hold_seconds - elapsed)
            gpu_sim._launch_step(h, gravity, None)
            elapsed += h
        wp.synchronize_device(args.device)
        release_positions = gpu_sim.positions.numpy().reshape(-1, 3).astype(np.float64)
        release_velocities = gpu_sim.velocities.numpy().reshape(-1, 3).astype(np.float64)
        gpu_sim.launch_acceleration(gpu_sim.positions, gpu_sim.velocities, gpu_sim.accel, gravity, None)
        wp.synchronize_device(args.device)
        release_forces = gpu_sim.forces.numpy().reshape(-1, 3).astype(np.float64)
        release_runtime = (time.perf_counter() - started) * 1000.0
        gpu_release = (release_positions, release_velocities, release_forces, release_runtime, int(round(hold_seconds / fixture["stable_dt"])), None)
        pinch_record = {
            "model": model, "domain": domain, "vertices": fixture["vertex_count"],
            "hold": {"numpyFloat64": compare(cpu_hold, gpu_hold, fixture, "pinch-hold")},
            "release": {"numpyFloat64": compare(cpu_release, gpu_release, fixture, "pinch-release")},
            "pinchTargetSource": target.tolist(), "pinchTriangleVertexIds": ids.tolist(), "pinchWeights": weights.tolist(),
        }
        if reference_manifest and abs(args.pinch_kp - 0.1) < 1.0e-12 and abs(args.pinch_kd - 0.01) < 1.0e-12:
            node_hold = load_node_reference(reference_manifest, reference_path, model, domain, "pinchHold")
            node_release = load_node_reference(reference_manifest, reference_path, model, domain, "pinchRelease")
            if node_hold is not None: pinch_record["hold"]["nodeFloat64Reference"] = compare(node_hold, gpu_hold, fixture, "pinch-hold")
            if node_release is not None: pinch_record["release"]["nodeFloat64Reference"] = compare(node_release, gpu_release, fixture, "pinch-release")
        pinch_results.append(pinch_record)
    report = {
        "schema": "vela-rk4-warp-gpu-benchmark-v1",
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "device": args.device,
        "warpVersion": wp.__version__,
        "cudaAvailable": wp.is_cuda_available(),
        "sourceMetersPerUnit": manifest["sourceMetersPerUnit"],
        "secondsPerRun": args.seconds,
        "pinchKp": args.pinch_kp,
        "pinchKd": args.pinch_kd,
        "cudaGraph": args.cuda_graph,
        "graphChunk": args.graph_chunk,
        "reference": "NumPy Float64 implementation of the exported existing Node Float64 equations; fixture topology and parameters are emitted by calibrate_realtime_rk4.mjs.",
        "gravity": gravity_results,
        "pinch": pinch_results,
    }
    if args.stress_count > 0:
        stress_records = []
        for model_index, (model, domain) in enumerate(domains):
            fixture = load_fixture(manifest_path, model, domain)
            stress_records.append({
                "model": model,
                "domain": domain,
                "vertices": fixture["vertex_count"],
                "gpu": gpu_random_stress(
                    fixture, args.stress_count, args.stress_seed + 100 + model_index,
                    args.stress_hold_seconds, args.stress_release_seconds, args.pinch_kp, args.pinch_kd,
                    args.device, args.cuda_graph, max(1, args.graph_chunk)
                ),
            })
        report["stress"] = {
            "seed": args.stress_seed,
            "count": args.stress_count,
            "holdSeconds": args.stress_hold_seconds,
            "releaseSeconds": args.stress_release_seconds,
            "records": stress_records,
            "overall": "SUCCESS" if all(record["gpu"]["valid"] for record in stress_records) else "FAILED",
        }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    if args.stress_count > 0:
        stress_output = Path(args.stress_output)
        stress_output.parent.mkdir(parents=True, exist_ok=True)
        stress_output.write_text(json.dumps(report["stress"], indent=2))
    print(json.dumps({"output": str(output), "device": args.device, "domains": len(domains), "warp": wp.__version__}, indent=2))


if __name__ == "__main__":
    main()
