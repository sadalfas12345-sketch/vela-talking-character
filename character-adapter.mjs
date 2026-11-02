const MORPH_ALIASES = new Map();

function register(target, ...names) {
  for (const name of [target, ...names]) MORPH_ALIASES.set(normalize(name), target);
}
function normalize(name) {
  return String(name).toLowerCase().replace(/^mixamorig[:_]?/, '').replace(/[^a-z0-9]/g, '');
}

const faceTargets = [
  ['jawOpen', 'jawopen'], ['mouthClose', 'mouthclose'], ['mouthFunnel', 'mouthfunnel'], ['mouthPucker', 'mouthpucker'],
  ['mouthSmileLeft', 'mouthsmileleft'], ['mouthSmileRight', 'mouthsmileright'], ['mouthFrownLeft', 'mouthfrownleft'], ['mouthFrownRight', 'mouthfrownright'],
  ['browInnerUp', 'browinnerup'], ['browDownLeft', 'browdownleft'], ['browDownRight', 'browdownright'],
  ['eyeBlinkLeft', 'eyeblinkleft'], ['eyeBlinkRight', 'eyeblinkright'], ['eyeLookUpLeft', 'eyelookupleft'], ['eyeLookUpRight', 'eyelookupright'],
  ['eyeLookDownLeft', 'eyelookdownleft'], ['eyeLookDownRight', 'eyelookdownright'], ['eyeLookInLeft', 'eyelookinleft'], ['eyeLookOutLeft', 'eyelookoutleft'],
  ['eyeLookInRight', 'eyelookinright'], ['eyeLookOutRight', 'eyelookoutright']
];
for (const [target, alias] of faceTargets) register(target, alias, `arkit_${alias}`, `blendshape_${alias}`, `bs_${alias}`);
register('jawOpen','mouthopen','jaw_open','jaw_opening','mouth_open','jawopenar','arkit_mouth_open','arkit_jaw_open');
register('eyeBlinkLeft','blinkleft','eyeblink_l','eye_blink_l','blink_l');
register('eyeBlinkRight','blinkright','eyeblink_r','eye_blink_r','blink_r');
register('mouthSmileLeft','smileleft','mouth_smile_l','smile_l');
register('mouthSmileRight','smileright','mouth_smile_r','smile_r');

const visemeAliases = {
  sil: ['sil', 'silence', 'viseme_sil', 'visemesil'], PP: ['pp', 'viseme_pp', 'visemepp', 'p_b_m'], FF: ['ff', 'viseme_ff', 'visemeff', 'f_v'],
  TH: ['th', 'viseme_th', 'visemeth'], DD: ['dd', 'viseme_dd', 'visemedd', 't_d'], kk: ['kk', 'viseme_kk', 'visemekk', 'k_g'],
  CH: ['ch', 'viseme_ch', 'visemech', 'sh_ch_j'], SS: ['ss', 'viseme_ss', 'visemess', 's_z'], nn: ['nn', 'viseme_nn', 'visemenn', 'n'],
  RR: ['rr', 'viseme_rr', 'visemerr', 'r'], aa: ['aa', 'viseme_aa', 'visemeaa'], E: ['e', 'viseme_e', 'visemee'], I: ['i', 'viseme_i', 'visemei'],
  O: ['o', 'viseme_o', 'visemeo'], U: ['u', 'viseme_u', 'visemeu']
};
for (const [target, aliases] of Object.entries(visemeAliases)) register(`viseme_${target}`, ...aliases);

