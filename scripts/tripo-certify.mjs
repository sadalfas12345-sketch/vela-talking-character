import { execFileSync } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const outDir = path.join(root, 'verification');
await mkdir(outDir, { recursive: true });
const sha = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
const run = (file, args) => execFileSync(file, args, { cwd: root, encoding: 'utf8', maxBuffer: 1024 ** 3 });
const save = async (name, data) => writeFile(path.join(outDir, name), JSON.stringify(data, null, 2) + '\n', 'utf8');
const gates = [];
const names = {
  1: 'Source asset integrity', 2: 'Body orientation and skeleton',
  3: 'Facial landmark and morph geometry', 4: 'Speech shape quality',
  5: 'Adapter and animation channels', 6: 'Live speech synchronization',
  7: 'Camera, presentation, and rendering', 8: 'End-to-end stability and performance',
  9: 'Perceptual demo acceptance'
};

const integrity = JSON.parse(run('python', ['scripts/tripo-certify-integrity.py']));
const renderer = JSON.parse(run(process.execPath, ['scripts/verify_tripo_skinning_renderer.mjs']));
await save('tripo-gate1-integrity.json', integrity);
await save('tripo-gate1-renderer.json', renderer);
const raw = integrity.files.find(x => x.path.endsWith('generated-original.glb'));
const rigged = integrity.files.find(x => x.path.endsWith('generated-rigged.glb'));
const faced = integrity.files.find(x => x.path.endsWith('vela-photoreal-faced.glb'));
const gate1Checks = {
  allThreeGLBsParse: integrity.files.length === 3 && integrity.errors.length === 0,
  allVertexCoordinatesFinite: integrity.files.every(x => x.vertexCoordinates.finite === x.vertexCoordinates.total),
  requiredBonesOnRiggedAndFaced: [rigged, faced].every(x => x?.skeleton.requiredPresent === 52),
  completeValidSkinWeights: [rigged, faced].every(x => x?.skinWeights.coverage === 1 && x.skinWeights.sumFailures === 0 && x.skinWeights.nonfiniteVertices === 0 && x.skinWeights.invalidJointIndexVertices === 0),
  inverseBindMatricesFiniteAndInvertible: [rigged, faced].every(x => x?.inverseBindMatrices.finite === x.inverseBindMatrices.total && x.inverseBindMatrices.invertible === x.inverseBindMatrices.total),
  texturesResolve: integrity.files.every(x => x.textures.missingReferences.length === 0),
  requiredFacialTargetsAndNeutralZero: faced?.missingRequiredMorphs.length === 0 && faced.neutralMorphNonzero.length === 0,
  originalAndMixamoSourceUnchanged: raw?.sourceGitClean === true && rigged?.sourceGitClean === true,
  rendererSkinningFiniteAndVisible: renderer.gates.length === 2 && renderer.gates.every(x => x.skinningFiniteFraction === 1 && x.rendererChangedPixelsForPose > 0 && x.neutralMorphNonzero === 0)
};
const gate1Pass = Object.values(gate1Checks).every(Boolean);
gates.push({
  id: 1, name: names[1], status: gate1Pass ? 'PASS' : 'FAIL',
  measurements: { checks: gate1Checks, files: integrity.files.map(({ path, bytes, sha256, vertexCoordinates, skeleton, skinWeights, inverseBindMatrices, textures, missingRequiredMorphs, neutralMorphNonzero, sourceGitClean }) => ({ path, bytes, sha256, vertexCoordinates, skeleton, skinWeights, inverseBindMatrices, textures, missingRequiredMorphs, neutralMorphNonzero, sourceGitClean })), renderer: renderer.gates.map(({ screenshot, ...x }) => x) },
  thresholds: { coordinateFiniteFraction: 1, requiredHumanoidBones: '52/52 on Mixamo and converted files', skinWeightCoverage: 1, maximumWeightSumError: 0.01, inverseBindMatrices: 'all finite and invertible', missingTextures: 0, requiredMorphTargets: 'all required; neutral weights zero', renderedSkinning: 'all finite; nonzero visible pose delta' },
  method: 'Independent GLB accessor, skin-weight, skeleton, inverse-bind, texture, and morph inspection; then real Three.js WebGL skinning in Vela.',
  evidence: ['verification/tripo-gate1-integrity.json', 'verification/tripo-gate1-renderer.json', 'verification/tripo-gate1-rigged-render.png', 'verification/tripo-gate1-faced-render.png'],
  diagnosis: gate1Pass ? 'The raw Tripo GLB and Mixamo GLB are unchanged. The facial GLB is an intentional derived asset and contains the converted rig.' : 'One or more structural or renderer integrity checks failed.',
  correctiveAction: gate1Pass ? null : 'Repair the failed integrity measurement and rerun this gate.', testedCommitSHA: sha
});

