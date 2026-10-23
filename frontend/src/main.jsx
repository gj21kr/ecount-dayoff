import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {CalendarDays, CalendarCheck2, Palmtree, Database, RefreshCw, ChevronLeft, ChevronRight, Clock3, Globe2, Building2, FileText, Video, X, ExternalLink, AlertCircle, CheckCircle2, Search, ArrowUpRight} from 'lucide-react';
import {dayKey, addDays, weekStart, monthStart, shiftMonth, dateLabel, monthLabel, timeText, onDay, dayBlocks, safeLink, sourceLabel} from './calendar';
import {DEFAULT_TEAMS, teamOf, teamName, matchesTeam, leaveGroups} from './teams';
import './style.css';

const today = () => dayKey();
const leaveSource = event => event.sourceType==='ecount'?'eCount 조회':'eCount PDF';
const displayStatus = status => status==='snapshot'?'저장본':sourceLabel(status);
const emptySources = {leave:{status:'configured'}};
const navs = [{id:'calendar',label:'휴가 캘린더',icon:CalendarDays},{id:'leave',label:'휴가 내역',icon:Palmtree},{id:'sources',label:'데이터 연결',icon:Database}];
const weekdays = ['월','화','수','목','금','토','일'];
const stamp = value => value ? `${dayKey(value)} ${timeText(value)}` : '아직 갱신되지 않았습니다';
const eventTitle = e => e.displayTitle || e.title;
const leaveType = e => e.displayLeaveType || e.leaveType || '휴가';
const rangeText = e => e.allDay ? (e.kind==='leave' ? `${leaveType(e)}${e.amount ? ` · ${e.amount}일` : ''}` : '종일') : `${timeText(e.start)}–${timeText(e.end)}`;

