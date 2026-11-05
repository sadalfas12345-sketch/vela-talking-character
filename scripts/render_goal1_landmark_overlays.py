"""Create 2D Tripo-only landmark overlays from detector output."""
import json
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / 'assets/tripo/vela-photoreal/verification/face-closeup.png'
DETECTED = ROOT / 'verification/goal1-tripo-detected-landmarks.json'
OUT = ROOT / 'verification/goal1-tripo-landmark-evidence'
LABELS = {
    'right_eye_outer': 33, 'right_eye_inner': 133,
    'left_eye_outer': 263, 'left_eye_inner': 362,
    'right_eyelid_upper': 159, 'right_eyelid_lower': 145,
    'left_eyelid_upper': 386, 'left_eyelid_lower': 374,
    'right_eyebrow': 107, 'left_eyebrow': 336,
    'nose_bridge': 168, 'nose_tip': 1,
    'nose_wing_right': 98, 'nose_wing_left': 327,
    'mouth_corner_right': 61, 'mouth_corner_left': 291,
    'upper_lip_center': 13, 'lower_lip_center': 14,
    'chin': 152, 'jawline_right': 172, 'jawline_left': 397,
}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(IMAGE))
    detector = json.loads(DETECTED.read_text(encoding='utf-8'))
    h, w = image.shape[:2]
    points = [(int(round(x * w)), int(round(y * h))) for x, y, _ in detector['landmarks']]
    all_points = image.copy()
    for x, y in points:
        cv2.circle(all_points, (x, y), 3, (0, 255, 0), -1, cv2.LINE_AA)
    cv2.imwrite(str(OUT / 'B_original_tripo_detected_2d_landmarks.png'), all_points)

    crop = image.copy()
    for name, index in LABELS.items():
        x, y = points[index]
        cv2.circle(crop, (x, y), 6, (0, 0, 255), -1, cv2.LINE_AA)
        cv2.putText(crop, f'{name} [{index}]', (x + 7, y - 7),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(str(OUT / 'D_original_tripo_anatomical_labels.png'), crop)
    print('wrote', OUT / 'B_original_tripo_detected_2d_landmarks.png')
    print('wrote', OUT / 'D_original_tripo_anatomical_labels.png')

if __name__ == '__main__':
    main()
