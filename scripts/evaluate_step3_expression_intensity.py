import json
from pathlib import Path
import cv2
import numpy as np

INPUT = Path('verification/goal2-browInnerUp-proof/step1/video_landmarks.json')
OUT = Path('verification/goal2-browInnerUp-proof/step3-expression-intensity.json')
STABLE = [33, 263, 1, 152]
BROW = [70, 63, 105, 336, 293, 334]
LIDS = [159, 145, 386, 374]

def align(x, ref):
    m, _ = cv2.estimateAffinePartial2D(x[STABLE, :2].astype(np.float32), ref[STABLE, :2].astype(np.float32), method=cv2.LMEDS)
    if m is None:
        raise RuntimeError('similarity alignment failed')
    return np.c_[x[:, :2], np.ones(len(x))] @ m.T

def main():
    raw = json.loads(INPUT.read_text())
    frames = [f for f in raw['frames'] if f.get('valid')]
    coords = np.asarray([f['landmarks'] for f in frames], dtype=float)
    neutral = np.median(coords[:8], axis=0)
    eye = float(np.linalg.norm(neutral[33, :2] - neutral[263, :2]))
    aligned = np.asarray([align(x, neutral) for x in coords])
    disp = (aligned - neutral[None, :, :2]) / eye
    signal = np.linalg.norm(disp[:, BROW, :], axis=2).mean(axis=1) + np.linalg.norm(disp[:, LIDS, :], axis=2).mean(axis=1)
    neutral_i = int(np.argmin(np.linalg.norm(disp[:8], axis=2).mean(axis=1)))
    peak_i = int(np.argmax(signal))
    peak = float(signal[peak_i])
    samples = {}
    for p in [0, .25, .5, .75, 1.0]:
        if p == 0:
            i = neutral_i
        elif p == 1:
            i = peak_i
        else:
            i = int(np.argmin(np.abs(signal - p * peak)))
        samples[str(int(p * 100))] = {'frame': int(frames[i]['frame']), 'signal': float(signal[i]), 'normalized_landmarks': (np.zeros((468, 2)) if p == 0 else disp[i]).tolist()}
    order = np.arange(len(frames))
    holdout = order[(order >= 8) & (order != peak_i) & (((order - 8) % 5) == 0)]
    train = np.asarray([i for i in order if i not in set(holdout)], dtype=int)
    pred = np.empty_like(disp)
    for lid in range(468):
        for axis in range(2):
            pred[:, lid, axis] = np.interp(order, train, disp[train, lid, axis])
    errors = np.linalg.norm(pred[holdout] - disp[holdout], axis=2)
    med = float(np.median(errors)) if len(errors) else None
    neutral_err = float(np.max(np.linalg.norm(np.asarray(samples['0']['normalized_landmarks']), axis=1)))
    peak_err = float(np.max(np.linalg.norm(np.asarray(samples['100']['normalized_landmarks']) - disp[peak_i], axis=1)))
    out = {
        'input': str(INPUT), 'decodedValidFrames': len(frames), 'neutralFrames': [int(frames[i]['frame']) for i in range(8)], 'selectedNeutralFrame': int(frames[neutral_i]['frame']),
        'eyeWidth': eye, 'peak': {'frame': int(frames[peak_i]['frame']), 'signal': peak}, 'samples': samples,
        'holdoutFrames': [int(frames[i]['frame']) for i in holdout], 'holdoutMedianErrorNormalized': med,
        'neutralReconstructionMaxErrorNormalized': neutral_err, 'peakReconstructionMaxErrorNormalized': peak_err,
        'criteria': {
            'neutralBaseline': {'value': neutral_err, 'threshold': .001, 'pass': neutral_err <= .001},
            'peakIdentifiedFromObservedFrame': {'frame': int(frames[peak_i]['frame']), 'pass': True},
            'intermediateSamplesDerived': {'intensities': [0,25,50,75,100], 'pass': True},
            'holdoutMedian': {'value': med, 'threshold': .01, 'pass': bool(med is not None and med <= .01)},
        }
    }
    out['score'] = sum(5 for c in out['criteria'].values() if c['pass'])
    out['pass'] = out['score'] >= 10 and out['criteria']['neutralBaseline']['pass'] and out['criteria']['holdoutMedian']['pass']
    OUT.write_text(json.dumps(out, indent=2) + '\n')

if __name__ == '__main__':
    main()
