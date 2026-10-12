import { Button } from '@fluentui/react-components';
import { Clock, ArrowRight } from '@phosphor-icons/react';
import type { Forecast, World } from './types';
import { Status, time, useWorld } from './lib';

export function Comparison({ before, after }: { before: Forecast; after: Forecast }) {
  return <div className="comparison"><div><span>แผนเดิม</span><strong className="negative">{before.lateTasks}<small> งานเกินเวลา</small></strong></div><ArrowRight size={20} /><div><span>หลังจัดทีมใหม่</span><strong className={after.lateTasks < before.lateTasks ? 'positive' : ''}>{after.lateTasks}<small> งานเกินเวลา</small></strong></div><p>คำนวณจากสถานการณ์จำลองเดียวกัน</p></div>;
}
export default function Timeline({ world, full = false }: { world: World; full?: boolean }) {
  const { horizon, setHorizon } = useWorld();
  const rows = world.forecast.rows.filter(r => r.end >= world.now).slice(0, full ? 24 : 6);
  const start = world.now;
  const span = horizon * 60;
  return <section className="panel timeline-panel"><div className="panel-heading"><div><h2><Clock size={18} />Turnaround forecast</h2><p>เห็นผลกระทบก่อนงานหลุด deadline</p></div><div className="segmented" aria-label="ช่วงคาดการณ์">{[10, 20, 30].map(h => <Button key={h} appearance={horizon === h ? 'primary' : 'subtle'} size="small" aria-pressed={horizon === h} onClick={() => setHorizon(h)}>{h} นาที</Button>)}</div></div>
    {!!world.forecast.scheduledIncidents && <div className="what-if-note">What-if รวม {world.forecast.scheduledIncidents} เหตุการณ์ที่กำหนดไว้ล่วงหน้า</div>}
    <div className="timeline-axis"><span>FLIGHT / TASK</span><div>{[0, 1, 2, 3].map(i => <span key={i}>{time(start + span * i / 3)}</span>)}</div><span>SLACK</span></div>
    <div className="timeline-rows">{rows.map(r => {
      const left = Math.max(0, Math.min(98, (r.start - start) / span * 100));
      const width = Math.max(2, Math.min(100 - left, (r.end - Math.max(r.start, start)) / span * 100));
      const deadline = Math.max(0, Math.min(100, (r.deadline - start) / span * 100));
      return <div className="timeline-row" key={r.taskId}><div className="timeline-label"><b>{r.flightId || 'RESPONSE'} <span>{r.zone}</span></b><small>{r.title}</small></div><div className="timeline-track" aria-label={`${r.title}: ${time(r.start)} ถึง ${time(r.end)}, deadline ${time(r.deadline)}`}><div className={`timeline-bar ${r.risk}`} style={{ left: `${left}%`, width: `${width}%` }}><span>{r.crewIds.join(' + ') || 'รอทีม'}</span></div><i className="deadline-mark" style={{ left: `${deadline}%` }} title={`Deadline ${time(r.deadline)}`} /></div><span className={`slack ${r.slack < 0 ? 'negative' : ''}`}>{r.slack < 0 ? '−' : '+'}{Math.round(Math.abs(r.slack) / 60)}m</span></div>;
    })}</div>{!rows.length && <div className="empty-state">งานในช่วงนี้เสร็จแล้ว เลือกช่วงคาดการณ์ที่ยาวขึ้น</div>}
    <div className="timeline-foot"><span><i className="deadline-swatch" />Deadline</span><span>ข้อมูลจำลอง / {rows.length} งานในช่วงที่แสดง</span></div>
    {full && <div className="forecast-detail">{world.forecast.rows.map(r => <div key={r.taskId}><b>{r.title}</b><span>{time(r.start)} → {time(r.end)}</span><Status value={r.risk} /></div>)}</div>}
  </section>;
}
