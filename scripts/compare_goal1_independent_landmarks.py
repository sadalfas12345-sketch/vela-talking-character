"""Compare manually selected Goal 1 references with detector and raycast data."""
import json
import math
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / 'assets/tripo/vela-photoreal/verification/face-closeup.png'
REF = ROOT / 'verification/goal1-independent-reference-set.json'
DETECTED = ROOT / 'verification/goal1-tripo-detected-landmarks.json'
RAYCAST = ROOT / 'verification/goal1-tripo-landmark-evidence/goal1-tripo-landmark-report.json'
OUT = ROOT / 'verification/goal1-tripo-landmark-evidence'

COLORS = {
    'right_eye': (255, 80, 80), 'left_eye': (80, 140, 255),
    'right_eyelid': (255, 160, 80), 'left_eyelid': (80, 220, 255),
    'nose_bridge': (180, 80, 255), 'nose_tip': (255, 0, 180),
    'nose_wing': (220, 0, 255), 'mouth_corner': (0, 180, 255),
    'upper_lip': (0, 180, 80), 'lower_lip': (0, 100, 220),
    'chin': (150, 150, 0), 'jawline': (0, 180, 180),
}

def draw_point(image, x, y, color, label=None, radius=5):
    cv2.circle(image, (int(round(x)), int(round(y))), radius, color, -1, cv2.LINE_AA)
    if label is not None:
        cv2.putText(image, str(label), (int(round(x)) + 7, int(round(y)) - 7),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

def main():
    base = cv2.imread(str(IMAGE))
    reference = json.loads(REF.read_text(encoding='utf-8'))
    detector = json.loads(DETECTED.read_text(encoding='utf-8'))
    raycast = json.loads(RAYCAST.read_text(encoding='utf-8'))
    detected = detector['landmarks']
    records = {int(item['index']): item for item in raycast['records']}
    points = reference['points']
    interocular = math.dist((points[0]['x'], points[0]['y']),
                            (next(p for p in points if p['name'] == 'left_eye_outer')['x'],
                             next(p for p in points if p['name'] == 'left_eye_outer')['y']))
    results = []
    full = base.copy()
    selected = base.copy()
    lips = base.copy()
    eyes = base.copy()
    for number, item in enumerate(points, 1):
        index = int(item['index'])
        dx, dy, _ = detected[index]
        detector_xy = (dx * base.shape[1], dy * base.shape[0])
        error = math.dist((item['x'], item['y']), detector_xy)
        region = item['region']
        color = COLORS.get(region, (0, 255, 0))
        ray = records.get(index, {})
        result = {
            'number': number,
            'name': item['name'],
            'index': index,
            'region': region,
            'referenceXY': [item['x'], item['y']],
            'detectedXY': [detector_xy[0], detector_xy[1]],
            'pixelError': error,
            'normalizedInterocularError': error / interocular,
            'manualUncertaintyPixels': item['uncertaintyPixels'],
            'withinManualUncertainty': error <= item['uncertaintyPixels'],
            'frontSurface': ray.get('frontSurface'),
            'frontNormalFacingDot': ray.get('frontNormalFacingDot'),
            'obliqueVisibleFirstSurface': ray.get('obliqueVisibleFirstSurface'),
            'meshXYZ': ray.get('meshXYZ'),
            'triangleIndex': ray.get('triangleIndex'),
            'surfaceClassification': (
                'UNRESOLVED' if not ray.get('surfaceVisibleFromFrontalCamera') else
                'AMBIGUOUS_NORMAL' if not ray.get('frontSurface') else
                'FRONT_SURFACE'
            ),
        }
        results.append(result)
        draw_point(selected, item['x'], item['y'], color, number)
        cv2.arrowedLine(full, (int(round(item['x'])), int(round(item['y']))),
                        (int(round(detector_xy[0])), int(round(detector_xy[1]))), color, 1, cv2.LINE_AA, tipLength=0.25)
        draw_point(full, item['x'], item['y'], (0, 0, 255), number)
        draw_point(full, detector_xy[0], detector_xy[1], (0, 255, 0), None, 4)
        if 'lip' in region or 'mouth' in region:
            draw_point(lips, item['x'], item['y'], (0, 0, 255), number)
            draw_point(lips, detector_xy[0], detector_xy[1], (0, 255, 0), None, 4)
        if 'eye' in region or 'eyelid' in region:
            draw_point(eyes, item['x'], item['y'], (0, 0, 255), number)
            draw_point(eyes, detector_xy[0], detector_xy[1], (0, 255, 0), None, 4)

    cv2.imwrite(str(OUT / 'goal1-30-numbered-independent-reference-points.png'), selected)
    cv2.imwrite(str(OUT / 'goal1-30-detected-vs-reference-error-vectors.png'), full)
    crop_lips = lips[285:410, 360:690]
    crop_eyes = eyes[65:215, 300:755]
    cv2.imwrite(str(OUT / 'goal1-30-lips-closeup-reference-vs-detected.png'), crop_lips)
    cv2.imwrite(str(OUT / 'goal1-30-eyelids-closeup-reference-vs-detected.png'), crop_eyes)

    errors = np.asarray([item['pixelError'] for item in results])
    normalized = np.asarray([item['normalizedInterocularError'] for item in results])
    report = {
        'status': 'UNVERIFIED_MANUAL_REFERENCE_NOT_INDEPENDENTLY_REVIEWED',
        'referenceMethod': reference['selectionMethod'],
        'referenceReviewStatus': reference['reviewStatus'],
        'selectedLandmarks': len(results),
        'interocularDistancePixels': interocular,
        'medianPixelError': float(np.median(errors)),
        'p95PixelError': float(np.percentile(errors, 95)),
        'medianNormalizedInterocularError': float(np.median(normalized)),
        'p95NormalizedInterocularError': float(np.percentile(normalized, 95)),
        'withinManualUncertaintyCount': sum(1 for item in results if item['withinManualUncertainty']),
        'frontSurfaceCount': sum(1 for item in results if item['surfaceClassification'] == 'FRONT_SURFACE'),
        'ambiguousNormalCount': sum(1 for item in results if item['surfaceClassification'] == 'AMBIGUOUS_NORMAL'),
        'unresolvedCount': sum(1 for item in results if item['surfaceClassification'] == 'UNRESOLVED'),
        'obliqueVisibleCount': sum(1 for item in results if item['obliqueVisibleFirstSurface'] is True),
        'obliqueOccludedOrAmbiguousCount': sum(1 for item in results if item['obliqueVisibleFirstSurface'] is False),
        'independentValidation': 'UNVERIFIED: reference selection was performed by one visual reviewer and requires second-person review.',
        'evidence': {
            'numberedReference': 'verification/goal1-tripo-landmark-evidence/goal1-30-numbered-independent-reference-points.png',
            'errorVectors': 'verification/goal1-tripo-landmark-evidence/goal1-30-detected-vs-reference-error-vectors.png',
            'lips': 'verification/goal1-tripo-landmark-evidence/goal1-30-lips-closeup-reference-vs-detected.png',
            'eyelids': 'verification/goal1-tripo-landmark-evidence/goal1-30-eyelids-closeup-reference-vs-detected.png',
            'oblique': 'verification/goal1-tripo-landmark-evidence/F_original_tripo_projected_landmarks_side.png',
        },
        'points': results,
    }
    (OUT / 'goal1-independent-validation-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['status', 'selectedLandmarks', 'interocularDistancePixels', 'medianPixelError', 'p95PixelError', 'medianNormalizedInterocularError', 'p95NormalizedInterocularError', 'withinManualUncertaintyCount', 'frontSurfaceCount', 'ambiguousNormalCount', 'unresolvedCount', 'obliqueVisibleCount', 'obliqueOccludedOrAmbiguousCount']}, indent=2))

if __name__ == '__main__':
    main()
