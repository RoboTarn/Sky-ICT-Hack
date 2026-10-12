import { Badge, Button, Dialog, DialogSurface } from '@fluentui/react-components';
import { Fire, FirstAid, ShieldCheck, Warning, X } from '@phosphor-icons/react';
import type { Incident, World } from './types';
import { time } from './lib';
import { RecoveryPanel } from './RecoveryPanel';

export default function EmergencyAlert({ world, incident, acknowledge, copilot }: { world: World; incident?: Incident; acknowledge: () => void; copilot: () => void }) {
  const affected = world.tasks.filter(t => t.zone === incident?.zone && t.status !== 'completed' && t.priority !== 'critical');
  return <Dialog open={!!incident} onOpenChange={(_,d) => { if (!d.open) acknowledge(); }}><DialogSurface className="emergency-surface" role="alertdialog" aria-labelledby="emergency-title" aria-describedby="emergency-description">
    {incident && <><header className="emergency-header"><span className="emergency-symbol">{incident.type === 'fire' ? <Fire size={32} weight="fill" /> : <FirstAid size={32} weight="fill" />}</span><div><div className="emergency-kicker">EMERGENCY · เหตุการณ์จำลอง</div><h2 id="emergency-title">เกิดเหตุฉุกเฉิน: {incident.label}</h2><p>Gate {incident.zone} · ตรวจพบเวลา {time(incident.scheduledAt)} ICT</p></div><Button appearance="subtle" aria-label="รับทราบและปิดแจ้งเตือน" icon={<X size={22} />} onClick={acknowledge} /></header>
    <div className="emergency-layout"><section className="emergency-brief"><Badge appearance="tint" color="danger">ต้องรับมือทันที</Badge><h3>เกิดอะไรขึ้น</h3><p id="emergency-description">{incident.description}</p><div className="emergency-operational-note"><Warning size={20} /><div><b>{incident.type === 'fire' ? `ปิดพื้นที่ ${incident.zone} แล้ว` : 'จัดทีมตามขอบเขตคุณสมบัติ'}</b><p>{incident.type === 'fire' ? 'งานในพื้นที่ถูกพัก เส้นทางทั่วไปจะหลีกเลี่ยง gate นี้ ทีมตอบสนองที่ได้รับอนุญาตเท่านั้นจึงเข้าพื้นที่ได้' : 'ผู้ช่วยทั่วไปประสานงาน ส่วนปฐมพยาบาลและงานเฉพาะใช้ crew ที่ผ่านคุณสมบัติ'}</p></div></div>
      <h3>งานที่เกี่ยวข้อง</h3>{affected.length ? <ul className="emergency-affected">{affected.map(t => <li key={t.id}><b>{t.flightId || t.id}</b><span>{t.title}</span><small>{t.status === 'suspended' ? 'พักงานแล้ว' : 'เฝ้าระวังผลกระทบ'}</small></li>)}</ul> : <p className="muted">ไม่มีงานเที่ยวบินที่ถูกพักในพื้นที่นี้</p>}
      <div className="scope-note"><ShieldCheck size={21} /><p>AI ร่างแผนอัตโนมัติ ทุก mission รอ commander อนุมัติ ขั้นตอนหน้างานใช้รายการจำลองที่กำหนดไว้</p></div><Button onClick={acknowledge}>รับทราบ · ดูแผนต่อใน Dashboard</Button></section>
      <RecoveryPanel world={world} incident={incident} onOpenCopilot={copilot} emergency />
    </div></>}
  </DialogSurface></Dialog>;
}