if (gate1Pass) {
  run('C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe', ['--background', '--python', 'scripts/tripo-certify-orientation.py']);
  run(process.execPath, ['scripts/verify_tripo_stage_e.mjs']);
  const orientation = JSON.parse(await readFile(path.join(outDir, 'tripo-gate2-orientation.json'), 'utf8'));
  const stageE = JSON.parse(await readFile(path.join(outDir, 'tripo-gate2-stage-e.json'), 'utf8'));
  const m = orientation.measurements;
  const limits = { headHipDegrees: 10, headTorsoDegrees: 10, shoulderHipDegrees: 10, spineRollDegrees: 5, shoulderHeightRatio: 0.03, neutralMajorJointDeviationDegrees: 5, meshToSkeletonDisplacementFraction: 0.01, cameraFacingDegrees: 10, cameraYawDegrees: 10, cameraPitchDegrees: 10, cameraRollDegrees: 2 };
  const stages = m.map(x => ({ stage: x.stage, headHipDegrees: x.headToHipForwardDisagreementDegrees, headTorsoDegrees: x.headToTorsoForwardDisagreementDegrees, shoulderHipDegrees: x.shoulderToHipFacingDisagreementDegrees, maxSpineRollDegrees: x.maxAbsoluteSpineRollDegrees, shoulderHeightRatio: x.shoulderHeightDeltaRatio, maxMajorJointDeviationDegrees: Math.max(...Object.values(x.neutralPoseDeviationDegrees || {}).filter(Number.isFinite)), pass: x.headToHipForwardDisagreementDegrees <= limits.headHipDegrees && x.headToTorsoForwardDisagreementDegrees <= limits.headTorsoDegrees && x.shoulderToHipFacingDisagreementDegrees <= limits.shoulderHipDegrees && x.maxAbsoluteSpineRollDegrees <= limits.spineRollDegrees && x.shoulderHeightDeltaRatio <= limits.shoulderHeightRatio && Math.max(...Object.values(x.neutralPoseDeviationDegrees || {}).filter(Number.isFinite)) <= limits.neutralMajorJointDeviationDegrees }));
  const e = stageE.live;
  const displacement = stageE.meshToSkeleton?.runtimeUnexpected?.maxDisplacementFractionOfHeight;
  const stageEChecks = { activated: stageE.activation?.selected === 'tripo' && stageE.stage === 'E_talkinghead_initialized', browserErrors: stageE.errors.length === 0 && stageE.consoleErrors.length === 0, headHip: e.headToHipDegrees <= limits.headHipDegrees, headTorso: e.headToTorsoDegrees <= limits.headTorsoDegrees, shoulderHip: e.shoulderToHipDegrees <= limits.shoulderHipDegrees, cameraFacing: e.cameraFacingDegrees <= limits.cameraFacingDegrees, cameraYaw: Math.abs(e.cameraYawDegrees) <= limits.cameraYawDegrees, cameraPitch: Math.abs(e.cameraPitchDegrees) <= limits.cameraPitchDegrees, cameraRoll: Math.abs(e.cameraRollDegrees) <= limits.cameraRollDegrees, meshToSkeletonMeasured: Number.isFinite(displacement), meshToSkeletonWithinLimit: Number.isFinite(displacement) ? displacement <= limits.meshToSkeletonDisplacementFraction : null };
  const allMeasuredPass = stages.length === 4 && stages.every(x => x.pass) && Object.values(stageEChecks).every(x => x === true);
  const hasMeasuredFailure = stages.some(x => x.pass === false) || Object.values(stageEChecks).some(x => x === false);
  const gate2Status = hasMeasuredFailure ? 'FAIL' : allMeasuredPass ? 'PASS' : 'UNVERIFIED';
  gates.push({
    id: 2, name: names[2], status: gate2Status,
    measurements: { stagesAtoD: stages, stageE: { checks: stageEChecks, values: e, meshToSkeleton: stageE.meshToSkeleton, mobile: stageE.mobile } },
    thresholds: limits,
    method: 'Matched Blender world-space anatomy measurements at stages A–D, plus actual TalkingHead runtime body axes and camera measurements at stage E using the imported Tripo character.',
    evidence: ['verification/tripo-gate2-orientation.json', 'verification/tripo-gate2-stage-e.json', 'verification/tripo-stage-e-desktop.png', 'verification/tripo-stage-e-mobile.png'],
    diagnosis: gate2Status === 'PASS' ? 'All required body-axis, neutral-pose, root-adjusted mesh-to-skeleton displacement, and runtime camera measurements are within limits. The reported global Hips translation is recorded separately as the expected TalkingHead placement offset.' : hasMeasuredFailure ? 'At least one measured orientation, displacement, or runtime camera check exceeds its threshold.' : 'A required orientation, displacement, or camera measurement is missing.',
    correctiveAction: gate2Status === 'PASS' ? null : hasMeasuredFailure ? 'Correct the failed stage before proceeding.' : 'Repair the missing measurement, then rerun this gate.', testedCommitSHA: sha
  });
}

