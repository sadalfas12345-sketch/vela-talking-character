"""Evaluate provisional anatomical references against the existing Goal 1 runs.

References are hand-selected from the untouched selected frontal renders. They
are not copied from MediaPipe or raycast output. This script deliberately labels
the result provisional until an independent reviewer confirms the annotations.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'verification' / 'goal1-generalization-run'
OUT = RUN / 'cross-character-accuracy'

# 36 representative anatomical points. Values are image pixels in the existing
# 640x640 selected renders, selected by visual inspection. Male lip points have
# wider uncertainty because beard and moustache obscure the vermilion boundary.
REFS = {
    'female': {
        33:(275,316,4,'eyesEyelids','left eye outer'), 133:(303,320,4,'eyesEyelids','left eye inner'),
        159:(287,313,4,'eyesEyelids','left upper lid'), 145:(290,321,4,'eyesEyelids','left lower lid'),
        263:(362,314,4,'eyesEyelids','right eye outer'), 362:(336,319,4,'eyesEyelids','right eye inner'),
        386:(352,312,4,'eyesEyelids','right upper lid'), 374:(348,320,4,'eyesEyelids','right lower lid'),
        168:(320,320,5,'nose','nose bridge'), 6:(320,330,5,'nose','nose dorsum'),
        1:(321,366,5,'nose','nose tip'), 98:(303,359,5,'nose','left nose wing'), 327:(337,359,5,'nose','right nose wing'),
        61:(292,370,4,'lipsMouth','left mouth corner'), 291:(347,368,4,'lipsMouth','right mouth corner'),
        13:(321,379,4,'lipsMouth','upper lip center'), 14:(321,381,4,'lipsMouth','lower lip center'),
        78:(295,371,4,'lipsMouth','left upper vermilion'), 308:(345,369,4,'lipsMouth','right upper vermilion'),
        82:(314,378,4,'lipsMouth','left lower vermilion'), 312:(327,378,4,'lipsMouth','right lower vermilion'),
        152:(320,410,6,'jawChin','chin'), 172:(269,368,7,'jawChin','left jawline'), 397:(367,365,7,'jawChin','right jawline'),
        70:(266,303,5,'eyebrows','left brow inner'), 63:(272,302,5,'eyebrows','left brow'), 105:(281,302,5,'eyebrows','left brow outer'),
        336:(334,308,5,'eyebrows','right brow inner'), 293:(370,299,5,'eyebrows','right brow'), 334:(361,300,5,'eyebrows','right brow outer'),
        10:(320,274,8,'remaining','forehead center'), 234:(260,350,8,'remaining','left cheek'), 454:(380,350,8,'remaining','right cheek'),
        127:(250,342,8,'remaining','left face outline'), 356:(390,341,8,'remaining','right face outline'), 199:(320,399,8,'remaining','lower face')
    },
    'male': {
        33:(244,358,5,'eyesEyelids','left eye outer'), 133:(296,364,5,'eyesEyelids','left eye inner'),
        159:(266,360,5,'eyesEyelids','left upper lid'), 145:(272,369,5,'eyesEyelids','left lower lid'),
        263:(413,346,5,'eyesEyelids','right eye outer'), 362:(361,361,5,'eyesEyelids','right eye inner'),
        386:(392,349,5,'eyesEyelids','right upper lid'), 374:(385,362,5,'eyesEyelids','right lower lid'),
        168:(329,369,6,'nose','nose bridge'), 6:(330,387,6,'nose','nose dorsum'),
        1:(333,469,7,'nose','nose tip'), 98:(297,458,7,'nose','left nose wing'), 327:(367,455,7,'nose','right nose wing'),
        61:(284,494,9,'lipsMouth','left mouth corner'), 291:(376,492,9,'lipsMouth','right mouth corner'),
        13:(331,502,10,'lipsMouth','upper lip center'), 14:(331,503,10,'lipsMouth','lower lip center'),
        78:(288,495,9,'lipsMouth','left upper vermilion'), 308:(373,493,9,'lipsMouth','right upper vermilion'),
        82:(319,501,10,'lipsMouth','left lower vermilion'), 312:(343,500,10,'lipsMouth','right lower vermilion'),
        152:(332,577,7,'jawChin','chin'), 172:(226,487,9,'jawChin','left jawline'), 397:(431,478,9,'jawChin','right jawline'),
        70:(215,333,6,'eyebrows','left brow inner'), 63:(226,329,6,'eyebrows','left brow'), 105:(244,330,6,'eyebrows','left brow outer'),
        336:(358,342,6,'eyebrows','right brow inner'), 293:(429,319,6,'eyebrows','right brow'), 334:(411,322,6,'eyebrows','right brow outer'),
        10:(330,285,10,'remaining','forehead center'), 234:(235,440,10,'remaining','left cheek'), 454:(420,438,10,'remaining','right cheek'),
        127:(215,430,10,'remaining','left face outline'), 356:(444,423,10,'remaining','right face outline'), 199:(332,556,10,'remaining','lower face')
    }
}

WEIGHTS = {'lipsMouth':30, 'eyesEyelids':25, 'nose':15, 'jawChin':10, 'eyebrows':10, 'remaining':10}

def load(model):
    base = RUN / f'{model}-camera'
    detected = json.loads((base/'detected-landmarks.json').read_text())['landmarks']
    raycast = json.loads((base/'raycast-report.json').read_text())['records']
    return detected, raycast

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    for model, refs in REFS.items():
        detected, raycast = load(model)
        points = []
        ipd = ((detected[33][0]-detected[263][0])**2 + (detected[33][1]-detected[263][1])**2) ** 0.5 * 640
        # MediaPipe coordinates are normalized; references are pixels.
        for index, (rx, ry, tolerance, region, feature) in refs.items():
            dx, dy = detected[index][0]*640, detected[index][1]*640
            error = ((dx-rx)**2 + (dy-ry)**2) ** 0.5
            hit = raycast[index]
            valid_surface = bool(hit.get('frontSurface')) and bool(hit.get('surfaceVisibleFromFrontalCamera'))
            status = 'correct' if error <= tolerance and valid_surface else 'incorrect'
            points.append({
                'model': model, 'feature': feature, 'region': region, 'mediapipeIndex': index,
                'detectedXY': [round(dx,3), round(dy,3)], 'referenceXY': [rx, ry],
                'pixelError': round(error,3), 'interocularNormalizedError': round(error/ipd,5),
                'tolerancePixels': tolerance, 'surfaceValid': valid_surface,
                'occludedOrAmbiguous': not valid_surface, 'status': status,
                'confidence': 'provisional single-reviewer reference'
            })
        region_scores = {}
        for region, maximum in WEIGHTS.items():
            group = [p for p in points if p['region'] == region]
            correct = sum(p['status'] == 'correct' for p in group)
            unresolved = sum(p['occludedOrAmbiguous'] for p in group)
            region_scores[region] = {
                'maximumPoints': maximum, 'evaluated': len(group), 'correct': correct,
                'incorrect': len(group)-correct-unresolved, 'occludedOrAmbiguous': unresolved,
                'score': round(maximum*correct/len(group),3) if group else None,
                'status': 'PROVISIONAL'
            }
        errors = sorted(p['pixelError'] for p in points)
        weighted = sum(v['score'] or 0 for v in region_scores.values())
        summary[model] = {
            'landmarksDetected': 478, 'validGeometricAttachments': sum(1 for r in raycast if r.get('frontSurface')),
            'reviewedPoints': len(points), 'provisionalWeightedScore': round(weighted,3),
            'medianPixelError': errors[len(errors)//2], 'p90PixelError': errors[int(len(errors)*.9)-1],
            'p95PixelError': errors[int(len(errors)*.95)-1], 'interocularPixels': round(ipd,3),
            'regions': region_scores, 'independentValidation': 'UNVERIFIED: single provisional reviewer',
            'points': points
        }
        image_dir = OUT / model
        image_dir.mkdir(parents=True, exist_ok=True)
        source = Image.open(RUN / f'{model}-camera' / 'frontal-neutral.png').convert('RGB')
        font = ImageFont.load_default()
        numbered = source.copy(); nd = ImageDraw.Draw(numbered)
        vectors = source.copy(); vd = ImageDraw.Draw(vectors)
        colors = {'lipsMouth':(255,70,70), 'eyesEyelids':(60,220,100), 'nose':(60,170,255), 'jawChin':(190,100,255), 'eyebrows':(255,190,40), 'remaining':(220,220,220)}
        for n, p in enumerate(points, 1):
            x, y = p['detectedXY']; rx, ry = p['referenceXY']; color = colors[p['region']]
            nd.ellipse((x-3,y-3,x+3,y+3), fill=color, outline='white')
            nd.text((x+4,y-7), str(n), fill='white', font=font)
            vd.line((x,y,rx,ry), fill='red', width=1)
            vd.ellipse((x-3,y-3,x+3,y+3), fill='orange', outline='white')
            vd.ellipse((rx-3,ry-3,rx+3,ry+3), fill='lime', outline='black')
        numbered.save(image_dir/'numbered-anatomical-overlay.png')
        vectors.save(image_dir/'detected-versus-reference-vectors.png')
        for name, region in [('mouth','lipsMouth'),('eyes','eyesEyelids'),('nose','nose')]:
            subset = [p for p in points if p['region'] == region]
            xs = [p['detectedXY'][0] for p in subset] + [p['referenceXY'][0] for p in subset]
            ys = [p['detectedXY'][1] for p in subset] + [p['referenceXY'][1] for p in subset]
            pad = 35
            box = (max(0,int(min(xs)-pad)), max(0,int(min(ys)-pad)), min(source.width,int(max(xs)+pad)), min(source.height,int(max(ys)+pad)))
            vectors.crop(box).resize(((box[2]-box[0])*3,(box[3]-box[1])*3)).save(image_dir/f'{name}-error-vectors.png')
    (OUT/'cross-character-accuracy.json').write_text(json.dumps(summary, indent=2)+'\n')
    lines = ['# Goal 1 cross-character anatomical accuracy', '',
             'References were placed by visual inspection of the untouched selected frontal renders. They were not copied from MediaPipe or raycast output. They are provisional single-reviewer annotations, not independent ground truth.', '']
    for model, data in summary.items():
        lines += [f'## {model.title()}', '', f"- Detected landmarks: {data['landmarksDetected']}", f"- Valid geometric attachments: {data['validGeometricAttachments']}", f"- Provisional reviewed points: {data['reviewedPoints']}", f"- Median error: {data['medianPixelError']} px", f"- P90 error: {data['p90PixelError']} px", f"- P95 error: {data['p95PixelError']} px", f"- Interocular distance: {data['interocularPixels']} px", f"- Provisional weighted score: {data['provisionalWeightedScore']} / 100", '- Certified score: UNVERIFIED', '', '| Region | Weight | Correct | Incorrect | Occluded or ambiguous | Provisional score |', '|---|---:|---:|---:|---:|---:|']
        for region, r in data['regions'].items():
            lines.append(f"| {region} | {r['maximumPoints']} | {r['correct']} | {r['incorrect']} | {r['occludedOrAmbiguous']} | {r['score']} |")
        lines += ['', 'The male mouth region has materially wider uncertainty because beard and moustache obscure the vermilion boundary. Provisional values must not be used as certified anatomical accuracy.', '']
    (OUT/'cross-character-accuracy.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