const BONE_ALIASES = {
  Hips: ['hips', 'pelvis', 'j_bip_c_hips'], Spine: ['spine', 'spine1', 'j_bip_c_spine'], Spine1: ['spine1', 'spine2', 'j_bip_c_spine1'],
  Spine2: ['spine2', 'spine3', 'chest', 'j_bip_c_spine2'], Neck: ['neck', 'j_bip_c_neck'], Head: ['head', 'j_bip_c_head'],
  LeftShoulder: ['leftshoulder', 'shoulder_l', 'j_bip_l_shoulder'], RightShoulder: ['rightshoulder', 'shoulder_r', 'j_bip_r_shoulder'],
  LeftArm: ['leftarm', 'leftupperarm', 'upperarm_l', 'j_bip_l_upperarm'], RightArm: ['rightarm', 'rightupperarm', 'upperarm_r', 'j_bip_r_upperarm'],
  LeftForeArm: ['leftforearm', 'leftlowerarm', 'lowerarm_l', 'j_bip_l_lowerarm'], RightForeArm: ['rightforearm', 'rightlowerarm', 'lowerarm_r', 'j_bip_r_lowerarm'],
  LeftHand: ['lefthand', 'hand_l', 'j_bip_l_hand'], RightHand: ['righthand', 'hand_r', 'j_bip_r_hand'],
  LeftUpLeg: ['leftupleg', 'leftthigh', 'thigh_l', 'j_bip_l_upperleg'], RightUpLeg: ['rightupleg', 'rightthigh', 'thigh_r', 'j_bip_r_upperleg'],
  LeftLeg: ['leftleg', 'leftcalf', 'calf_l', 'j_bip_l_lowerleg'], RightLeg: ['rightleg', 'rightcalf', 'calf_r', 'j_bip_r_lowerleg'],
  LeftFoot: ['leftfoot', 'foot_l', 'j_bip_l_foot'], RightFoot: ['rightfoot', 'foot_r', 'j_bip_r_foot'],
  LeftToeBase: ['lefttoebase', 'lefttoe', 'toes_l', 'j_bip_l_toes'], RightToeBase: ['righttoebase', 'righttoe', 'toes_r', 'j_bip_r_toes'],
  LeftEye: ['lefteye', 'eye_l', 'j_bip_l_eye'], RightEye: ['righteye', 'eye_r', 'j_bip_r_eye']
};
const REQUIRED_BONES = ['Hips','Spine','Spine1','Spine2','Neck','Head','LeftShoulder','RightShoulder','LeftArm','RightArm','LeftForeArm','RightForeArm','LeftHand','RightHand','LeftUpLeg','RightUpLeg','LeftLeg','RightLeg','LeftFoot','RightFoot','LeftToeBase','RightToeBase'];
for (const side of ['Left','Right']) for (const digit of ['HandThumb','HandIndex','HandMiddle','HandRing','HandPinky']) for (let segment=1;segment<=3;segment++) {
  const canonical=`${side}${digit}${segment}`;
  BONE_ALIASES[canonical]=[canonical.toLowerCase(),`${side==='Left'?'l':'r'}_${digit.slice(4).toLowerCase()}_${segment}`,`j_bip_${side==='Left'?'l':'r'}_${digit.slice(4).toLowerCase()}${segment}`];
  REQUIRED_BONES.push(canonical);
}
const findBoneAlias = new Map();
for (const [canonical, aliases] of Object.entries(BONE_ALIASES)) {
  for (const alias of [canonical, ...aliases]) findBoneAlias.set(normalize(alias), canonical);
}

