"""Model-agnostic Goal 1 GLB onboarding audit.

The command accepts any GLB and an output directory. It inspects meshes, node
transforms, cameras, skins, and head-related metadata without assuming Tripo
object names, vertex IDs, dimensions, or axes. Optional detector and surface
audit JSON files let an already calibrated evidence package be attached to the
model. Missing calibration is reported as UNVERIFIED rather than guessed.

Example:
  python scripts/onboard_goal1_model.py model.glb verification/onboarding/model
  python scripts/onboard_goal1_model.py model.glb out --landmarks-json points.json \
      --raycast-report surface-report.json --attachment-manifest manifest.json
"""
import argparse
import json
import math
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np


HEAD_TERMS = ('head', 'skull', 'face', 'facial', 'neck', 'jaw')


def read_glb(path):
    data = Path(path).read_bytes()
    off, document, binary = 12, None, None
    while off < len(data):
        length, chunk_type = struct.unpack_from('<II', data, off)
        chunk = data[off + 8:off + 8 + length]
        if chunk_type == 0x4E4F534A:
            document = json.loads(chunk.decode('utf-8'))
        elif chunk_type == 0x004E4942:
            binary = chunk
        off += 8 + length
    if document is None or binary is None:
        raise ValueError(f'Not a complete binary GLB: {path}')
    return document, binary


