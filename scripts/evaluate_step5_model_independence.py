import ast
import json
from pathlib import Path
import numpy as np

TRANSFER = Path('scripts/run_step4_tripo_landmark_transfer.py')
REPORT = Path('verification/goal2-browInnerUp-proof/step4-tripo-transfer/step4-transfer-report.json')
MARKER_ROOT = Path('verification/goal2-browInnerUp-proof/step4-tripo-transfer')
OUT = Path('verification/goal2-browInnerUp-proof/step5-model-independence.json')

def normalized(path):
    d = json.loads(path.read_text())
    out = {}
    neutral = np.asarray(d['neutral'], float)
    x = np.asarray(d['xAxis'], float)
    up = np.asarray(d['upAxis'], float)
    w = float(d['eyeWidth'])
    for k, p in d['samples'].items():
        p = np.asarray(p, float)
        delta = p - neutral
        out[k] = np.column_stack((delta @ x / w, -(delta @ up) / w))
    return out

def main():
    src = TRANSFER.read_text()
    tree = ast.parse(src)
    shared_entry = 'for model in [\'female\', \'male\']' in src and 'load_records(model)' in src
    forbidden = ['female_multiplier', 'male_multiplier', 'female_offset', 'male_offset', 'female_scale', 'male_scale']
    no_character_motion_params = not any(x in src for x in forbidden)
    f = normalized(MARKER_ROOT / 'female' / 'landmark_markers.json')
    m = normalized(MARKER_ROOT / 'male' / 'landmark_markers.json')
    diffs = {k: float(np.max(np.abs(f[k] - m[k]))) for k in f}
    max_diff = max(diffs.values())
    out = {'sharedEntryPoint': shared_entry, 'characterSpecificMotionParameters': not no_character_motion_params, 'trajectoryMaxDifferences': diffs, 'maxCrossCharacterNormalizedDifference': max_diff, 'criteria': {
        'sharedImplementation': {'pass': shared_entry},
        'zeroCharacterSpecificMotionParameters': {'pass': no_character_motion_params},
        'crossCharacterTrajectory': {'value': max_diff, 'threshold': .001, 'pass': max_diff <= .001},
    }}
    out['score'] = sum(5 for x in out['criteria'].values() if x['pass'])
    out['pass'] = out['score'] == 15
    OUT.write_text(json.dumps(out, indent=2) + '\n')

if __name__ == '__main__':
    main()
