"""Build deterministic triangle attachments for the selected Goal 1 anchors.

This is an inspection-only artifact generator. It reads the untouched Tripo GLB,
does not edit or resave it, and records the triangle and barycentric attachment
for each selected detector landmark that passed the existing surface audit.
"""
import json
import math
import struct
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
GLB = ROOT / 'assets/tripo/vela-photoreal/generated-rigged.glb'
DETECTED = ROOT / 'verification/goal1-tripo-detected-landmarks.json'
RAYCAST = ROOT / 'verification/goal1-tripo-landmark-evidence/goal1-tripo-landmark-report.json'
COMPARE = ROOT / 'verification/goal1-tripo-landmark-evidence/goal1-independent-validation-report.json'
OUT = ROOT / 'verification/goal1-tripo-landmark-evidence'
IMAGE = ROOT / 'assets/tripo/vela-photoreal/verification/face-closeup.png'

GREEN = (40, 210, 70)
YELLOW = (0, 210, 255)
RED = (50, 50, 230)


def read_glb(path):
    data = path.read_bytes()
    offset = 12
    document = None
    binary = None
    while offset < len(data):
        length, chunk_type = struct.unpack_from('<II', data, offset)
        chunk = data[offset + 8:offset + 8 + length]
        if chunk_type == 0x4E4F534A:
            document = json.loads(chunk.decode('utf-8'))
        elif chunk_type == 0x004E4942:
            binary = chunk
        offset += 8 + length
    return document, binary


def accessor_array(document, binary, accessor_index):
    accessor = document['accessors'][accessor_index]
    view = document['bufferViews'][accessor['bufferView']]
    component_type = accessor['componentType']
    dtype = {5121: np.uint8, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}[component_type]
    components = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[accessor['type']]
    start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    count = accessor['count']
    item_bytes = np.dtype(dtype).itemsize * components
    stride = view.get('byteStride', item_bytes)
    raw = np.ndarray((count, stride), dtype=np.uint8, buffer=binary, offset=start)
    values = np.ndarray((count, components), dtype=dtype, buffer=raw.data, strides=(stride, np.dtype(dtype).itemsize))
    return values[:, 0] if components == 1 else values.copy()


def barycentric(point, triangle):
    a, b, c = triangle
    v0, v1, v2 = b - a, c - a, point - a
    d00, d01, d11 = np.dot(v0, v0), np.dot(v0, v1), np.dot(v1, v1)
    d20, d21 = np.dot(v2, v0), np.dot(v2, v1)
    denominator = d00 * d11 - d01 * d01
    if abs(denominator) < 1e-20:
        return None
    v = (d11 * d20 - d01 * d21) / denominator
    w = (d00 * d21 - d01 * d20) / denominator
    return np.asarray([1.0 - v - w, v, w], dtype=np.float64)


