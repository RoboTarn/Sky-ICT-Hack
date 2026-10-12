import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { Badge, Spinner } from '@fluentui/react-components';
import type { World } from './types';

export async function api<T = unknown>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, body === undefined ? undefined : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'คำขอไม่สำเร็จ กรุณาลองใหม่');
  return data as T;
}
type Store = { world: World | null; error: string; online: boolean; horizon: number; setHorizon: (n: number) => void; refresh: () => Promise<void> };
const WorldContext = createContext<Store | null>(null);
export function WorldProvider({ children }: { children: ReactNode }) {
  const [world, setWorld] = useState<World | null>(null);
  const [error, setError] = useState('');
  const [online, setOnline] = useState(false);
  const [horizon, setHorizon] = useState(30);
  const requestId = useRef(0);
  const inFlight = useRef(false);
  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    const id = ++requestId.current;
    try {
      const snapshot = await api<World>(`/api/state?horizon=${horizon}`);
      if (id === requestId.current) { setWorld(snapshot); setError(''); }
      setOnline(true);
    } catch (e) { if (id === requestId.current) setError(e instanceof Error ? e.message : 'เชื่อมต่อระบบกลางไม่ได้'); setOnline(false); }
    finally { inFlight.current = false; }
  }, [horizon]);
  useEffect(() => {
    void refresh();
    const cloud = location.hostname.endsWith('.robotarn.org') || location.hostname.endsWith('.vercel.app');
    const events = cloud ? null : new EventSource('/api/events');
    if (events) {
      events.onopen = () => { setOnline(true); void refresh(); };
      events.addEventListener('state', () => { void refresh(); });
      events.onerror = () => { setOnline(false); };
    }
    // Serverless streams reconnect; polling keeps both apps current during reconnect.
    const poll = window.setInterval(() => { if (!document.hidden) void refresh(); }, 1200);
    const visible = () => { if (!document.hidden) void refresh(); };
    document.addEventListener('visibilitychange', visible);
    return () => { events?.close(); window.clearInterval(poll); document.removeEventListener('visibilitychange', visible); };
  }, [refresh]);
  return <WorldContext.Provider value={{ world, error, online, horizon, setHorizon, refresh }}>{children}</WorldContext.Provider>;
}
export function useWorld() { const value = useContext(WorldContext); if (!value) throw new Error('Missing WorldProvider'); return value; }
export function useCommand() {
  const { refresh } = useWorld();
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const run = async <T,>(key: string, path: string, body: unknown): Promise<T | undefined> => {
    setBusy(key); setError('');
    try { const result = await api<T>(path, body); await refresh(); return result; }
    catch (e) { setError(e instanceof Error ? e.message : 'ทำรายการไม่สำเร็จ'); }
    finally { setBusy(''); }
  };
  return { busy, error, setError, run };
}
export function time(seconds: number) { const n = 14 * 3600 + 30 * 60 + seconds; return `${String(Math.floor(n / 3600) % 24).padStart(2, '0')}:${String(Math.floor(n / 60) % 60).padStart(2, '0')}`; }
export function duration(seconds: number) { const n = Math.max(0, Math.round(seconds)); return `${Math.floor(n / 60)}m ${String(n % 60).padStart(2, '0')}s`; }
export const finished = (status: string) => ['completed', 'cancelled', 'rejected'].includes(status);
export const statusText: Record<string, string> = { assigned: 'รอรับงาน', accepted: 'รับงานแล้ว', en_route: 'กำลังเดินทาง', arrived: 'ถึงจุดหมาย', in_progress: 'กำลังทำงาน', completed: 'เสร็จแล้ว', rejected: 'ปฏิเสธ', cancelled: 'ยกเลิก', blocked: 'มีอุปสรรค', active: 'รอจัดการ', dispatched: 'ส่งทีมแล้ว', resolved: 'จัดการแล้ว', scheduled: 'กำหนดล่วงหน้า', available: 'พร้อมรับงาน', busy: 'ติดงาน', reserved: 'จอง mission', mission: 'กำลังทำ mission', unavailable: 'ไม่พร้อม', high: 'เสี่ยงสูง', critical: 'ฉุกเฉิน', medium: 'เฝ้าระวัง', low: 'ตามแผน', broken: 'ขัดข้อง', stale: 'ต้องวิเคราะห์ใหม่', suspended: 'พักงาน' };
export function Status({ value }: { value: string }) { const color = ['high', 'critical', 'blocked', 'broken', 'unavailable'].includes(value) ? 'danger' : ['medium', 'busy', 'stale', 'suspended'].includes(value) ? 'warning' : ['low', 'completed', 'resolved', 'available'].includes(value) ? 'success' : 'informative'; return <Badge appearance="tint" color={color}>{statusText[value] ?? value}</Badge>; }
export function Loading({ label = 'กำลังเชื่อมต่อศูนย์ควบคุม' }: { label?: string }) { return <div className="page-loading"><Spinner size="medium" label={label} /></div>; }
export function ErrorBox({ message }: { message: string }) { return message ? <div className="error-box" role="alert">{message}</div> : null; }
