import { chromium } from 'playwright';
import { writeFile } from 'node:fs/promises';

const targets=['jawOpen','mouthOpen','viseme_sil','viseme_PP','viseme_FF','viseme_TH','viseme_DD','viseme_kk','viseme_CH','viseme_SS','viseme_nn','viseme_RR','viseme_aa','viseme_E','viseme_I','viseme_O','viseme_U','eyeBlinkLeft','eyeBlinkRight','mouthSmileLeft','mouthFrownLeft','browInnerUp'];
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:1});
try{
  await page.goto(process.env.VELA_URL||'http://127.0.0.1:4174',{waitUntil:'domcontentloaded',timeout:45000});
  await page.waitForFunction(()=>!document.querySelector('#speak')?.disabled,null,{timeout:90000});
  await page.locator('#characterSelect').selectOption('tripo');
  await page.getByText('vela-photoreal-faced.glb:',{exact:false}).waitFor({timeout:90000});
  await page.waitForTimeout(800);
  const activation=await page.evaluate(()=>({selected:document.querySelector('#characterSelect').value,report:document.querySelector('#compatibility').textContent}));
  if(activation.selected!=='tripo')throw new Error('The Tripo character did not activate.');
  const captures=[];
  for(const name of targets){
    const result=await page.evaluate(name=>{
      const h=window.talkingHead,channel=h.mtAvatar[name];
      if(!channel||!channel.ms?.length)return {name,available:false,reason:'TalkingHead has no resolved mesh morph for this channel.'};
      for(const mesh of h.morphs)for(const key of Object.keys(mesh.morphTargetDictionary||{}))mesh.morphTargetInfluences[mesh.morphTargetDictionary[key]]=0;
      channel.ms.forEach((influences,index)=>{influences[channel.is[index]]=1;});
      h.scene.updateMatrixWorld(true);for(const mesh of h.morphs)if(mesh.isSkinnedMesh)mesh.skeleton.update();
      h.renderer.render(h.scene,h.camera);
      return {name,available:true,influence:1,meshCount:channel.ms.length,targetIndices:channel.is.slice()};
    },name);
    if(result.available){
      await page.locator('#avatar canvas').screenshot({path:`assets/tripo/vela-photoreal/verification/morph-${name}.png`});
      captures.push({name,...result,evidence:`assets/tripo/vela-photoreal/verification/morph-${name}.png`});
    }else captures.push(result);
  }
  const report={avatar:'assets/tripo/vela-photoreal/vela-photoreal-faced.glb',method:'Each resolved TalkingHead facial channel was set to influence 1 on every mapped morph mesh, rendered in Chromium, then reset before the next capture.',activation,captures,limitations:['The image grid documents full-influence appearance; it does not certify quantitative mouth aperture, landmark error, anatomical intersections, or speech synchronization.']};
  await writeFile('verification/tripo-viseme-grid.json',JSON.stringify(report,null,2)+'\n','utf8');
  console.log(JSON.stringify({activation,captures:captures.map(({name,available,evidence,reason})=>({name,available,evidence,reason}))},null,2));
  if(captures.some(x=>!x.available))throw new Error('One or more requested facial targets did not resolve to a mesh deformation channel.');
}finally{await browser.close();}
