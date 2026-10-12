import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Button, Input, Select } from '@fluentui/react-components';
import { AirplaneTilt, ArrowRight, ArrowUpRight, MagnifyingGlass, ShieldCheck, User, UsersThree } from '@phosphor-icons/react';
import { ErrorBox, Loading, Status, useWorld } from './lib';
import { commanderUrl } from './urls';

export default function CrewSelect() {
  const { world, error, refresh } = useWorld();
  const [role, setRole] = useState('all');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState('');
  if (!world) return error ? <div className="connection-error"><ErrorBox message={error} /><Button onClick={() => void refresh()}>ลองเชื่อมต่อใหม่</Button></div> : <Loading />;
  const roles = [...new Set(world.crew.map(c => c.role))];
  const people = world.crew.filter(c => (role === 'all' || c.role === role) && `${c.id} ${c.name} ${c.skills.join(' ')}`.toLowerCase().includes(query.toLowerCase()));
  const person = world.crew.find(c => c.id === selected);
  return <div className="crew-entry"><header className="crew-topbar"><Link to="/crew" className="brand"><span className="brand-symbol"><AirplaneTilt size={24} weight="fill" /></span><span>SKY SWARM<small>CREW CONNECT</small></span></Link><Badge appearance="outline" color="informative">ข้อมูลจำลอง</Badge></header>
    <main className="crew-entry-main"><div className="page-kicker">CREW CONNECT</div><h1>วันนี้คุณอยู่ทีมไหน?</h1><p className="entry-intro">เลือกตำแหน่งหรือสมาชิกทีม เพื่อดูงานปัจจุบันและรับ mission จากศูนย์ควบคุม</p>
      <div className="entry-filters"><label htmlFor="entry-role"><UsersThree size={17} />ตำแหน่ง<Select id="entry-role" value={role} onChange={e => { setRole(e.target.value); setSelected(''); }}><option value="all">ทุกตำแหน่ง</option>{roles.map(r => <option key={r}>{r}</option>)}</Select></label><label htmlFor="entry-search"><MagnifyingGlass size={17} />ค้นหาสมาชิก<Input id="entry-search" value={query} onChange={(_,d) => setQuery(d.value)} placeholder="ชื่อ, A17 หรือทักษะ" /></label></div>
      <div className="entry-results-heading"><h2>สมาชิกทีม</h2><span>{people.length} คน</span></div><div className="entry-crew-list" role="group" aria-label="เลือกสมาชิกทีม">{people.map(c => {
        const task = world.tasks.find(t => t.id === c.currentTaskId);
        const missions = world.missions.filter(m => m.crewId === c.id && !['completed','cancelled','rejected'].includes(m.status)).length;
        return <button className={`entry-person ${selected === c.id ? 'selected' : ''}`} key={c.id} aria-pressed={selected === c.id} onClick={() => setSelected(c.id)}><span className="crew-avatar">{c.id.slice(1)}</span><span className="entry-person-detail"><b>{c.name}<small>{c.id}</small></b><span>{c.role} · {c.zone}</span><small>{task?.title || 'พร้อมรับงานถัดไป'}</small></span><span className="entry-person-status"><Status value={c.status} />{missions > 0 && <small>{missions} mission</small>}</span></button>;
      })}</div>{!people.length && <div className="empty-state"><User size={24} /><p>ไม่พบสมาชิก ลองเปลี่ยนตำแหน่งหรือคำค้น</p><Button onClick={() => { setRole('all'); setQuery(''); }}>แสดงทุกคน</Button></div>}
      <p className="entry-demo-note"><ShieldCheck size={17} />การเลือกตัวตนใช้สำหรับเดโม สมาชิกทุกคนเป็นข้อมูลสมมติ</p><a className="text-link" href={commanderUrl}>เปิด Commander<ArrowUpRight size={15} /></a>
    </main><div className="entry-continue"><div><small>{person ? 'สมาชิกที่เลือก' : 'เลือกสมาชิกเพื่อเริ่ม'}</small><b>{person ? `${person.id} ${person.name}` : 'ยังไม่ได้เลือกทีม'}</b></div>{person ? <Button as="a" href={`/crew/${person.id}`} appearance="primary" icon={<ArrowRight size={18} />}>เข้าสู่ mission</Button> : <Button appearance="primary" disabled>เข้าสู่ mission</Button>}</div>
  </div>;
}