const prior = gates.find(x => x.status !== 'PASS');
if (!prior && gates.length === 2) gates.push({
  id: 3, name: names[3], status: 'UNVERIFIED',
  measurements: { registeredLandmarkHits: JSON.parse(await readFile(path.join(root, 'assets/tripo/vela-photoreal/face-calibration.json'), 'utf8')).landmarksHit, independentImageFeatureErrorMillimeters: null, neutralDriftMillimeters: null },
  thresholds: { validLandmarkProjections: '>=95%', medianProjectionErrorMillimeters: 2, p95ProjectionErrorMillimeters: 5, outsideMaskDeformationMillimeters: 1, neutralMedianDriftMillimeters: 1, neutralP95DriftMillimeters: 3 },
  method: 'MediaPipe registration points, generated vertex morphs, and the landmark overlay are recorded, but independent image-identified facial landmarks have not been measured against the rendered character.',
  evidence: ['assets/tripo/vela-photoreal/facial-rig-report.json', 'verification/tripo-stage-e-landmark-overlay.png', 'verification/tripo-stage-e-landmark-overlay.json'],
  diagnosis: 'Landmark hits do not establish that each ray landed on the correct visible anatomical feature. Independent feature projection and neutral-drift measurements are missing.',
  correctiveAction: 'Annotate visible eye, lip, brow, and chin features independently on the source render, then compare those measurements to the registered markers and quantify neutral deformation.', testedCommitSHA: sha
});
// Gate 4 is measured independently even while Gate 3's manual landmark survey
// is unverified. The user explicitly requested a measured decision on the
// current mouth; do not hide a known downstream failure behind that survey.
if (gates.some(x => x.id === 3)) {
  try {
    const g4 = JSON.parse(await readFile(path.join(outDir, 'tripo-gate4-measurements.json'), 'utf8'));
    const lip = g4.lipAnchorAperture;
    const shapes = g4.shapeDimensions;
    const collisionStates = Object.entries(g4.collisionTest.states).map(([state, value]) => ({
      state, shellTeethIntersectingTrianglePairs: value.shellTeethIntersectingTrianglePairs,
      shellTongueIntersectingTrianglePairs: value.shellTongueIntersectingTrianglePairs
    }));
    const checks = {
      fullOpenAperture: lip.jawOpenRatioW >= 0.25,
      closedLipAperture: lip.closedPPRatioW <= 0.03,
      openVersusClosedDifference: lip.openMinusClosedRatioW >= 0.22,
      OVersusEDifference: shapes.OToEDifferenceRatioW >= 0.20,
      leftBlinkClosure: shapes.leftBlinkClosureFraction >= 0.85,
      rightBlinkClosure: shapes.rightBlinkClosureFraction >= 0.85,
      smileCornerLift: shapes.leftSmileCornerLiftRatioW >= 0.05,
      noVisibleUnintendedIntersections: !g4.visualFindings.some(x => /protrude through the painted lip contour/i.test(x)),
      noVisibleLipTextureStretch: !g4.visualFindings.some(x => /painted on the continuous face surface and visibly stretch/i.test(x)),
      noPersistentCavityInClosedViseme: !g4.visualFindings.some(x => /stays visibly open in the closed-lip/i.test(x))
    };
    const pass = Object.values(checks).every(Boolean);
    gates.push({
      id: 4, name: names[4], status: pass ? 'PASS' : 'FAIL',
      measurements: { ...g4, checks, collisionStates },
      thresholds: {
        fullOpenApertureRatioW: 0.25, closedLipApertureRatioW: 0.03,
        openVersusClosedDifferenceRatioW: 0.22, roundedOWidthRatio: 0.85,
        wideEWidthRatio: 1.10, OVersusEWidthDifferenceRatioW: 0.20,
        leftBlinkClosureFraction: 0.85, rightBlinkClosureFraction: 0.85,
        smileCornerLiftRatioW: 0.05, unintendedMouthSurfaceIntersections: 'none visible',
        visibleLipTextureStretch: false, persistentCavityInClosedViseme: false
      },
      method: 'Full-influence morphs measured in live Three.js against registered lip and eyelid landmarks; dark mouth pixels recorded separately as a cavity proxy; evaluated Blender BVH overlap tested near the mouth; rendered frames visually inspected.',
      evidence: [...g4.reviewedFrames, 'verification/tripo-mouth-aperture-measurements.json', 'verification/tripo-mouth-topology.json', 'verification/tripo-mouth-bvh-overlap.json'],
      diagnosis: pass ? 'All measured Gate 4 requirements passed.' : 'Full-open lip-anchor aperture is below threshold; texture stretch and persistent cavity appearance remain; both blinks are below threshold; BVH reports oral-mesh intersections with the face shell.',
      correctiveAction: pass ? null : 'Stop tuning this shell and donor fit. Replace the incompatible facial topology with a fitted animation-ready face, then rerun Gates 3 and 4.',
      testedCommitSHA: sha
    });
  } catch (error) {
    gates.push({
      id: 4, name: names[4], status: 'UNVERIFIED', measurements: {},
      thresholds: { fullOpenApertureRatioW: 0.25, closedLipApertureRatioW: 0.03, openVersusClosedDifferenceRatioW: 0.22, leftBlinkClosureFraction: 0.85, rightBlinkClosureFraction: 0.85 },
      method: 'The Gate 4 measurement artifact was not available.', evidence: [],
      diagnosis: `Gate 4 was not measured: ${error.message}`,
      correctiveAction: 'Run the full-influence mouth, pixel, and BVH diagnostics, then rerun certification.',
      testedCommitSHA: sha
    });
  }
}
const stopGate = gates.find(x => x.status === 'FAIL') || gates.find(x => x.status !== 'PASS') || { id: gates.length + 1, status: 'UNVERIFIED' };
for (let id = gates.length + 1; id <= 9; id++) gates.push({
  id, name: names[id], status: 'UNVERIFIED', measurements: {}, thresholds: {},
  method: 'Not executed by this sequential certification run because the preceding gate did not pass.', evidence: [],
  diagnosis: `Stopped after Gate ${stopGate.id} ${stopGate.status}.`,
  correctiveAction: `Complete Gate ${stopGate.id}, then rerun this runner so downstream gates execute in order.`, testedCommitSHA: sha
});