def draw(image, x, y, color, label, radius=5):
    cv2.circle(image, (round(x), round(y)), radius, color, -1, cv2.LINE_AA)
    cv2.putText(image, str(label), (round(x) + 7, round(y) - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)


def camera_project(point, camera, target=np.array([0.0, 0.0, 0.82]), ortho=0.20):
    forward = target - camera
    forward = forward / np.linalg.norm(forward)
    right = np.cross(forward, np.array([0.0, 1.0, 0.0]))
    right = right / np.linalg.norm(right)
    up = np.cross(right, forward)
    relative = point - camera
    return np.array([0.5 + np.dot(relative, right) / ortho, 0.5 - np.dot(relative, up) / ortho]) * 1024.0


def main():
    document, binary = read_glb(GLB)
    primitive = document['meshes'][0]['primitives'][0]
    positions = accessor_array(document, binary, primitive['attributes']['POSITION']).astype(np.float64)
    # glTF stores this asset in its Y-up frame. The existing Blender audit and
    # raycast report use the evaluated Blender frame: [x, -z, y].
    positions = positions[:, [0, 2, 1]]
    positions[:, 1] *= -1.0
    indices = accessor_array(document, binary, primitive['indices']).astype(np.int64).reshape(-1, 3)
    detected = json.loads(DETECTED.read_text(encoding='utf-8'))['landmarks']
    raycast = json.loads(RAYCAST.read_text(encoding='utf-8'))
    comparison = json.loads(COMPARE.read_text(encoding='utf-8'))
    ray_records = {int(item['index']): item for item in raycast['records']}
    comparison_records = {int(item['index']): item for item in comparison['points']}

    manifest = []
    for point in comparison['points']:
        index = int(point['index'])
        ray = ray_records[index]
        triangle_index = ray.get('triangleIndex')
        status = 'UNRESOLVED'
        cause = 'E_SURFACE_OCCLUSION_OR_AMBIGUITY'
        triangle_vertices = None
        weights = None
        local_position = None
        attachment_residual = None
        if triangle_index is not None and ray.get('frontSurface') and ray.get('surfaceVisibleFromFrontalCamera'):
            triangle_vertices = [int(v) for v in indices[int(triangle_index)]]
            triangle = positions[triangle_vertices]
            local_position = np.asarray(ray['meshXYZ'], dtype=np.float64)
            weights = barycentric(local_position, triangle)
            if weights is not None:
                reconstructed = weights @ triangle
                attachment_residual = float(np.linalg.norm(reconstructed - local_position))
                # The GLB POSITION accessor is float32; allow a small
                # float32 reconstruction residual while still rejecting a
                # point that is not on its recorded triangle.
                if attachment_residual <= 2e-6:
                    status = 'PROVISIONALLY_ACCEPTED'
                    cause = 'B_REFERENCE_PRECISION' if not point['withinManualUncertainty'] else 'NO_DEMONSTRATED_FAILURE'
        if index == 397 or triangle_index is None:
            status = 'UNRESOLVED'
            cause = 'E_SURFACE_OCCLUSION_OR_AMBIGUITY'
        confidence = 'provisional_geometry_only' if status == 'PROVISIONALLY_ACCEPTED' else 'unresolved'
        manifest.append({
            'number': point['number'], 'name': point['name'], 'mediapipeIndex': index,
            'region': point['region'], 'meshIdentifier': ray.get('hitObject'),
            'triangleIndex': triangle_index, 'triangleVertexIndices': triangle_vertices,
            'barycentricCoordinates': [float(v) for v in weights] if weights is not None else None,
            'local3D': [float(v) for v in local_position] if local_position is not None else None,
            'world3D': [float(v) for v in local_position] if local_position is not None else None,
            'cameraProjectionXY': ray.get('imageXY'), 'projectionResidualPixels': ray.get('projectionResidualPixels'),
            'surfaceNormal': ray.get('surfaceNormal'), 'frontalVisibility': ray.get('surfaceVisibleFromFrontalCamera'),
            'obliqueVisibility': ray.get('obliqueVisibleFirstSurface'), 'surfaceClassification': point['surfaceClassification'],
            'pixelErrorAgainstManualReference': point['pixelError'], 'manualUncertaintyPixels': point['manualUncertaintyPixels'],
            'status': status, 'causeClassification': cause, 'validationMethod': 'first-visible frontal ray, normal, ROI, oblique-view audit, barycentric reconstruction',
            'confidence': confidence, 'attachmentReconstructionResidualMeters': attachment_residual,
        })

    report = {
        'status': 'UNVERIFIED_PENDING_SECOND_INDEPENDENT_REVIEW',
        'sourceGLB': str(GLB.relative_to(ROOT)),
        'meshIdentifier': manifest[0]['meshIdentifier'],
        'selectedAnchorCount': len(manifest),
        'deterministicAttachmentCount': sum(x['status'] == 'PROVISIONALLY_ACCEPTED' for x in manifest),
        'provisionallyAcceptedCount': sum(x['status'] == 'PROVISIONALLY_ACCEPTED' for x in manifest),
        'correctedCount': 0,
        'rejectedCount': sum(x['status'] == 'REJECTED' for x in manifest),
        'unresolvedCount': sum(x['status'] == 'UNRESOLVED' for x in manifest),
        'independentlyValidatedCount': 0,
        'independentReview': 'PENDING: the reference set has one visual reviewer and is not independent ground truth.',
        'outlierCauseSummary': {
            'B_REFERENCE_PRECISION': [x['name'] for x in manifest if x['causeClassification'] == 'B_REFERENCE_PRECISION'],
            'E_SURFACE_OCCLUSION_OR_AMBIGUITY': [x['name'] for x in manifest if x['causeClassification'] == 'E_SURFACE_OCCLUSION_OR_AMBIGUITY'],
            'other': [],
        },
        'attachments': manifest,
    }
    (OUT / 'goal1-tripo-deterministic-landmark-manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')

    base = cv2.imread(str(IMAGE))
    frontal = base.copy()
    comparison_image = base.copy()
    for item in manifest:
        x, y = ray_records[int(item['mediapipeIndex'])]['imageXY']
        color = GREEN if item['status'] == 'PROVISIONALLY_ACCEPTED' and item['causeClassification'] == 'NO_DEMONSTRATED_FAILURE' else YELLOW if item['status'] == 'PROVISIONALLY_ACCEPTED' else RED
        draw(frontal, x, y, color, item['number'])
        ref = comparison_records[int(item['mediapipeIndex'])]['referenceXY']
        det = comparison_records[int(item['mediapipeIndex'])]['detectedXY']
        cv2.arrowedLine(comparison_image, (round(ref[0]), round(ref[1])), (round(det[0]), round(det[1])), color, 1, cv2.LINE_AA, tipLength=0.25)
        draw(comparison_image, det[0], det[1], color, item['number'])
    cv2.imwrite(str(OUT / 'goal1-final-30-mesh-attached-anchors-frontal.png'), frontal)
    cv2.imwrite(str(OUT / 'goal1-final-30-detected-vs-reference-color-coded.png'), comparison_image)
    cv2.imwrite(str(OUT / 'goal1-final-mouth-anchors-closeup.png'), frontal[285:410, 360:690])
    cv2.imwrite(str(OUT / 'goal1-final-eyelid-anchors-closeup.png'), frontal[65:215, 300:755])

    oblique_path = OUT / 'E_original_tripo_projected_landmarks_oblique.png'
    oblique = cv2.imread(str(oblique_path))
    camera = np.array([0.88, -0.42, 0.88])
    for item in manifest:
        if item['world3D'] is None:
            continue
        xy = camera_project(np.asarray(item['world3D']), camera)
        color = GREEN if item['status'] == 'PROVISIONALLY_ACCEPTED' and item['causeClassification'] == 'NO_DEMONSTRATED_FAILURE' else YELLOW if item['status'] == 'PROVISIONALLY_ACCEPTED' else RED
        draw(oblique, xy[0], xy[1], color, item['number'])
    cv2.imwrite(str(OUT / 'goal1-final-30-mesh-attached-anchors-oblique.png'), oblique)
    print(json.dumps({k: report[k] for k in ['selectedAnchorCount', 'deterministicAttachmentCount', 'correctedCount', 'rejectedCount', 'unresolvedCount', 'independentlyValidatedCount']}, indent=2))


if __name__ == '__main__':
    main()