export function inspectCharacter(gltf) {
  const report = { meshes:0, skinnedMeshes:0, materials:new Set(), textures:new Set(), morphTargets:[], bones:new Set(), morphMeshes:0 };
  gltf.scene.traverse(object => {
    if (object.isMesh) {
      report.meshes++;
      for (const mat of (Array.isArray(object.material) ? object.material : [object.material])) {
        if (!mat) continue;
        report.materials.add(mat.name || mat.type);
        for (const key of ['map','normalMap','roughnessMap','metalnessMap','emissiveMap','aoMap']) if (mat[key]) report.textures.add(mat[key].uuid);
      }
      const dict = object.morphTargetDictionary;
      if (dict && Object.keys(dict).length) { report.morphMeshes++; report.morphTargets.push(...Object.keys(dict)); }
    }
    if (object.isSkinnedMesh && object.skeleton) {
      report.skinnedMeshes++;
      for (const bone of object.skeleton.bones) report.bones.add(bone.name);
    }
    if (object.isBone) report.bones.add(object.name);
  });
  report.morphTargets = [...new Set(report.morphTargets)];
  report.materials = [...report.materials]; report.textures = [...report.textures]; report.bones = [...report.bones];
  const targets = new Set(report.morphTargets.map(name => MORPH_ALIASES.get(normalize(name))).filter(Boolean));
  const visemes = ['sil','PP','FF','TH','DD','kk','CH','SS','nn','RR','aa','E','I','O','U'].filter(name => targets.has(`viseme_${name}`));
  const expressionTargets = ['mouthSmileLeft','mouthSmileRight','mouthFrownLeft','mouthFrownRight','browInnerUp','browDownLeft','browDownRight'].filter(name => targets.has(name));
  const blinks = ['eyeBlinkLeft','eyeBlinkRight'].filter(name => targets.has(name));
  const recognizedNames = new Map();
  for (const source of report.morphTargets) {
    const target = MORPH_ALIASES.get(normalize(source));
    if (target && !recognizedNames.has(target)) recognizedNames.set(target, source);
  }
  const canonicalBones = new Set(report.bones.map(name => findBoneAlias.get(normalize(name))).filter(Boolean));
  const missingBones = REQUIRED_BONES.filter(name => !canonicalBones.has(name));
  return {
    ...report,
    facialMorphCount: targets.size,
    visemes,
    missingVisemes: ['sil','PP','FF','TH','DD','kk','CH','SS','nn','RR','aa','E','I','O','U'].filter(name => !visemes.includes(name)),
    blinks,
    expressions: expressionTargets,
    missingBones,
    hasFaceMorphs: targets.has('jawOpen') || visemes.length >= 4,
    hasTalkReadyVisemes: visemes.length >= 4,
    hasBothBlinks: blinks.length === 2,
    skeletonCompatible: missingBones.length === 0,
    importable: report.morphMeshes > 0 && visemes.length >= 4 && missingBones.length === 0,
    mappings: Object.fromEntries(recognizedNames)
  };
}

export function adaptCharacterGLTF(gltf, report) {
  if (!report.importable) throw new Error(compatibilityMessage(report));
  gltf.scene.traverse(object => {
    if (object.isBone) {
      const normalized = normalize(object.name);
      const canonical = findBoneAlias.get(normalized);
      if (canonical) object.name = canonical;
      else object.name = object.name.replace(/^mixamorig[:_]?/i, '');
    }
    if (object.morphTargetDictionary) {
      for (const [sourceName, index] of Object.entries(object.morphTargetDictionary)) {
        const targetName = MORPH_ALIASES.get(normalize(sourceName));
        if (targetName && object.morphTargetDictionary[targetName] === undefined) object.morphTargetDictionary[targetName] = index;
      }
      // TalkingHead expects recognized facial targets in each morph mesh.
      if (object.morphTargetInfluences) {
        for (const [targetName, index] of Object.entries(object.morphTargetDictionary)) object.morphTargetInfluences[index] ??= 0;
      }
    }
  });
  return gltf;
}

export function compatibilityMessage(report) {
  const reasons = [];
  if (!report.morphMeshes) reasons.push('No facial morph targets were found.');
  else if (!report.hasTalkReadyVisemes) reasons.push(`Facial morphs exist, but only ${report.visemes.length} of 15 speech visemes were recognized; at least four are required for activation.`);
  if (report.missingBones?.length) reasons.push(`Missing TalkingHead humanoid bones: ${report.missingBones.join(', ')}.`);
  if (!report.hasBothBlinks) reasons.push(`Blink morphs found: ${report.blinks?.join(', ') || 'none'}. Eye blinking cannot be guaranteed.`);
  if (report.missingVisemes?.length) reasons.push(`Missing speech visemes: ${report.missingVisemes.join(', ')}.`);
  if (!report.expressions?.length) reasons.push('No recognized smile/frown/brow morphs; selector expressions will be limited to rig-supported movement.');
  if (reasons.length === 0) reasons.push('Ready for speech, blinking, and mapped expressions.');
  return reasons.join(' ');
}

export function cacheKey(file) { return `vela-character-adapter:v1:${file.name}:${file.size}:${file.lastModified}`; }
