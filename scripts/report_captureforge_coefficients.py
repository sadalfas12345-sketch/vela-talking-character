import csv, json, sys
from pathlib import Path

src = Path(sys.argv[1])
out = Path(sys.argv[2])
with src.open(newline='', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
names = [k for k in rows[0] if k not in {'time','headRotX','headRotY','headRotZ','headPosX','headPosY','headPosZ'}]
report = {'source': str(src), 'frames': len(rows), 'coefficient_count': len(names), 'coefficients': {}}
for name in names:
    vals = [float(r[name]) for r in rows]
    i_min = min(range(len(vals)), key=vals.__getitem__)
    i_max = max(range(len(vals)), key=vals.__getitem__)
    report['coefficients'][name] = {
        'min': min(vals), 'max': max(vals), 'range': max(vals)-min(vals),
        'mean': sum(vals)/len(vals), 'min_frame': i_min, 'max_frame': i_max,
        'nonzero_frames': sum(abs(v) > 1e-6 for v in vals),
    }
report['selected'] = {k: report['coefficients'][k] for k in ['browInnerUp','browDownLeft','browDownRight','eyeBlinkLeft','eyeBlinkRight','jawOpen','mouthSmileLeft','mouthSmileRight'] if k in report['coefficients']}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({'frames': report['frames'], 'coefficient_count': report['coefficient_count'], 'selected': report['selected']}, indent=2))
