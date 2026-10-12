import { useRef, useState } from 'react';
import { Button, Input, Spinner } from '@fluentui/react-components';
import { Sparkle, PaperPlaneTilt, X } from '@phosphor-icons/react';
import { ErrorBox, useCommand } from './lib';

export default function Copilot({ onClose }: { onClose: () => void }) {
  const [question, setQuestion] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const [messages, setMessages] = useState<{ question: string; answer: string; source: string }[]>([]);
  const { run, busy, error } = useCommand();
  async function send(text: string) {
    if (!text.trim() || busy) return;
    setQuestion('');
    input.current?.focus();
    const result = await run<{ answer: string; source: string }>('chat', '/api/copilot/chat', { message: text });
    if (result) setMessages(old => [...old, { question: text, ...result }]);
  }
  return <section className="copilot-panel" aria-label="Typhoon Copilot"><div className="panel-heading"><div><h2><Sparkle size={20} />Typhoon Copilot</h2><p>วิเคราะห์จากสถานะกลางล่าสุด</p></div><Button appearance="subtle" icon={<X size={20} />} aria-label="ปิด Copilot" onClick={onClose} /></div><div className="chat-body">
    {!messages.length && <div className="copilot-welcome"><Sparkle size={30} /><h3>มองแผนให้ครบ ก่อนส่งทีม</h3><p>ถามถึงคนที่เลือก งานเดิม และผลกระทบต่อเที่ยวบินได้ที่นี่</p>{['ทำไมเลือก crew ในแผนนี้?', 'ถ้าไม่ย้ายทีมจะเกิดอะไรขึ้น?', 'คนไหนมีคุณสมบัติช่วยเหตุฉุกเฉินได้?'].map(q => <button key={q} onClick={() => void send(q)} disabled={!!busy}>{q}<PaperPlaneTilt size={15} /></button>)}</div>}
    {messages.map((m, i) => <div className="chat-pair" key={i}><p className="chat-question">{m.question}</p><div className="chat-answer"><small>{m.source === 'typhoon' ? 'TYPHOON / LIVE RESPONSE' : 'OPTIMIZER / API ไม่พร้อม'}</small><p>{m.answer}</p></div></div>)}
    {busy && <Spinner size="small" label="Typhoon กำลังวิเคราะห์ข้อมูลจริงในเดโม" />}<ErrorBox message={error} />
  </div><form className="chat-input" onSubmit={e => { e.preventDefault(); void send(question); }}><label className="sr-only" htmlFor="copilot-question">คำถามถึง Copilot</label><Input ref={input} id="copilot-question" value={question} onChange={(_, d) => setQuestion(d.value)} placeholder="เช่น ทำไม A17 เหมาะกับงานนี้?" maxLength={1200} /><Button type="submit" appearance="primary" icon={<PaperPlaneTilt size={18} />} aria-label="ส่งคำถาม" disabled={!question.trim() || !!busy} /></form><p className="copilot-disclosure">Copilot เสนอและอธิบายแผน การส่งงานต้องผ่าน commander</p></section>;
}
