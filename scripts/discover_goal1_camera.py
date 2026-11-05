"""Select a frontal camera from rendered GLB candidates using MediaPipe geometry."""
import argparse
import json
import math
import shutil
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


def detect(image_path, model_path):
    image = cv2.imread(str(image_path))
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.IMAGE, num_faces=1,
        output_face_blendshapes=False, output_facial_transformation_matrixes=False)
    with vision.FaceLandmarker.create_from_options(options) as landmarker:
        result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not result.face_landmarks:
        return None
    return np.asarray([[p.x, p.y, p.z] for p in result.face_landmarks[0]], dtype=np.float64)


def evaluate(landmarks):
    if landmarks is None or len(landmarks) < 478:
        return None
    width = 640.0
    height = 640.0
    p = landmarks[:, :2] * np.array([width, height])
    right_eye = p[33]
    left_eye = p[263]
    nose = p[1]
    mouth_right = p[61]
    mouth_left = p[291]
    eye_mid = (right_eye + left_eye) * 0.5
    eye_distance = float(np.linalg.norm(left_eye - right_eye))
    if eye_distance <= 1.0:
        return None
    bbox_min = p.min(axis=0)
    bbox_max = p.max(axis=0)
    bbox_area = float(np.prod(bbox_max - bbox_min) / (width * height))
    eye_level = abs(float(left_eye[1] - right_eye[1])) / eye_distance
    mouth_level = abs(float(mouth_left[1] - mouth_right[1])) / eye_distance
    nose_center_offset = abs(float(nose[0] - eye_mid[0])) / eye_distance
    eye_mid_y = float(eye_mid[1]) / height
    # The score uses only standard anatomical landmark geometry. It does not
    # assume a world axis, object name, character height, or Tripo dimensions.
    frontal_symmetry = 1.0 / (1.0 + 2.0 * eye_level + mouth_level + nose_center_offset)
    size_score = min(1.0, math.sqrt(max(0.0, bbox_area)) * 3.0)
    center_score = max(0.0, 1.0 - abs(float(eye_mid[0]) / width - 0.5) * 2.0)
    score = 0.60 * frontal_symmetry + 0.25 * size_score + 0.15 * center_score
    return {
        'score': float(score), 'eyeDistancePixels': eye_distance,
        'bboxAreaFraction': bbox_area, 'eyeLevelError': eye_level,
        'mouthLevelError': mouth_level, 'noseCenterOffset': nose_center_offset,
        'eyeMidpoint': eye_mid.tolist(), 'landmarks': landmarks.tolist(),
    }


def overlay(image_path, landmarks, output_path):
    image = cv2.imread(str(image_path))
    points = np.asarray(landmarks)[:, :2] * np.array([image.shape[1], image.shape[0]])
    for index, (x, y) in enumerate(points):
        color = (0, 255, 80) if index in {1, 33, 61, 133, 263, 291, 362} else (0, 180, 255)
        cv2.circle(image, (round(x), round(y)), 2 if index not in {1, 33, 61, 133, 263, 291, 362} else 5, color, -1, cv2.LINE_AA)
    cv2.imwrite(str(output_path), image)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('candidate_dir', type=Path)
    parser.add_argument('model', type=Path)
    args = parser.parse_args()
    metadata = json.loads((args.candidate_dir / 'candidate-cameras.json').read_text(encoding='utf-8'))
    candidates = []
    for item in metadata['candidates']:
        image = args.candidate_dir / item['image']
        landmarks = detect(image, args.model)
        evaluation = evaluate(landmarks)
        if evaluation:
            candidates.append({**item, **{k: v for k, v in evaluation.items() if k != 'landmarks'}, 'landmarks': evaluation['landmarks']})
    if not candidates:
        raise SystemExit('No candidate view produced a MediaPipe face detection.')
    candidates.sort(key=lambda x: x['score'], reverse=True)
    best = candidates[0]
    shutil.copy2(args.candidate_dir / best['image'], args.candidate_dir / 'frontal-neutral.png')
    overlay(args.candidate_dir / best['image'], best['landmarks'], args.candidate_dir / 'frontal-landmarks.png')
    camera = {k: best[k] for k in ('index', 'cameraLocation', 'target', 'orthoScale', 'resolution', 'projection')}
    camera.update({
        'sourceGLB': metadata['sourceGLB'], 'boundsMin': metadata['boundsMin'], 'boundsMax': metadata['boundsMax'],
        'center': metadata['center'], 'selectionScore': best['score'], 'eyeDistancePixels': best['eyeDistancePixels'],
        'detectedLandmarks': 478, 'selectionMethod': 'spherical GLB-bound candidate views scored by MediaPipe eye, nose, mouth symmetry and face size',
    })
    (args.candidate_dir / 'discovered-camera.json').write_text(json.dumps(camera, indent=2) + '\n', encoding='utf-8')
    (args.candidate_dir / 'detected-landmarks.json').write_text(json.dumps({
        'image': str((args.candidate_dir / best['image']).resolve()), 'width': 640, 'height': 640,
        'landmarks': best['landmarks'], 'camera': camera,
    }, indent=2) + '\n', encoding='utf-8')
    (args.candidate_dir / 'candidate-evaluations.json').write_text(json.dumps({
        'candidateCount': len(metadata['candidates']), 'detectedCandidateCount': len(candidates),
        'selected': best, 'candidates': candidates,
    }, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'candidateCount': len(metadata['candidates']), 'detectedCandidateCount': len(candidates), 'selectedIndex': best['index'], 'score': best['score'], 'eyeDistancePixels': best['eyeDistancePixels']}))


if __name__ == '__main__':
    main()