const overall = gates.every(x => x.status === 'PASS') ? 'SUCCESS' : gates.some(x => x.status === 'FAIL') ? 'FAILED' : 'INCOMPLETE';
const report = { schemaVersion: 2, project: 'Vela Tripo avatar certification', overall, testedCommitSHA: sha, generatedAt: new Date().toISOString(), acceptanceThresholdsChanged: false, gateResults: gates };
await save('tripo-certification.json', report);
const md = ['# Tripo avatar certification', '', `**Overall: ${overall}**`, '', `Tested commit: \`${sha}\``, '', 'No acceptance threshold was changed. UNVERIFIED is not a pass.', '', ...gates.map(g => `## Gate ${g.id}: ${g.name} — ${g.status}\n\n${g.diagnosis}\n\n${g.correctiveAction ? `Action: ${g.correctiveAction}\n\n` : ''}Evidence: ${g.evidence.length ? g.evidence.map(x => `\`${x}\``).join(', ') : 'Not captured.'}`), '', '## Scope notes', '', 'Android rendering and performance were not tested on physical Android hardware. The source Tripo and Mixamo GLBs were preserved; the facial derivative is intentional.', ''].join('\n');
await writeFile(path.join(outDir, 'tripo-certification.md'), md, 'utf8');
console.log(JSON.stringify({ overall, testedCommitSHA: sha, gates: gates.map(({ id, status, name }) => ({ id, status, name })) }, null, 2));
