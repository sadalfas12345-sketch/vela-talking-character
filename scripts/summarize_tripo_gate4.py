"""Combine read-only mouth measurements, topology, donor fit, and rendered-pixel evidence."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import label,find_objects
ROOT=Path(__file__).resolve().parents[1]
load=lambda p: json.loads((ROOT/p).read_text(encoding='utf-8'))
ap=load(Path('verification/tripo-mouth-aperture-measurements.json'))
topo=load(Path('verification/tripo-mouth-topology.json'))
bvh=load(Path('verification/tripo-mouth-bvh-overlap.json'))
builder=load(Path('assets/tripo/vela-photoreal/facial-rig-report.json'))
W=ap['neutral']['mouthWidthMeters']; Wpx=ap['neutral']['mouthWidthPixels']
pixel_states={}
for name in ['jawOpen','viseme_PP','viseme_O','viseme_E','viseme_I','viseme_U','viseme_FF']:
 path=ROOT/'assets'/'tripo'/'vela-photoreal'/'verification'/f'aperture-{name}.png'
 image=np.asarray(Image.open(path).convert('RGB'))
 roi=image[810:870,690:800]
 mask=(roi.max(axis=2)<55)
 labels,count=label(mask)
 comps=[]
 for index,slices in enumerate(find_objects(labels),1):
  if slices is None: continue
  region=labels[slices]==index;area=int(region.sum())
  if area<20:continue
  y0,y1=slices[0].start+810,slices[0].stop+810
  x0,x1=slices[1].start+690,slices[1].stop+690
  # Only mouth-centered dark regions; the ROI is around the registered mouth.
  if x1<700 or x0>795 or y1<815 or y0>865:continue
  comps.append({'areaPixels':area,'bboxXYXY':[x0,y0,x1,y1],'widthPixels':x1-x0,'heightPixels':y1-y0})
 if comps:
  y0=min(c['bboxXYXY'][1] for c in comps);y1=max(c['bboxXYXY'][3] for c in comps)
  x0=min(c['bboxXYXY'][0] for c in comps);x1=max(c['bboxXYXY'][2] for c in comps)
  span=y1-y0
 else: x0=y0=x1=y1=span=0
 pixel_states[name]={'threshold':'all RGB channels <55 in fixed mouth ROI [690,810]-[800,870]','darkComponents':comps,'combinedDarkEnvelopeXYXY':[x0,y0,x1,y1],'combinedDarkSpanPixels':span,'combinedDarkSpanRatioToNeutralMouthWidth':span/Wpx if Wpx else None,'evidence':str(path.relative_to(ROOT))}

jaw=ap['measurements']['jawOpen'];pp=ap['measurements']['viseme_PP'];o=ap['measurements']['viseme_O'];e=ap['measurements']['viseme_E']
rig=builder['transferredDentalAnatomy']['VelaTransplantedTeeth']
source_bounds=rig['sourceBoundsMeters']; donor_w=source_bounds['max'][0]-source_bounds['min'][0];donor_h=source_bounds['max'][2]-source_bounds['min'][2]
vert_scale=rig['dentalVerticalScale'];runtime_scale=W/builder['mouthWidthMeters']
# The two higher and two lower disconnected source components overlap in Z.
upper_lo,upper_hi=1.6739,1.7015; lower_lo,lower_hi=1.6529,1.6862
vertical_overlap=max(0,min(upper_hi,lower_hi)-max(upper_lo,lower_lo))
measurements={
 'testedAsset':'assets/tripo/vela-photoreal/vela-photoreal-faced.glb',
 'testedAssetSha256':load(Path('verification/tripo-gate1-integrity.json'))['files'][-1]['sha256'],
 'runtimeMouthWidthMeters':W,'runtimeMouthWidthMillimeters':W*1000,'runtimeMouthWidthPixels':Wpx,
 'registeredBuilderMouthWidthMeters':builder['mouthWidthMeters'],'runtimeToBuilderScaleObserved':runtime_scale,
 'lipAnchorAperture':{
  'neutralMillimeters':ap['neutral']['apertureMeters']*1000,'neutralRatioW':ap['neutral']['apertureRatioW'],
  'jawOpenMillimeters':jaw['apertureMeters']*1000,'jawOpenRatioW':jaw['apertureRatioW'],
  'jawOpenPixelsBetweenRegisteredLipVertices':jaw['aperturePixels'],
  'jawOpenRequiredMillimeters':0.25*W*1000,'jawOpenRequiredPixels':0.25*Wpx,
  'openMinusClosedMillimeters':(jaw['apertureMeters']-pp['apertureMeters'])*1000,
  'openMinusClosedRatioW':jaw['apertureRatioW']-pp['apertureRatioW'],
  'requiredOpenMinusClosedMillimeters':0.22*W*1000,
  'closedPPMillimeters':pp['apertureMeters']*1000,'closedPPRatioW':pp['apertureRatioW'],
 },
 'shapeDimensions':{
  'OWidthRatioToNeutral':o['mouthWidthMeters']/W,'EWidthRatioToNeutral':e['mouthWidthMeters']/W,
  'OToEDifferenceRatioW':(e['mouthWidthMeters']-o['mouthWidthMeters'])/W,
  'leftBlinkClosureFraction':ap['measurements']['eyeBlinkLeft']['eyeClosureFraction'],
  'rightBlinkClosureFraction':ap['measurements']['eyeBlinkRight']['eyeClosureFraction'],
  'leftSmileCornerLiftRatioW':ap['measurements']['mouthSmileLeft']['leftCornerLiftW'],
 },
 'renderedDarkMouthPixelEnvelope':pixel_states,
 'donorMismatch':{
  'donorTeethRawWidthMeters':donor_w,'donorTeethRawHeightMeters':donor_h,'donorWidthToBuilderMouthRatio':donor_w/builder['mouthWidthMeters'],
  'appliedHorizontalScale':rig['mouthWidthScale'],'appliedVerticalScale':vert_scale,
  'fittedTeethHeightBuilderMeters':donor_h*vert_scale,'fittedTeethHeightRatioToBuilderMouth':donor_h*vert_scale/builder['mouthWidthMeters'],
  'estimatedFittedTeethHeightRuntimeMillimeters':donor_h*vert_scale*runtime_scale*1000,
  'sourceUpperLowerComponentZOverlapMeters':vertical_overlap,'fittedRuntimeUpperLowerOverlapMillimeters':vertical_overlap*vert_scale*runtime_scale*1000,
  'overlapRatioToRuntimeMouthWidth':vertical_overlap*vert_scale*runtime_scale/W,
 },
 'faceTopology':topo['files'][0]['nodes'][0],
 'convertedFaceTopology':topo['files'][2]['nodes'][-1],
 'collisionTest':bvh,
 'reviewedFrames':['assets/tripo/vela-photoreal/verification/aperture-jawOpen.png','assets/tripo/vela-photoreal/verification/aperture-viseme_PP.png','assets/tripo/vela-photoreal/verification/aperture-viseme_O.png','assets/tripo/vela-photoreal/verification/aperture-viseme_E.png','assets/tripo/vela-photoreal/verification/aperture-viseme_FF.png'],
 'visualFindings':[
  'The Tripo lips are color painted on the continuous face surface and visibly stretch across the opened seam.',
  'The dark cavity stays visibly open in the closed-lip viseme_PP frame; the mouth reads as a cutout rather than lip contact.',
  'Transferred teeth intersect the shell in the BVH check and protrude through the painted lip contour in rendered frames.',
  'The donor upper and lower dental components overlap in the fitted neutral geometry.'
 ],
 'gate4':'FAIL',
 'gate4FailedChecks':[
  {'metric':'Full-open aperture at jawOpen','actualRatioW':jaw['apertureRatioW'],'thresholdRatioW':0.25,'result':'FAIL'},
  {'metric':'Open-versus-closed aperture difference','actualRatioW':jaw['apertureRatioW']-pp['apertureRatioW'],'thresholdRatioW':0.22,'result':'FAIL'},
  {'metric':'Left blink closure','actualFraction':ap['measurements']['eyeBlinkLeft']['eyeClosureFraction'],'thresholdFraction':0.85,'result':'FAIL'},
  {'metric':'Right blink closure','actualFraction':ap['measurements']['eyeBlinkRight']['eyeClosureFraction'],'thresholdFraction':0.85,'result':'FAIL'},
  {'metric':'Visible unintended mouth surface intersections','actualObserved':True,'threshold':'none visible','supportingBVHTrianglePairs':{state:{'shellTeeth':value['shellTeethIntersectingTrianglePairs'],'shellTongue':value['shellTongueIntersectingTrianglePairs']} for state,value in bvh['states'].items()},'result':'FAIL'}
 ],
 'methodLimitations':['Pixel dark-component envelopes are a visual cavity proxy and are not treated as true lip-contour measurements. The separate lip-vertex projection is the quantitative aperture metric.','BVH counts are intersecting triangle pairs in the measured mouth AABB, not unique intersection curves.']
}
path=ROOT/'verification'/'tripo-gate4-measurements.json';path.write_text(json.dumps(measurements,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in measurements.items() if k not in ['renderedDarkMouthPixelEnvelope','faceTopology','convertedFaceTopology','collisionTest']},indent=2))
