export const DEFAULT_TEAMS = [
  {id:'AI',name:'AI팀',members:[]},
  {id:'SW',name:'SW팀',members:[]},
];
export const teamOf = event => ['AI','SW'].includes(event.team) ? event.team : 'unassigned';
export const teamName = id => ({all:'전체 팀',AI:'AI팀',SW:'SW팀',unassigned:'미분류'}[id] || '미분류');
export const matchesTeam = (event,id) => event.kind!=='leave' || id==='all' || teamOf(event)===id;
export function leaveGroups(events,teams=DEFAULT_TEAMS){
  const roster=DEFAULT_TEAMS.map(fallback=>teams.find(team=>team.id===fallback.id)||fallback);
  return [...roster,{id:'unassigned',name:'미분류',members:[]}].map(team=>({...team,events:events.filter(event=>event.kind==='leave'&&teamOf(event)===team.id)}));
}
