import { AirplaneTilt, Truck, FirstAid, ShieldCheck, ArrowsOutSimple } from '@phosphor-icons/react';
import { Button } from '@fluentui/react-components';
import { useState } from 'react';
import type { Mission, World } from './types';
import { finished } from './lib';

export default function OperationsMap({ world, selectedGate, onGate, mission, previewRoute }: { world: World; selectedGate?: string; onGate?: (id: string) => void; mission?: Mission; previewRoute?: string[] }) {
  const [expanded, setExpanded] = useState(false);
  const points = Object.fromEntries([...world.gates, ...world.nodes].map(n => [n.id, n]));
  const activeRoutes = mission ? [mission] : world.missions.filter(m => !finished(m.status) && m.status !== 'blocked' && m.kind === 'response');
  const line = (nodes: string[]) => nodes.map(id => points[id]).filter(Boolean).map(p => `${p.x},${p.y}`).join(' ');
  const coordinate = (m: Mission) => {
    const origin = points[m.origin];
    if (!origin) return points.HUB;
    if (['arrived', 'in_progress', 'completed'].includes(m.status)) return points[m.zone] || origin;
    if (m.status !== 'en_route' || m.departedAt === undefined) return origin;
    let remaining = Math.max(0, world.now - m.departedAt);
    for (let i = 0; i < m.route.nodes.length - 1; i++) {
      const a = points[m.route.nodes[i]], b = points[m.route.nodes[i + 1]];
      const edge = world.edges.find(e => (e.from === a.id && e.to === b.id) || (e.to === a.id && e.from === b.id));
      const seconds = edge?.seconds || 1;
      if (remaining <= seconds) { const ratio = remaining / seconds; return { x: a.x + (b.x - a.x) * ratio, y: a.y + (b.y - a.y) * ratio }; }
      remaining -= seconds;
    }
    return points[m.zone] || origin;
  };
  let box = '0 0 1000 485';
  if (mission) {
    const locations = mission.route.nodes.map(id => points[id]).filter(Boolean);
    if (locations.length) {
      const xs = locations.map(p => p.x), ys = locations.map(p => p.y);
      const x = Math.max(0, Math.min(...xs) - 100), y = Math.max(0, Math.min(...ys) - 130);
      box = `${x} ${y} ${Math.max(360, Math.max(...xs) - x + 100)} ${Math.max(290, Math.max(...ys) - y + 80)}`;
    }
  }
  return <div className={`map-wrap ${mission ? 'mission-map' : ''}`}>
    <div className="map-topline"><span className="map-context">B CONCOURSE <span>แผนผังจำลอง</span></span><Button appearance="subtle" size="small" icon={<ArrowsOutSimple size={16} />} onClick={() => setExpanded(!expanded)} aria-pressed={expanded}>{expanded ? 'ย่อแผนที่' : 'ขยาย'}</Button></div>
    <div className={`map-scroll ${expanded ? 'expanded' : ''}`}>
      <svg className="airport-map" viewBox={box} role="img" aria-label="แผนผังจำลองสนามบิน แสดง gate ตำแหน่ง crew อุปกรณ์ และเส้นทาง mission">
        <rect x="65" y="43" width="870" height="62" rx="5" className="terminal-building" />
        <text x="500" y="78" textAnchor="middle" className="map-terminal">TERMINAL B</text>
        {world.edges.map((e, i) => <g key={i}><line x1={points[e.from].x} y1={points[e.from].y} x2={points[e.to].x} y2={points[e.to].y} className="apron-road" /><line x1={points[e.from].x} y1={points[e.from].y} x2={points[e.to].x} y2={points[e.to].y} className="road-center" /></g>)}
        <text x="490" y="371" className="map-lane" textAnchor="middle">APRON SERVICE LANE</text>
        {world.gates.map((gate) => {
          const flight = world.flights.filter(f => f.gate === gate.id).sort((a, b) => a.etd - b.etd)[0];
          const risk = world.forecast.rows.some(r => r.zone === gate.id && r.slack < 0);
          const cls = gate.closed ? 'closed' : risk ? 'risk' : 'normal';
          return <g key={gate.id} className={`gate ${cls} ${selectedGate === gate.id ? 'selected' : ''}`} onClick={() => onGate?.(gate.id)}>
            <line x1={gate.x} y1="105" x2={gate.x} y2="133" className="jetbridge" />
            <rect x={gate.x - 45} y="120" width="90" height="28" rx="4" className="gate-label-box" />
            <text x={gate.x} y="139" textAnchor="middle" className="gate-label">{gate.id}</text>
            <rect x={gate.x - 52} y="155" width="104" height="100" rx="8" className="stand-outline" />
            <AirplaneTilt x={gate.x - 30} y="160" width={60} height={60} weight="fill" className="aircraft" />
            <text x={gate.x} y="243" textAnchor="middle" className="flight-label">{gate.closed ? 'AREA CLOSED' : flight?.id || 'AVAILABLE'}</text>
            {risk && !gate.closed && <text x={gate.x} y="278" textAnchor="middle" className="gate-risk-label">SLA RISK</text>}
          </g>;
        })}
        {['HUB', 'MED'].map(id => <g key={id}><rect x={points[id].x - 48} y={points[id].y - 24} width="96" height="50" rx="6" className="station" />{id === 'MED' ? <FirstAid x={points[id].x - 35} y={points[id].y - 9} size={20} /> : <ShieldCheck x={points[id].x - 36} y={points[id].y - 9} size={20} />}<text x={points[id].x + 10} y={points[id].y + 5} textAnchor="middle" className="station-label">{id}</text></g>)}
        {previewRoute && <polyline points={line(previewRoute)} className="preview-route" />}
        {activeRoutes.map(m => <polyline key={m.id} points={line(m.route.nodes)} className={`mission-route ${m.status === 'assigned' ? 'pending' : ''}`} />)}
        {!mission && world.gse.slice(0, 6).map((g, i) => { const p = points[g.zone] || points.HUB; return <g key={g.id} className={`map-gse ${g.status === 'broken' ? 'broken' : ''}`}><Truck x={p.x + 23} y={p.y + 25 + i % 2 * 14} size={20} /><title>{g.id}: {g.label}</title></g>; })}
        {(mission ? world.crew.filter(c => c.id === mission.crewId) : world.crew.filter(c => c.role === 'Ramp agent')).map((c, i) => {
          const m = mission || activeRoutes.find(m => m.crewId === c.id);
          const p = m ? coordinate(m) : points[c.zone] || points.HUB;
          const x = p.x + (m ? 0 : (i % 3 - 1) * 17), y = p.y + (m ? 0 : 54 + Math.floor(i % 6 / 3) * 20);
          return <g key={c.id} className={`crew-marker ${m ? 'on-mission' : c.status}`} transform={`translate(${x} ${y})`}><circle r={m ? 14 : 7} /><text x="0" y={m ? 5 : 23} textAnchor="middle">{c.id}</text><title>{c.name} ({c.role})</title></g>;
        })}
      </svg>
    </div>
    {!mission && <div className="gate-selector" aria-label="เลือก gate">{world.gates.map(g => <button key={g.id} aria-pressed={selectedGate === g.id} className={g.closed ? 'is-closed' : ''} onClick={() => onGate?.(g.id)}>{g.id}<span>{g.closed ? 'ปิดพื้นที่' : world.forecast.rows.some(r => r.zone === g.id && r.slack < 0) ? 'เสี่ยง SLA' : 'ตามแผน'}</span></button>)}</div>}
    <div className="map-legend"><span><i className="legend-dot available" />พร้อมรับงาน</span><span><i className="legend-dot busy" />ติดงาน</span><span><i className="legend-dot on-mission" />Mission</span><span><i className="legend-line" />เส้นทางที่อนุญาต</span></div>
  </div>;
}
