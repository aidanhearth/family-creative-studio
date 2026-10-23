import {createShader,getWebGPUSupport} from 'shaders/js';
export async function paperEffect(canvas) {
  const support=await getWebGPUSupport();
  if(!support.supported)return {state:'unsupported',support,destroy(){}};
  try{
    const instance=await createShader(canvas,{components:[{type:'Circle',id:'light',props:{color:'#d8cbb8',radius:.4}}]},
       {disableTelemetry:true,enablePerformanceTracking:false,isPreview:true});
    return {state:'active',destroy:()=>instance.destroy()};
  }catch(error){return {state:'fallback',reason:String(error),destroy(){}};}
}