def matrix_from_node(node):
    if 'matrix' in node:
        # glTF matrices are column-major.
        return np.asarray(node['matrix'], dtype=np.float64).reshape(4, 4, order='F')
    t = np.eye(4, dtype=np.float64)
    if 'translation' in node:
        t[:3, 3] = node['translation']
    r = np.eye(4, dtype=np.float64)
    if 'rotation' in node:
        x, y, z, w = node['rotation']
        r[:3, :3] = np.array([
            [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
            [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
            [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y],
        ])
    s = np.eye(4, dtype=np.float64)
    if 'scale' in node:
        s[0, 0], s[1, 1], s[2, 2] = node['scale']
    return t @ r @ s


def world_matrices(document):
    nodes = document.get('nodes', [])
    parents = {}
    for i, node in enumerate(nodes):
        for child in node.get('children', []):
            parents[child] = i
    cache = {}

    def resolve(index):
        if index in cache:
            return cache[index]
        parent = parents.get(index)
        value = matrix_from_node(nodes[index])
        if parent is not None:
            value = resolve(parent) @ value
        cache[index] = value
        return value
    return {i: resolve(i) for i in range(len(nodes))}


def accessor_array(document, binary, index):
    accessor = document['accessors'][index]
    view = document['bufferViews'][accessor['bufferView']]
    dtype = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}[accessor['componentType']]
    components = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[accessor['type']]
    start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    count = accessor['count']
    item_bytes = np.dtype(dtype).itemsize * components
    stride = view.get('byteStride', item_bytes)
    raw = np.ndarray((count, stride), dtype=np.uint8, buffer=binary, offset=start)
    values = np.ndarray((count, components), dtype=dtype, buffer=raw.data, strides=(stride, np.dtype(dtype).itemsize))
    return values[:, 0].copy() if components == 1 else values.copy()


def transformed_bounds(document, binary, matrices):
    meshes = document.get('meshes', [])
    results = []
    for node_index, node in enumerate(document.get('nodes', [])):
        if 'mesh' not in node:
            continue
        mesh = meshes[node['mesh']]
        points = []
        for primitive in mesh.get('primitives', []):
            if 'POSITION' not in primitive.get('attributes', {}):
                continue
            positions = accessor_array(document, binary, primitive['attributes']['POSITION']).astype(np.float64)
            hom = np.column_stack((positions, np.ones(len(positions))))
            points.append((hom @ matrices[node_index].T)[:, :3])
        if not points:
            continue
        all_points = np.concatenate(points, axis=0)
        results.append({
            'nodeIndex': node_index,
            'nodeName': node.get('name', f'node_{node_index}'),
            'meshIndex': node['mesh'],
            'meshName': mesh.get('name', f'mesh_{node["mesh"]}'),
            'vertexCount': int(len(all_points)),
            'minXYZ': all_points.min(axis=0).tolist(),
            'maxXYZ': all_points.max(axis=0).tolist(),
        })
    return results


def metadata(document):
    nodes = document.get('nodes', [])
    head_nodes = []
    for i, node in enumerate(nodes):
        name = str(node.get('name', f'node_{i}'))
        if any(term in name.lower() for term in HEAD_TERMS):
            head_nodes.append({'nodeIndex': i, 'name': name, 'hasMesh': 'mesh' in node})
    cameras = [{'index': i, 'name': c.get('name', f'camera_{i}'), 'type': c.get('type')} for i, c in enumerate(document.get('cameras', []))]
    skins = [{'index': i, 'name': s.get('name', f'skin_{i}'), 'jointCount': len(s.get('joints', [])), 'skeleton': s.get('skeleton')} for i, s in enumerate(document.get('skins', []))]
    return head_nodes, cameras, skins


def load_optional(path):
    return json.loads(Path(path).read_text(encoding='utf-8')) if path else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('glb', type=Path)
    parser.add_argument('output_dir', type=Path)
    parser.add_argument('--landmarks-json', type=Path, help='MediaPipe landmark JSON for this exact model and calibrated image')
    parser.add_argument('--raycast-report', type=Path, help='First-visible surface audit for this exact model and camera')
    parser.add_argument('--attachment-manifest', type=Path, help='Barycentric attachment manifest for this exact model')
    parser.add_argument('--auto-camera', action='store_true', help='Discover a frontal camera, detect landmarks, and raycast them automatically')
    parser.add_argument('--blender', type=Path, default=Path(r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'))
    parser.add_argument('--landmarker-model', type=Path, default=Path('models/face_landmarker.task'))
    parser.add_argument('--candidate-count', type=int, default=32)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.auto_camera:
        camera_dir = args.output_dir / 'camera-discovery'
        render_script = Path(__file__).with_name('render_goal1_camera_candidates.py').resolve()
        discover_script = Path(__file__).with_name('discover_goal1_camera.py').resolve()
        raycast_script = Path(__file__).with_name('raycast_goal1_discovered_camera.py').resolve()
        subprocess.run([
            str(args.blender), '-b', '--python', str(render_script), '--',
            str(args.glb.resolve()), str(camera_dir.resolve()), str(args.candidate_count)
        ], check=True)
        subprocess.run([
            sys.executable, str(discover_script), str(camera_dir.resolve()),
            str(args.landmarker_model.resolve())
        ], check=True)
        args.landmarks_json = camera_dir / 'detected-landmarks.json'
        args.raycast_report = camera_dir / 'raycast-report.json'
        subprocess.run([
            str(args.blender), '-b', '--python', str(raycast_script), '--',
            str(args.glb.resolve()), str((camera_dir / 'discovered-camera.json').resolve()),
            str(args.raycast_report.resolve())
        ], check=True)

    document, binary = read_glb(args.glb)
    matrices = world_matrices(document)
    meshes = transformed_bounds(document, binary, matrices)
    head_nodes, cameras, skins = metadata(document)
    all_points = np.asarray([p for m in meshes for p in (m['minXYZ'], m['maxXYZ'])], dtype=np.float64) if meshes else np.empty((0, 3))
    bounds = {'minXYZ': all_points.min(axis=0).tolist(), 'maxXYZ': all_points.max(axis=0).tolist()} if len(all_points) else None
    diagonal = float(np.linalg.norm(all_points.max(axis=0) - all_points.min(axis=0))) if len(all_points) else None

    landmark_data = load_optional(args.landmarks_json)
    raycast_data = load_optional(args.raycast_report)
    attachment_data = load_optional(args.attachment_manifest)
    detected_count = len(landmark_data.get('landmarks', [])) if landmark_data else 0
    surface_count = raycast_data.get('validFrontSurfaceHits') if raycast_data else None
    attachment_count = attachment_data.get('deterministicAttachmentCount') if attachment_data else None
    orientation_status = 'CALIBRATED_AUTOMATICALLY' if args.auto_camera else ('CALIBRATED_FROM_SUPPLIED_EVIDENCE' if raycast_data else 'UNVERIFIED_NO_MODEL_CAMERA_CALIBRATION')
    head_status = 'CANDIDATE_HEAD_METADATA_FOUND' if head_nodes else 'AMBIGUOUS_NO_HEAD_METADATA'
    detection_status = 'EVIDENCE_ATTACHED' if landmark_data else 'UNVERIFIED_NO_RENDERED_FACE_INPUT'
    report = {
        'model': str(args.glb),
        'pipeline': 'model-agnostic GLB onboarding audit, no geometry edits',
        'meshCount': len(document.get('meshes', [])),
        'nodeCount': len(document.get('nodes', [])),
        'materialCount': len(document.get('materials', [])),
        'animationCount': len(document.get('animations', [])),
        'boundsWorld': bounds,
        'worldDiagonal': diagonal,
        'meshInventory': meshes,
        'candidateHeadMetadata': head_nodes,
        'cameras': cameras,
        'skins': skins,
        'orientationStatus': orientation_status,
        'headDetectionStatus': head_status,
        'detectionStatus': detection_status,
        'landmarksDetected': detected_count,
        'validVisibleSurfaceAttachments': surface_count,
        'anatomicallyPlausibleAttachments': None,
        'deterministicAttachments': attachment_count,
        'unresolvedOrAmbiguous': (raycast_data.get('unresolvedLandmarks', 0) + raycast_data.get('ambiguousSurfaceHits', 0)) if raycast_data else None,
        'independentAccuracy': 'UNVERIFIED unless an external anatomical reference and reviewer are supplied',
        'sourceCodeChangesBetweenModels': False,
        'limitations': [
            'A GLB alone does not contain anatomical ground truth or a guaranteed frontal camera.',
            'Automatic focus uses head-bone metadata when available and otherwise the imported mesh bounds; the method is recorded in camera-discovery/candidate-cameras.json.',
            'Anatomical correctness remains unverified without independent reference annotations.',
        ],
    }
    (args.output_dir / 'goal1-onboarding-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (args.output_dir / 'goal1-onboarding-report.md').write_text(
        '# Goal 1 model onboarding\n\n'
        f'- Model: `{args.glb}`\n'
        f'- Meshes: {report["meshCount"]}; nodes: {report["nodeCount"]}; world diagonal: {diagonal}\n'
        f'- Head metadata: **{head_status}**\n'
        f'- Orientation: **{orientation_status}**\n'
        f'- Landmark detection: **{detection_status}**\n'
        f'- Detected landmarks: {detected_count}\n'
        f'- Valid visible surface attachments: {surface_count}\n'
        f'- Deterministic attachments: {attachment_count}\n'
        f'- Independent anatomical accuracy: **UNVERIFIED**\n\n'
        'No geometry was modified. Missing camera calibration or anatomical references are reported as unverified.\n',
        encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('model', 'meshCount', 'worldDiagonal', 'headDetectionStatus', 'orientationStatus', 'detectionStatus', 'landmarksDetected', 'validVisibleSurfaceAttachments', 'deterministicAttachments', 'unresolvedOrAmbiguous')}, indent=2))


if __name__ == '__main__':
    main()
