"""Summarize independent spatially matched Goal-2 measurements."""
import json, sys
from pathlib import Path

def main():
    a=sys.argv[sys.argv.index('--')+1:]; root=Path(a[a.index('--root')+1]).resolve(); out=Path(a[a.index('--report')+1]).resolve()
    result={}
    for model in ['female','male']:
        d=json.loads((root/f'{model}-model-agnostic-measurements.json').read_text()); by={int(i):x for i,x in d['landmarkDisplacements'].items()}
        def side(ids,field='magnitudeMillimeters'):
            vals=[by[i][field] for i in ids]
            return {'maxMillimeters':max(vals),'medianMillimeters':sum(vals)/len(vals),'normalizedMax':max(vals)/json.loads((root/f'{model}-model-agnostic-transfer.json').read_text())['eyeWidthMillimeters']}
        transfer=json.loads((root/f'{model}-model-agnostic-transfer.json').read_text()); eye=transfer['eyeWidthMillimeters']
        browL=[by[i]['magnitudeMillimeters'] for i in [70,63,105]]; browR=[by[i]['magnitudeMillimeters'] for i in [336,293,334]]
        lidL=[by[i]['magnitudeMillimeters'] for i in [159,145]]; lidR=[by[i]['magnitudeMillimeters'] for i in [386,374]]
        bmax=max(browL+browR); lmax=max(lidL+lidR)
        result[model]={'interocularMillimeters':eye,'leftEyebrow':{'maxMillimeters':max(browL),'medianMillimeters':sum(browL)/3,'normalizedMax':max(browL)/eye},'rightEyebrow':{'maxMillimeters':max(browR),'medianMillimeters':sum(browR)/3,'normalizedMax':max(browR)/eye},'leftEyelid':{'maxMillimeters':max(lidL),'medianMillimeters':sum(lidL)/2,'normalizedMax':max(lidL)/eye},'rightEyelid':{'maxMillimeters':max(lidR),'medianMillimeters':sum(lidR)/2,'normalizedMax':max(lidR)/eye},'eyebrowToEyelidMaxRatio':bmax/max(lmax,1e-12)}
    out.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
