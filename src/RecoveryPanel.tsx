import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Button, Spinner } from '@fluentui/react-components';
import { ArrowClockwise, ArrowRight, ArrowUpRight, CheckCircle, Clock, MapTrifold, ShieldCheck, Sparkle, UsersThree, Warning, X } from '@phosphor-icons/react';
import type { Incident, World } from './types';
import { duration, ErrorBox, Status, time, useCommand } from './lib';
import { crewUrl } from './urls';
import { Comparison } from './Timeline';

export function RecoveryPanel({ world, incident, onOpenCopilot, emergency = false }: { world: World; incident?: Incident; onOpenCopilot: () => void; emergency?: boolean }) {
  const [selected, setSelected] = useState('');
  const { busy, run, error } = useCommand();
  const plans = world.plans.filter(p => p.incidentId === incident?.id && p.status !== 'rejected');
  const plan = plans.find(p => p.id === selected) || plans.find(p => p.recommended) || plans[0];
  const ai = incident?.analysis || world.ai;
  const analyzing = busy === 'analyze' || (incident?.status === 'active' && (!incident.analysis || ai.status === 'analyzing' || ai.status === 'stale'));
  return <section className={`panel recovery-panel ${emergency ? 'emergency-recovery' : ''}`}><div className="panel-heading"><div><h2><Sparkle size={19} />แผนรับมืออัตโนมัติ</h2><p>AI ร่างแผน · commander อนุมัติ</p></div><Badge appearance="outline" color="informative">{analyzing ? 'กำลังคิดแผน' : 'AUTO'}</Badge></div>
    {!incident ? <div className="recovery-empty"><div className="empty-orbit"><ShieldCheck size={35} /></div><h3>พร้อมรับสถานการณ์</h3><p>จำลอง incident เพื่อดูผลกระทบและให้ AI เสนอทีมรับมือ</p><div className="recovery-process"><span>คาดการณ์</span><ArrowRight size={15} /><span>จัดทีม</span><ArrowRight size={15} /><span>อนุมัติ</span></div><div className="standby-note"><CheckCircle size={17} /><span>ตรวจทักษะ งานเดิม และเส้นทางทุกแผน</span></div></div> : <>
      <div className="incident-focus"><div><span className="incident-code">{incident.zone} / {incident.type === 'flight_delay' ? 'TG312 → TG421' : incident.label}</span><Status value={incident.severity} /></div><h3>{incident.label}</h3><p>{incident.description}</p><Status value={incident.status} /></div>
      <ErrorBox message={error} />
      {incident.status === 'scheduled' ? <div className="empty-state"><Clock size={28} /><p>เหตุการณ์เริ่มเวลา {time(incident.scheduledAt)}</p><small>ดูผล What-if ใน Forecast แล้วเดินเวลาถึงเหตุการณ์เพื่อจัดทีม</small></div> : <>
        {analyzing && <div className="auto-analysis" role="status"><Spinner size="tiny" aria-label="กำลังดำเนินการ" /><div><b>ตรวจพบเหตุแล้ว กำลังร่างแผน</b><p>ตรวจทีม งานเดิม อุปกรณ์ และเส้นทางให้ครบก่อนเสนอ</p></div></div>}
        {!analyzing && ['error','no_plan','declined'].includes(ai.status) && <div className="analysis-retry"><ErrorBox message={ai.message} /><Button icon={<ArrowClockwise size={16} />} onClick={() => void run('analyze', '/api/recovery/proposals', { incidentId: incident.id })} disabled={!!busy}>ลอง AI อีกครั้ง</Button></div>}
        {!analyzing && plan && plan.status === 'stale' && <p className="analysis-status" role="status">สถานะเปลี่ยน ระบบกำลังตรวจแผนใหม่อัตโนมัติ</p>}
        {plan && <>
          <div className="plan-options" aria-label="ทางเลือกแผน">{plans.map(p => <button key={p.id} aria-pressed={p.id === plan.id} onClick={() => setSelected(p.id)}>แผน {p.rank}{p.recommended && <span>แนะนำ</span>}</button>)}</div>
          <div className="ai-reason"><div><Sparkle size={15} /><b>{plan.source === 'typhoon' ? 'TYPHOON / LIVE' : 'CP-SAT / OPTIMIZER'}</b></div><p>{plan.rationale}</p>{plan.explanationSource === 'validated_template' && <small>คำอธิบายยืนยันจากข้อมูลกลาง</small>}{world.ai.status === 'error' && <small>Typhoon ไม่พร้อมใช้งาน ลองวิเคราะห์ใหม่ได้</small>}</div>
          <div className="assignment-list">{plan.assignments.map(a => <div className="assignment" key={a.taskId}><div className="assignment-title"><strong>{a.title}</strong><span className="mono">{a.zone}</span></div>{a.members.map(m => <div className="member" key={m.crewId}><div className="member-heading"><span className="crew-avatar small">{m.crewId.slice(1)}</span><div><b>{m.crewId} {m.name}</b><small>{m.role}</small></div><Link to={crewUrl(m.crewId)} target="_blank" rel="noreferrer" className="crew-launch" aria-label={`เปิด mission ของ ${m.crewId}`}><ArrowUpRight size={19} /></Link></div><div className="member-context"><span>งานเดิม</span><p>{m.previousTask}</p>{m.backfill && <div className="handoff"><UsersThree size={15} /><Link to={crewUrl(m.backfill.crewId)} target="_blank" rel="noreferrer">{m.backfill.crewId} รับช่วง</Link><span>ออกเดินทางหลังส่งต่องาน</span></div>}</div><div className="member-stats"><span><MapTrifold size={14} />{m.origin} → {a.zone}</span><span><Clock size={14} />ETA {duration(m.route.seconds)}</span></div><div className="skill-row">{world.tasks.find(t => t.id === a.taskId)?.requiredSkills.map(s => <span key={s}><CheckCircle size={12} />{s}</span>)}</div></div>)}{!!a.gseIds.length && <div className="equipment-assignment"><ShieldCheck size={16} /><span>อุปกรณ์ร่วม: <b>{a.gseIds.join(' + ')}</b></span></div>}</div>)}</div>
          <Comparison before={plan.before} after={plan.after} /><p className="tradeoff">{plan.tradeoffs}</p>
          {plan.status === 'stale' && <ErrorBox message="สถานะเปลี่ยน แผนนี้ต้องวิเคราะห์ใหม่ก่อนส่งงาน" />}
          {plan.status === 'approved' ? <div className="approved-note"><CheckCircle size={18} />ส่ง missions แล้ว เปิดแอป crew เพื่อรับงาน</div> : <div className="approval-actions"><Button appearance="primary" icon={<CheckCircle size={18} />} disabled={!!busy || analyzing || plan.status !== 'proposed'} onClick={() => void run('approve', `/api/recovery/${plan.id}/approve`, {})}>{busy === 'approve' ? 'กำลังส่ง' : 'อนุมัติและส่งทีม'}</Button><Button appearance="subtle" aria-label="ปฏิเสธแผน" icon={<X size={18} />} disabled={!!busy || analyzing || plan.status !== 'proposed'} onClick={() => void run('reject', `/api/recovery/${plan.id}/reject`, {})} /></div>}
          <button className="text-link copilot-link" onClick={onOpenCopilot}><Sparkle size={15} />ถาม Copilot เกี่ยวกับแผนนี้<ArrowRight size={14} /></button>
          {!!incident.rejectedCandidates.length && <details className="candidate-details"><summary>เหตุผลที่ crew อื่นไม่ผ่าน</summary>{incident.rejectedCandidates.filter((c, i, a) => a.findIndex(x => x.crewId === c.crewId && x.reason === c.reason) === i).map(c => <div key={c.crewId + c.taskId + c.reason}><b>{c.crewId}</b><span>{c.reason}</span></div>)}</details>}
        </>}
      </>}
    </>}
  </section>;
}
