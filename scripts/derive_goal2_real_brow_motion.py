"""Derive target-world brow constraints from Avaturn's real browInnerUp key."""
import json, sys
from pathlib import Path
import numpy as np

BROW = [70, 63, 105, 336, 293, 334]

def arg(name):
    a = sys.argv[sys.argv.index('--') + 1:]
    return Path(a[a.index(name) + 1]).resolve()

def frame(points):
    left_eye = (points[33] + points[133] + points[159] + points[145]) / 4.0
    right_eye = (points[263] + points[362] + points[386] + points[374]) / 4.0
    eye_mid = (left_eye + right_eye) * .5
    x = right_eye - left_eye
    x /= np.linalg.norm(x)
    forward = points[1] - eye_mid
    forward -= x * np.dot(forward, x)
    forward /= np.linalg.norm(forward)
    up = eye_mid - points[152]
    up -= x * np.dot(up, x) + forward * np.dot(up, forward)
    up /= np.linalg.norm(up)
    if np.dot(up, eye_mid - points[152]) < 0:
        up *= -1
    return np.column_stack((x, up, forward))

eye_idx = 33

def main():
    donor_npz, donor_manifest, target_manifest, out = arg('--donor-npz'), arg('--donor-landmarks'), arg('--target-goal1'), arg('--output')
    z = np.load(donor_npz)
    p = json.loads(donor_manifest.read_text())
    tri = z['Head_Mesh__Triangles'][np.asarray(p['donorFaceIds'], dtype=int)]
    bary = np.asarray(p['donorBarycentric'], float)
    base = (bary[:, :, None] * z['Head_Mesh__Basis'][tri]).sum(axis=1)
    expr = (bary[:, :, None] * z['Head_Mesh__Key__browInnerUp'][tri]).sum(axis=1)
    donor_delta = expr - base
    records = json.loads(target_manifest.read_text())['records']
    target = {int(r['index']): np.asarray(r['meshXYZ'], float) for r in records if r.get('frontSurface') and r.get('meshXYZ')}
    donor_frame = frame(base)
    target_points = np.zeros_like(base)
    for i, p3 in target.items():
        target_points[i] = p3
    target_frame = frame(target_points)
    donor_eye = np.linalg.norm(base[33] - base[263])
    target_eye = np.linalg.norm(target[33] - target[263])
    scale = target_eye / donor_eye
    rotation = target_frame @ donor_frame.T
    desired = np.asarray([scale * rotation @ donor_delta[i] for i in BROW])
    result = {
        'expression': 'browInnerUp',
        'source': str(donor_npz),
        'donorEyeWidth': float(donor_eye),
        'targetEyeWidth': float(target_eye),
        'scale': float(scale),
        'donorFrame': donor_frame.tolist(),
        'targetFrame': target_frame.tolist(),
        'browLandmarkIndices': BROW,
        'donorDisplacements': donor_delta[BROW].tolist(),
        'desiredTargetWorldDisplacements': desired.tolist(),
        'desiredMagnitudesMillimeters': (np.linalg.norm(desired, axis=1) * 1000).tolist(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
