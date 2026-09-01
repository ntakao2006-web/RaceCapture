export const validChannel=value=>/^[a-z0-9_-]{24,48}$/.test(value||"");
export function validDatabase(value){
  try{const u=new URL(value);return (u.protocol==="https:"&&(u.hostname.endsWith(".firebaseio.com")||u.hostname.endsWith(".firebasedatabase.app")))||(u.protocol==="http:"&&(u.hostname==="localhost"||u.hostname==="127.0.0.1"))}catch{return false}
}
export function streamPoint(event){
  try{const message=JSON.parse(event);return message?.path==="/"&&message?.data?.t&&message?.data?.d?message.data:null}catch{return null}
}
export const dayKey=ms=>new Date(ms).toISOString().slice(0,10).replaceAll("-","");
export function niceGridMeters(target){
  if(!Number.isFinite(target)||target<=0)return NaN;
  const unit=10**Math.floor(Math.log10(target)),candidates=[1,2,5,10].map(x=>x*unit);
  return candidates.reduce((best,x)=>Math.abs(Math.log(x/target))<Math.abs(Math.log(best/target))?x:best);
}
export function formatGridMeters(meters){
  if(!Number.isFinite(meters)||meters<=0)return "--";
  return meters>=1000?`${meters/1000} km`:`${meters} m`;
}
