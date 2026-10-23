export const ZONE = 'Asia/Seoul';
export const dayKey = (value = new Date()) => new Intl.DateTimeFormat('sv-SE', {timeZone: ZONE, year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));
export const dateOf = key => new Date(`${key}T12:00:00+09:00`);
export const addDays = (key,n) => dayKey(new Date(dateOf(key).getTime()+n*86400000));
export const weekStart = key => addDays(key,-((dateOf(key).getUTCDay()+6)%7));
export const monthStart = key => key.slice(0,7)+'-01';
export function shiftMonth(key,n){const d=dateOf(monthStart(key));d.setUTCMonth(d.getUTCMonth()+n);return dayKey(d);}
export const timeText = value => new Intl.DateTimeFormat('ko-KR',{timeZone:ZONE,hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value));
export const dateLabel = key => new Intl.DateTimeFormat('ko-KR',{timeZone:ZONE,month:'long',day:'numeric',weekday:'long'}).format(dateOf(key));
export const monthLabel = key => `${Number(key.slice(0,4))}년 ${Number(key.slice(5,7))}월`;
export const eventDate = event => dayKey(event.start);
export function onDay(event,key){return new Date(event.start).getTime()<new Date(`${addDays(key,1)}T00:00:00+09:00`).getTime()&&new Date(event.end).getTime()>new Date(`${key}T00:00:00+09:00`).getTime();}
export function minuteOnDay(value,key){return (new Date(value)-new Date(`${key}T00:00:00+09:00`))/60000;}
export function dayBlocks(events,key){
  const list=events.filter(e=>!e.allDay&&onDay(e,key)).map(e=>({event:e,start:Math.max(0,minuteOnDay(e.start,key)),end:Math.min(1440,minuteOnDay(e.end,key))})).sort((a,b)=>a.start-b.start||b.end-a.end);
  const groups=[]; let group=[],end=-1;
  for(const item of list){if(item.start>=end&&group.length){groups.push(group);group=[];end=-1;}group.push(item);end=Math.max(end,item.end);}if(group.length)groups.push(group);
  return groups.flatMap(items=>{const lanes=[];for(const item of items){let lane=lanes.findIndex(end=>end<=item.start);if(lane<0)lane=lanes.length;lanes[lane]=item.end;item.lane=lane;}return items.map(item=>({...item,columns:lanes.length}));});
}
export function safeLink(value){try{const u=new URL(value);return ['https:','http:'].includes(u.protocol)?u.href:null;}catch{return null;}}
export const sourceLabel = status => ({ok:'연결됨',empty:'파일 대기',error:'확인 필요',configured:'연결 준비',unconfigured:'미연결',review:'확인 필요'}[status]||'확인 중');
