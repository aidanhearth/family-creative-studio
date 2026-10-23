import {createShader,getWebGPUSupport} from 'shaders/js';

export const defaultEffect={enabled:false,type:'Circle',color:'#d8cbb8',secondary:'#F6F4EF',radius:.4,softness:.1,angle:0,opacity:.35};

// The same entry is bundled into the editor and the portable viewer export.
export async function paperEffect(canvas,settings={}) {
 const config={...defaultEffect,...settings};
 canvas.style.opacity=String(config.opacity);
 if(!config.enabled){canvas.style.background='none';return {state:'disabled',destroy(){}};}
 const staticBackground=config.type==='LinearGradient'
  ?`linear-gradient(${config.angle}deg,${config.color},${config.secondary})`
  :`radial-gradient(circle at center,${config.color} 0%,transparent ${Math.min(100,config.radius*100)}%)`;
 canvas.style.background=staticBackground;
 let support;
 try{support=await getWebGPUSupport();}catch(error){return {state:'fallback',reason:String(error),destroy(){canvas.style.background='none';}};}
 if(!support.supported)return {state:'unsupported',support,destroy(){canvas.style.background='none';}};
 try{
  const props=config.type==='LinearGradient'
   ?{colorA:config.color,colorB:config.secondary,angle:config.angle,start:{x:0,y:.5},end:{x:1,y:.5}}
   :{color:config.color,radius:config.radius,softness:config.softness};
  const instance=await createShader(canvas,{components:[{type:config.type,id:'studio-light',props}]},{disableTelemetry:true,enablePerformanceTracking:false,isPreview:true});
  canvas.style.background='none';
  return {state:'active',destroy(){instance.destroy();canvas.style.background='none';}};
 }catch(error){return {state:'fallback',reason:String(error),destroy(){canvas.style.background='none';}};}
}
if(typeof window!=='undefined')window.mountStudioEffect=paperEffect;
