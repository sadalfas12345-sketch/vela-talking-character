"""Apply the weighted, independent Goal 1 anatomical scoring rubric."""
import argparse
import json
from pathlib import Path


REGIONS = {
    'lips_mouth': {
        'weight': 30,
        'names': ('mouth_corner_', 'upper_lip_', 'lower_lip_'),
    },
    'eyes_eyelids': {
        'weight': 25,
        'names': ('eye_', 'eyelid_'),
    },
    'nose': {'weight': 15, 'names': ('nose_',)},
    'jaw_chin': {'weight': 10, 'names': ('jawline_', 'chin')},
    'eyebrows': {'weight': 10, 'names': ('eyebrow',)},
    'remaining': {'weight': 10, 'names': ()},
}


def region_for(name):
    if 'eye' in name or 'eyelid' in name:
        return 'eyes_eyelids'
    if 'eyebrow' in name:
        return 'eyebrows'
    for region, spec in REGIONS.items():
        if any(name.startswith(prefix) or name == prefix for prefix in spec['names']):
            return region
    return 'remaining'


def score_report(path):
    report = json.loads(Path(path).read_text(encoding='utf-8'))
    results = {region: {
        'weight': spec['weight'], 'evaluated': 0, 'verifiedCorrect': 0,
        'incorrect': 0, 'occluded': 0, 'unresolved': 0, 'unreviewed': 0,
        'points': [], 'score': None,
    } for region, spec in REGIONS.items()}
    for point in report.get('points', []):
        region = region_for(point['name'])
        result = results[region]
        result['evaluated'] += 1
        status = 'unreviewed'
        if point.get('surfaceClassification') == 'UNRESOLVED':
            result['unresolved'] += 1
            status = 'unresolved'
        elif point.get('obliqueVisibleFirstSurface') is False:
            result['occluded'] += 1
            status = 'occluded'
        elif not point.get('withinManualUncertainty') or point.get('surfaceClassification') != 'FRONT_SURFACE':
            result['incorrect'] += 1
            status = 'incorrect_or_outside_tolerance'
        elif point.get('withinManualUncertainty') and point.get('surfaceClassification') == 'FRONT_SURFACE':
            result['verifiedCorrect'] += 1
            status = 'provisional_correct'
        else:
            result['unreviewed'] += 1
        result['points'].append({'name': point['name'], 'status': status, 'pixelError': point['pixelError'], 'normalizedInterocularError': point['normalizedInterocularError'], 'tolerancePixels': point['manualUncertaintyPixels']})

    evaluated_weight = 0
    weighted_points = 0.0
    for result in results.values():
        if result['evaluated']:
            evaluated_weight += result['weight']
            result['score'] = result['weight'] * result['verifiedCorrect'] / result['evaluated']
            weighted_points += result['score']
    critical = {name: results[name]['score'] for name in ('lips_mouth', 'eyes_eyelids')}
    independent = report.get('independentValidation', '')
    overall = None if 'UNVERIFIED' in independent else weighted_points
    return {
        'status': 'PROVISIONAL_UNVERIFIED_SINGLE_REVIEWER',
        'rubric': {'lips_mouth': 30, 'eyes_eyelids': 25, 'nose': 15, 'jaw_chin': 10, 'eyebrows': 10, 'remaining': 10},
        'correctnessTolerance': '2D error <= each reference point manualUncertaintyPixels; front-surface hit; oblique first-surface visibility; no unresolved or incorrect region assignment',
        'overallScoreOutOf100': overall,
        'provisionalScoreOnEvaluatedRegionsOutOf100': (weighted_points / evaluated_weight * 100.0) if evaluated_weight else None,
        'evaluatedWeight': evaluated_weight,
        'criticalRegionThreshold': 80,
        'criticalRegionScores': critical,
        'regions': results,
        'independentValidation': independent,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('comparison_report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = score_report(args.comparison_report)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'overallScoreOutOf100', 'provisionalScoreOnEvaluatedRegionsOutOf100', 'evaluatedWeight', 'criticalRegionScores')}, indent=2))


if __name__ == '__main__':
    main()
