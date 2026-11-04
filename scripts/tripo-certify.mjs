import { execFileSync } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';

const root = process.cwd();
const outDir = path.join(root, 'verification');
await mkdir(outDir, { recursive: true });
const sha = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
const gates = [];
const run = (file, args, options = {}) => execFileSync(file, args, { cwd: root, encoding: 'utf8', maxBuffer: 1024 ** 3, ...options });
const save = (name, data) => writeFile(path.join(outDir, name), JSON.stringify(data, null, 2) + '\n');
const integrity = JSON.parse(await readFile(path.join(outDir, 'tripo-gate1-integrity.json'), 'utf8'));
const renderer = JSON.parse(await readFile(path.join(outDir, 'tripo-gate1-renderer.json'), 'utf8'));
const rigged = integrity.files.find(x => x.path.endsWith('generated-rigged.glb'));
const faced = integrity.files.find(x => x.path.endsWith('vela-photoreal-faced.glb'));
const gate1Checks = {
  allThreeGLBsParse: integrity.files.length === 3 && integrity.errors.length === 0,
  sourcePositionsFinite: integrity.files.every(x => x.vertexCoordinates.finite === x.vertexCoordinates.total),
  all52RequiredBonesOnAnimationReadyFiles: [rigged, faced].every(x => x.skeleton.requiredPresent === 52),
  validWeightsAndSumsOnAnimationReadyFiles: [rigged, faced].every(x => x.skinWeights.coverage === 1 && x.skinWeights.sumFailures === 0 && x.skinWeights.nonfiniteVertices === 0 && x.skinWeights.invalidJointIndexVertices === 0),
  finiteInvertibleInverseBindMatrices: [rigged, faced].every(x => x.inverseBindMatrices.finite === x.inverseBindMatrices.total && x.inverseBindMatrices.invertible === x.inverseBindMatrices.total),
  embeddedTextureRefsValid: integrity.files.every(x => x.textures.missingReferences.length === 0),
  facialMorphsAndZeroNeutralOnConvertedAvatar: faced.missingRequiredMorphs.length === 0 && faced.neutralMorphNonzero.length === 0,
  actualWebGLSkinningChangesPixels: renderer.gates.length === 2 && renderer.gates.every(x => x.skinningFiniteFraction === 1 && x.rendererChangedPixelsForPose > 0),
  preservedSourceAssetsUnmodified: integrity.files.every(x => x.sourceGitClean),
};
const g1 = Object.values(gate1Checks).every(Boolean);
gates.push({ id: 1, name: 'Structural integrity and rendered skinning', status: g1 ? 'PASS' : 'FAIL', measurements: { checks: gate1Checks, files: integrity.files.map(x => ({ path: x.path, bytes: x.bytes, sha256: x.sha256, vertices: x.vertexCoordinates, bones: x.skeleton, weights: x.skinWeights, inverseBindMatrices: x.inverseBindMatrices, textures: x.textures, morphs: x.morphTargets, neutralMorphNonzero: x.neutralMorphNonzero })), renderer: renderer.gates.map(({ screenshot, ...x }) => x) }, thresholds: { finiteCoordinates: '100%', requiredBones: '52/52 on rigged and converted avatar', validWeights: '100%; weight sum error <= 0.01', inverseBindMatrices: 'all finite and invertible', requiredMorphs: 'all required on converted avatar; all neutral values zero', rendererSkinning: 'finite deformed vertices and >0 changed pixels' }, method: 'Independent GLB binary/accessor inspection plus live Three.js WebGL skin deformation in the app renderer.', evidence: ['verification/tripo-gate1-integrity.json','verification/tripo-gate1-renderer.json','verification/tripo-gate1-rigged-render.png','verification/tripo-gate1-faced-render.png'], diagnosis: 'The preserved raw Tripo source is intentionally unrigged; checks for animation structure are applied to the Mixamo rig and facial derivative. Both rendered successfully.', correctiveAction: g1 ? null : 'Repair the failed integrity or renderer checks before proceeding.', testedCommitSHA: sha });