function App(){
  const [page,setPage]=useState('calendar');
  const [anchor,setAnchor]=useState(today);
  const [selectedDay,setSelectedDay]=useState(today);
  const [view,setView]=useState('month');
  const [filter,setFilter]=useState('all');
  const [query,setQuery]=useState('');
  const [teamFilter,setTeamFilter]=useState('all');
  const [data,setData]=useState({events:[],sources:emptySources,reviews:[],lastSync:null});
  const [near,setNear]=useState([]);
  const [loading,setLoading]=useState(true);
  const [syncing,setSyncing]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [detail,setDetail]=useState(null);
  const [tick,setTick]=useState(0);
  const scrollRef=useRef(null);
  const dialogRef=useRef(null);
  const start=weekStart(monthStart(anchor));
  const end=addDays(start,42);

  useEffect(()=>{const controller=new AbortController();setLoading(true);setError('');
    const get = async (a,b)=>{const r=await fetch(`/api/dashboard?start=${a}&end=${b}`,{signal:controller.signal});if(!r.ok)throw new Error('일정 데이터를 불러오지 못했습니다. 다시 시도해 주세요.');return r.json();};
    Promise.all([get(start,end),get(today(),addDays(today(),31))]).then(([main,next])=>{setData(main);setNear(next.events);}).catch(e=>{if(e.name!=='AbortError')setError(e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[start,end,tick]);
  useEffect(()=>{const id=setInterval(()=>setTick(n=>n+1),60000);return ()=>clearInterval(id);},[]);
  useEffect(()=>{if(scrollRef.current)scrollRef.current.scrollTop=7*56;},[view,page]);
  useEffect(()=>{if(detail&&dialogRef.current)dialogRef.current.showModal();},[detail]);
  async function sync(){setSyncing(true);setNotice('');setError('');try{const r=await fetch('/api/sync',{method:'POST',headers:{'X-Requested-With':'team-dashboard'}});if(!r.ok)throw new Error('갱신 요청에 실패했습니다. 데이터 연결 상태를 확인해 주세요.');setTick(n=>n+1);setNotice('갱신 확인을 마쳤습니다. 연결별 결과를 확인해 주세요.');}catch(e){setError(e.message);}finally{setSyncing(false);}}
  const visible=data.events.filter(e=>e.kind==='leave'&&matchesTeam(e,teamFilter));
  const teams=data.teams||DEFAULT_TEAMS;
  const monthLeave=data.events.filter(e=>e.kind==='leave'&&dayKey(e.start).slice(0,7)===anchor.slice(0,7)&&matchesTeam(e,teamFilter)&&(!query||`${e.title} ${e.person||''}`.toLowerCase().includes(query.toLowerCase())));
  const groupedLeave=leaveGroups(monthLeave,teams).filter(group=>teamFilter==='all'||group.id===teamFilter);
  const days=Array.from({length:7},(_,i)=>addDays(weekStart(anchor),i));
  const shownCount=visible.filter(e=>view==='month'||days.some(day=>onDay(e,day))).length;
  const todayEvents=near.filter(e=>onDay(e,today()));
  const todayLeave=todayEvents.filter(e=>e.kind==='leave'&&matchesTeam(e,teamFilter));
  const todayMeet=todayEvents.filter(e=>e.kind==='meeting');
  const nextMeeting=near.filter(e=>e.kind==='meeting'&&new Date(e.end)>new Date()).sort((a,b)=>new Date(a.start)-new Date(b.start))[0];
  const selectedEvents=visible.filter(e=>onDay(e,selectedDay)).sort((a,b)=>new Date(a.start)-new Date(b.start));
  const reviews=data.reviews||[];
  function move(n){const next=view==='week'&&page==='calendar'?addDays(anchor,n*7):shiftMonth(anchor,n);setAnchor(next);setSelectedDay(next);}
  function goToday(){setAnchor(today());setSelectedDay(today());}
  const title=navs.find(n=>n.id===page).label;
  const subtitles={calendar:'AI·SW팀의 휴가를 한눈에',leave:'근태일자를 기준으로 확인하는 팀 휴가',sources:'일정이 어디에서, 언제 갱신되는지 확인하세요'};
  const stale=Object.values(data.sources).some(s=>s.status==='error');
  const eventButton=(e,extra={})=><button key={e.id} className={`event ${e.kind} ${e.kind==='leave'?`team-${teamOf(e)}`:''} ${extra.style?.height<40?'compact-event':''}`} onClick={()=>setDetail(e)} title={`${eventTitle(e)} · ${rangeText(e)}${e.timeSlotNote ? ` · ${e.timeSlotNote}` : ''}`} {...extra}><span className="event-time">{rangeText(e)}</span><strong>{e.kind==='leave'&&<span className="event-team-label">{teamName(teamOf(e))} · </span>}{eventTitle(e)}</strong>{e.timeSlotNote&&<small className="slot-note">{e.timeSlotNote}</small>}</button>;
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand">TEAM<span className="brand-dot"/></div><div className="workspace"><Building2 size={18}/><span>AI &amp; SW</span><span className="workspace-mark">워크스페이스</span></div><nav aria-label="주 메뉴">{navs.map(n=><button key={n.id} className={page===n.id?'active':''} onClick={()=>{setPage(n.id);setNotice('');}} aria-current={page===n.id?'page':undefined}><n.icon size={20}/>{n.label}{n.id==='sources'&&reviews.length>0&&<span className="nav-count">{reviews.length}</span>}</button>)}</nav><div className="sidebar-bottom"><span className="local-dot"/>팀 일정 대시보드<div><Globe2 size={15}/>Asia/Seoul · KST</div></div></aside>
    <main>
      <header className="page-header"><div><h1>{title}</h1><p>{subtitles[page]}</p></div><button className="refresh" onClick={sync} disabled={syncing}><RefreshCw size={16} className={syncing?'spin':''}/>{syncing?'갱신 중':'새로고침'}</button></header>
      {(error||stale)&&<div className="banner error" role="alert"><AlertCircle size={18}/><span>{error||'일부 연결의 갱신에 실패했습니다. 마지막으로 저장된 일정이 표시될 수 있습니다.'}</span><button onClick={()=>setPage('sources')}>연결 확인</button></div>}
      {notice&&<div className="banner notice" role="status"><CheckCircle2 size={17}/>{notice}<button aria-label="알림 닫기" onClick={()=>setNotice('')}><X size={15}/></button></div>}
      {page!=='sources'&&<TeamFilter value={teamFilter} onChange={setTeamFilter}/>}
      {page==='calendar'&&<>
        <section className="summary" aria-label="휴가 요약">{[{label:'오늘 휴가 · '+teamName(teamFilter),value:new Set(todayLeave.map(e=>e.person)).size,unit:'명'},{label:'이번 달 휴가 · '+teamName(teamFilter),value:monthLeave.length,unit:'건'},{label:'이번 달 휴가 일수',value:monthLeave.reduce((sum,e)=>sum+(e.amount||0),0),unit:'일'}].map(item=><div className="summary-item" key={item.label}><span className="summary-icon mint"><Palmtree/></span><div><span className="summary-label">{item.label}</span><strong>{loading||error?'—':item.value}<small>{item.unit}</small></strong></div></div>)}</section>
        <div className="calendar-layout"><section className="calendar-panel" aria-label="팀 캘린더"><div className="calendar-toolbar"><div className="date-controls"><h2>{monthLabel(anchor)}</h2><button className="icon-button" aria-label="이전 기간" onClick={()=>move(-1)}><ChevronLeft size={18}/></button><button className="icon-button" aria-label="다음 기간" onClick={()=>move(1)}><ChevronRight size={18}/></button><button onClick={goToday}>오늘</button></div><div className="view-controls"><div className="segmented" aria-label="캘린더 보기"><button aria-pressed={view==='week'} className={view==='week'?'selected':''} onClick={()=>setView('week')}>주간</button><button aria-pressed={view==='month'} className={view==='month'?'selected':''} onClick={()=>setView('month')}>월간</button></div></div></div>
          <div className="calendar-scroll-x" aria-busy={loading}>
          {view==='week'?<div className="week-calendar"><div className="week-head"><div className="axis-head">KST</div>{days.map((day,i)=><button key={day} className={`day-head ${day===today()?'today':''} ${day===selectedDay?'chosen':''} ${i===6?'sunday':''}`} onClick={()=>setSelectedDay(day)}><span>{Number(day.slice(5,7))}.{day.slice(8)}</span><small>{weekdays[i]}</small></button>)}</div><div className="all-day-row"><div className="axis">휴가</div>{days.map(day=><div key={day} className="all-day-cell">{visible.filter(e=>(e.allDay||e.kind==='leave')&&onDay(e,day)).map(e=>eventButton(e))}</div>)}</div><div className="time-scroll" ref={scrollRef}><div className="time-grid"><div className="time-axis">{Array.from({length:24},(_,i)=><span key={i} style={{top:i*56}}>{String(i).padStart(2,'0')}:00</span>)}</div>{days.map(day=><div className={`time-day ${day===today()?'today-column':''}`} key={day}>{dayBlocks(visible.filter(e=>e.kind!=='leave'),day).map(b=>eventButton(b.event,{style:{position:'absolute',top:b.start/60*56,height:Math.max(23,(b.end-b.start)/60*56-3),left:`calc(${b.lane/b.columns*100}% + 3px)`,width:`calc(${100/b.columns}% - 6px)`}}))}</div>)}</div></div></div>:<div className="month-calendar"><div className="month-weekdays">{weekdays.map(d=><span key={d}>{d}</span>)}</div><div className="month-grid">{Array.from({length:42},(_,i)=>addDays(start,i)).map(day=><div key={day} className={`month-cell ${day.slice(0,7)!==anchor.slice(0,7)?'outside':''} ${day===selectedDay?'chosen':''}`}><button className={`month-date ${day===today()?'today':''}`} onClick={()=>setSelectedDay(day)} aria-label={dateLabel(day)}>{Number(day.slice(8))}</button>{visible.filter(e=>onDay(e,day)).slice(0,3).map(e=>eventButton(e))}{visible.filter(e=>onDay(e,day)).length>3&&<button className="more-events" onClick={()=>setSelectedDay(day)}>+{visible.filter(e=>onDay(e,day)).length-3}개 더 보기</button>}</div>)}</div></div>}
          </div><div className="calendar-footer"><span><i className="legend leave"/>AI 휴가 <i className="legend sw"/>SW 휴가</span><span>{loading?'일정 불러오는 중…':`${shownCount}개 일정 · ${view==='week'?'이번 주':'화면에 표시된 기간'}`}<span className="desktop-only"> · 한국 시간 기준</span></span></div>
        </section><aside className="agenda"><h2>{selectedDay===today()?'오늘의 일정':'선택한 날의 일정'}</h2><p className="agenda-date">{dateLabel(selectedDay)}</p><h3><Palmtree size={19} className="green"/>{teamName(teamFilter)} 휴가 <span>{selectedEvents.filter(e=>e.kind==='leave').length}건</span></h3><div className="agenda-list">{selectedEvents.filter(e=>e.kind==='leave').map(e=>eventButton(e))}{!selectedEvents.some(e=>e.kind==='leave')&&<Empty icon={Palmtree} text={loading?'휴가를 불러오는 중입니다':`${teamName(teamFilter)}의 등록된 휴가 데이터가 없습니다`}/>}</div><section className="agenda-sources"><h3><Database size={18}/>데이터 연결</h3><SourceMini label="eCount PDF" source={data.sources.leave} icon={FileText} onClick={()=>setPage('sources')}/>{data.sources.ecount&&<SourceMini label="eCount 조회" source={data.sources.ecount} icon={Database} onClick={()=>setPage('sources')}/>}<div className="sync-note"><Clock3 size={14}/><span>최근 확인 {data.lastSync?timeText(data.lastSync):'—'}</span></div><div className="sync-note"><RefreshCw size={14}/><span>매일 00:00 PDF 휴가 갱신</span></div></section></aside></div>
      </>}
      {page==='leave'&&<section className="content-panel"><div className="section-toolbar"><div className="date-controls"><h2>{monthLabel(anchor)}</h2><button className="icon-button" aria-label="이전 달" onClick={()=>move(-1)}><ChevronLeft size={18}/></button><button className="icon-button" aria-label="다음 달" onClick={()=>move(1)}><ChevronRight size={18}/></button><button onClick={goToday}>이번 달</button></div><label className="search"><Search size={17}/><input placeholder="이름 검색" aria-label="휴가자 이름 검색" value={query} onChange={e=>setQuery(e.target.value)}/></label></div>{query&&!monthLeave.length&&<p className="team-search-empty" role="status">검색 결과가 없습니다</p>}{groupedLeave.map(group=><section className={`leave-group group-${group.id}`} key={group.id} aria-label={`${group.name} 휴가 내역`}><header className="leave-group-header"><div><h3><i className={`team-dot team-dot-${group.id}`}/>{group.name}<span>{group.events.length}건</span></h3><p>{group.members.length?group.members.join(' · '):'팀 정보가 확인되지 않은 사원'}</p></div></header>{group.events.length?<div className="table-scroll"><table><thead><tr><th>팀원</th><th>근태일자</th><th>휴가 유형</th><th>일수</th><th>자료</th></tr></thead><tbody>{group.events.map(e=><tr key={e.id}><td><button className="text-button" onClick={()=>setDetail(e)}>{e.person||e.title}</button></td><td>{dayKey(e.start)}</td><td><span className={`tag team-tag-${group.id}`}>{leaveType(e)}</span>{e.timeSlotNote&&<small className="slot-note">{e.timeSlotNote}</small>}</td><td>{e.amount??'확인 필요'}</td><td>{leaveSource(e)}</td></tr>)}</tbody></table></div>:<p className="group-empty">{query?'검색 조건에 맞는 휴가 데이터가 없습니다.':`이번 달 ${group.name}의 등록된 휴가 데이터가 없습니다.`}</p>}</section>)}<div className="panel-footnote">휴가 날짜는 ‘근태일자’ 기준입니다. 기록이 없는 팀은 휴가가 없다고 확정할 수 없습니다.</div></section>}
      {page==='sources'&&<div className="sources-page"><div className="source-grid"><SourceCard name="eCount PDF" caption="지정 폴더에서 휴가 자동 수집" icon={FileText} source={data.sources.leave}><dl><dt>폴더</dt><dd className="folder-path">관리자가 지정한 PDF 폴더</dd><dt>갱신 시각</dt><dd>매일 00:00 · 한국 시간</dd><dt>확인한 PDF</dt><dd>{data.sources.leave.fileCount??0}개</dd><dt>휴가 일정</dt><dd>{data.sources.leave.eventCount??0}개</dd></dl></SourceCard>{data.sources.ecount&&<SourceCard name="eCount 조회" caption="브라우저 조회 시점의 저장본 · 자동 갱신 미연결" icon={Database} source={data.sources.ecount}><dl><dt>조회 범위</dt><dd>{data.sources.ecount.rangeStart&&data.sources.ecount.rangeEnd?`${data.sources.ecount.rangeStart} ~ ${addDays(data.sources.ecount.rangeEnd,-1)}`:'아직 조회되지 않았습니다'}</dd><dt>저장된 휴가</dt><dd>{data.sources.ecount.eventCount??0}개</dd><dt>갱신 방식</dt><dd>Chrome에서 조회한 결과를 저장 · PDF와 중복 제거</dd></dl></SourceCard>}</div><section className="content-panel review-panel"><div className="section-toolbar"><h2>확인이 필요한 문서</h2><span className="tag">{reviews.length}건</span></div>{reviews.length?reviews.map((r,i)=><div className="review-row" key={i}><AlertCircle size={19}/><div><strong>{r.file||r.filename||r.source||'문서 확인'}</strong><p>{r.reason||r.message||r.error||'문서 내용을 확인해 주세요.'}</p></div></div>):<Empty icon={CheckCircle2} text="현재 확인이 필요한 문서가 없습니다"/>}</section><div className="operating-note"><Clock3 size={20}/><div><strong>자동 갱신은 이 PC와 Docker가 실행 중일 때 동작합니다.</strong><p>잠자기나 종료 중에는 정시에 실행되지 않습니다. 다시 시작하면 최신 자료를 확인합니다. 갱신 버튼으로 언제든 수동 확인할 수 있습니다.</p></div></div></div>}
      <footer className="app-footer">TEAM · AI &amp; SW<span>등록된 AI·SW팀 휴가 기준</span></footer>
    </main>
    {detail&&<dialog ref={dialogRef} onCancel={()=>setDetail(null)} onClick={e=>{if(e.target===e.currentTarget)setDetail(null);}}><div className="modal-header"><span className={`tag ${detail.kind==='leave'?`team-tag-${teamOf(detail)}`:'blue'}`}>{detail.kind==='leave'?`${teamName(teamOf(detail))} · 휴가`:'회의'}</span><button aria-label="상세 닫기" className="icon-button" onClick={()=>setDetail(null)}><X size={20}/></button></div><h2>{eventTitle(detail)}</h2><p className="detail-date">{dateLabel(dayKey(detail.start))}</p><div className="detail-line"><Clock3 size={18}/>{rangeText(detail)}</div>{detail.timeSlotNote&&<p className="slot-note detail-slot-note">{detail.timeSlotNote}</p>}{dayKey(detail.end)!==dayKey(detail.start)&&!detail.allDay&&<p>종료: {dateLabel(dayKey(detail.end))} {timeText(detail.end)}</p>}{detail.person&&<div className="detail-line"><Building2 size={18}/>{detail.person}</div>}{detail.location&&<div className="detail-line"><Video size={18}/>{detail.location}</div>}<div className="detail-line muted"><Database size={18}/>{detail.kind==='leave'?leaveSource(detail):'Outlook Calendar'}</div>{safeLink(detail.url)&&<a className="join-link" href={safeLink(detail.url)} target="_blank" rel="noopener noreferrer">회의 링크 열기<ExternalLink size={16}/></a>}</dialog>}
  </div>;
}
function TeamFilter({value,onChange}){return <section className="team-filter-bar" aria-label="휴가 팀 필터"><div className="team-filter-options"><span>휴가 그룹</span>{['all','AI','SW','unassigned'].map(id=><button key={id} aria-pressed={value===id} className={`team-filter-button ${value===id?'active':''} filter-${id}`} onClick={()=>onChange(id)}>{id!=='all'&&<i className={`team-dot team-dot-${id}`}/>} {teamName(id)}</button>)}</div><p>선택한 팀의 휴가만 표시합니다</p></section>;}
function Empty({icon:Icon,text}){return <div className="empty"><Icon size={28}/><p>{text}</p></div>;}
function SourceMini({label,source={},icon:Icon,onClick}){return <button className="source-mini" onClick={onClick}><Icon size={23}/><span><strong>{label}</strong><small>{source.status==='snapshot'?`저장본 · ${stamp(source.lastSuccess)}`:displayStatus(source.status)}</small></span><i className={`status-dot ${source.status}`}/><ChevronRight size={15}/></button>;}
function SourceCard({name,caption,icon:Icon,source={},children}){return <section className="content-panel source-card"><div className="source-card-header"><span className="summary-icon blue"><Icon size={23}/></span><div><h2>{name}</h2><p>{caption}</p></div><span className={`status-tag ${source.status}`}><i className={`status-dot ${source.status}`}/>{displayStatus(source.status)}</span></div>{children}<div className="last-success"><CheckCircle2 size={16}/><span>마지막 성공 · {stamp(source.lastSuccess)}</span></div>{source.error&&<div className="source-error"><AlertCircle size={17}/>{source.error}</div>}</section>;}
createRoot(document.getElementById('root')).render(<App/>);