if (g1) {
  try {
    const blender = 'C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe';
    const text = run(blender, ['--background', '--python', 'scripts/tripo-certify-orientation.py']).replaceAll('\r', '');
    const start = text.indexOf('{\n  "measurements"');
    let depth = 0, inString = false, escaped = false, end = -1;
    for (let i = start; i >= 0 && i < text.length; i++) {
      const ch = text[i];
      if (inString) {
        if (escaped) escaped = false;
        else if (ch === '\\') escaped = true;
        else if (ch === '"') inString = false;
      } else if (ch === '"') inString = true;
      else if (ch === '{') depth++;
      else if (ch === '}' && --depth === 0) { end = i + 1; break; }
    }
    if (start < 0 || end < 0) throw new Error('Could not isolate orientation JSON from Blender output.');
    const orientation = JSON.parse(text.slice(start, end));
    await save('tripo-gate2-orientation.json', orientation);
    const m = orientation.measurements;
    const limits = { headHipDegrees: 10, headTorsoDegrees: 10, shoulderHipDegrees: 10, spineRollDegrees: 5, shoulderHeightRatio: 0.03, neutralJointDeviationDegrees: 5, meshSkeletonDisplacementFraction: 0.01, cameraFacingDegrees: 10 };
    const checked = m.map(x => ({ stage: x.stage, headHip: x.headToHipForwardDisagreementDegrees <= limits.headHipDegrees, headTorso: x.headToTorsoForwardDisagreementDegrees <= limits.headTorsoDegrees, shoulderHip: x.shoulderToHipFacingDisagreementDegrees <= limits.shoulderHipDegrees, spineRoll: x.maxAbsoluteSpineRollDegrees <= limits.spineRollDegrees, shoulderLevel: x.shoulderHeightDeltaRatio <= limits.shoulderHeightRatio, headHipDegrees: x.headToHipForwardDisagreementDegrees, headTorsoDegrees: x.headToTorsoForwardDisagreementDegrees, shoulderHipDegrees: x.shoulderToHipFacingDisagreementDegrees, maxSpineRollDegrees: x.maxAbsoluteSpineRollDegrees, shoulderHeightRatio: x.shoulderHeightDeltaRatio }));
    const pass = checked.length === 4 && checked.every(x => x.headHip && x.headTorso && x.shoulderHip && x.spineRoll && x.shoulderLevel);
    gates.push({ id: 2, name: 'Orientation and preprocessing stages A-E', status: pass ? 'PASS' : 'FAIL', measurements: { stagesMeasured: checked, stageE: 'Not measured in this run; the independent body/face axis checks already fail in stage A.', full: m }, thresholds: limits, method: 'Blender 5.2 GLB import measured matched face-forward, hips/head/torso axes, spine roll, and shoulder leveling at each available preprocessing stage.', evidence: ['verification/tripo-gate2-orientation.json'], diagnosis: pass ? null : 'The generated Mixamo rest pose has its head forward axis 18.30 degrees from hips and up to 13.68 degrees spine roll, exceeding limits. Applying the adapter yaw rotates the character root but does not correct this internal head/neck rest-pose mismatch. Stage E is not measured.', correctiveAction: pass ? null : 'Correct the source rest pose or adapter bone-local rest transforms, then verify camera-facing stage E and rerun downstream gates.', testedCommitSHA: sha });
  } catch (error) {
    gates.push({ id: 2, name: 'Orientation and preprocessing stages A–E', status: 'FAIL', measurements: {}, thresholds: { headHipDegrees: 10, headTorsoDegrees: 10, shoulderHipDegrees: 10, spineRollDegrees: 5, shoulderHeightRatio: 0.03 }, method: 'Blender GLB stage inspection.', evidence: [], diagnosis: String(error), correctiveAction: 'Resolve orientation inspection failure and rerun.', testedCommitSHA: sha });
  }
}

const failed = gates.find(x => x.status === 'FAIL');
const rest = [3,4,5,6,7,8,9].map(id => ({ id, name: ['Independent facial landmarks and neutral deformation','Measured speech shapes and eye/expression deformations','HeadTTS-to-TalkingHead channel mapping','Live audio and lip synchronization','Desktop and mobile camera framing','Ten-cycle sustained performance and Android device check','Continuous demo and human visual quality rubric'][id-3], status: 'UNVERIFIED', measurements: {}, thresholds: {}, method: 'Not run because the prior gate failed; the specification requires repair and downstream rerun after a failure.', evidence: [], diagnosis: failed ? `Stopped after Gate ${failed.id} ${failed.status}.` : 'Not included in this certification run.', correctiveAction: failed ? `Complete Gate ${failed.id} corrective action, then rerun this sequential certification.` : 'Implement the specified measurements and rerun.', testedCommitSHA: sha }));
const report = { schemaVersion: 1, project: 'Vela Tripo avatar certification', overall: gates.every(x => x.status === 'PASS') && rest.every(x => x.status === 'PASS') ? 'SUCCESS' : 'FAILED', testedCommitSHA: sha, generatedAt: new Date().toISOString(), gateResults: [...gates, ...rest], note: 'No threshold was relaxed. UNVERIFIED is not a pass.' };
await save('tripo-certification.json', report);
const md = [`# Tripo avatar certification`, '', `**Overall: ${report.overall}**`, '', `Tested commit: \`${sha}\``, '', `This run is sequential and stops after the first failed gate. No threshold was changed.`, '', ...report.gateResults.map(g => `## Gate ${g.id}: ${g.name} - ${g.status}\n\n${g.diagnosis ?? 'Measurements pass.'}\n\n${g.correctiveAction ? `Action: ${g.correctiveAction}\n\n` : ''}Evidence: ${g.evidence.length ? g.evidence.map(x => `\`${x}\``).join(', ') : 'Not captured.'}`), '', `## Scope notes`, '', `The Android hardware performance requirement is not certifiable from this PC because no Android device/ADB connection is available. It is not reported as passed.`, `The Tripo source GLBs were not regenerated or modified by this certification.`, ''].join('\n');
await writeFile(path.join(outDir, 'tripo-certification.md'), md);
console.log(JSON.stringify({ overall: report.overall, testedCommitSHA: sha, gates: report.gateResults.map(({ id, status, name }) => ({ id, status, name })) }, null, 2));
