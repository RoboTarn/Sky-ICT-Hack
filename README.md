# SKY SWARM OPS

เดโม AI Ground Crew Swarm สำหรับจัดทีมภาคพื้นสนามบิน มี **Commander Dashboard** และ **Crew Connect** ใช้สถานะกลางเดียวกัน ดูความเสี่ยง เสนอแผน อนุมัติ ส่ง mission รับงาน เดินทาง และรายงานผลได้ครบวงจร

ข้อมูล crew คุณสมบัติ เที่ยวบิน แผนผัง อุปกรณ์ และเหตุฉุกเฉินทั้งหมดเป็นข้อมูลสมมติ ตัวเลขก่อนและหลังมาจาก simulator ไม่ใช่ผลวัดจากสนามบิน

## ติดตั้งและเปิด

ใช้ Node.js 22.12+ และ Python 3.11+ แนะนำใช้ Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm ci
```

ถ้ายังไม่มี `.env` ให้คัดลอกจาก `.env.example` แล้วตั้งค่า `TYPHOON_API_KEY` ในไฟล์ฝั่ง server โมเดลเริ่มต้นคือ `typhoon-v2.5-30b-a3b-instruct` เปลี่ยนได้ด้วย `TYPHOON_MODEL` ตาม [เอกสาร Typhoon](https://docs.opentyphoon.ai/en/models/) ไฟล์ `.env` และฐานข้อมูลไม่เข้า Git

```powershell
npm run dev
```

- Commander: http://127.0.0.1:5173/commander
- Crew A17: http://127.0.0.1:5173/crew/A17
- API/OpenAPI: http://127.0.0.1:8000/docs

Frontend เปลี่ยนโค้ดแล้วอัปเดตได้ทันที เมื่อแก้ Python ให้หยุดและเปิดคำสั่งใหม่ เพื่อให้การพัฒนาบน Windows ไม่ส่งสัญญาณหยุดไปยังอีก service ฐานข้อมูล `.runtime/swarm.sqlite3` เก็บสถานะและประวัติไว้ เมื่อเปิด server ใหม่เวลาจะหยุดก่อนเสมอ ใช้ backend หนึ่ง worker สำหรับเดโมนี้

หากตั้งค่า key ไม่ได้หรือ Typhoon ตอบผิด/timeout ระบบยังเสนอแผนจาก CP-SAT โดยแสดงแหล่งที่มาเป็น **OPTIMIZER** ชัดเจน กด “ลอง AI อีกครั้ง” เมื่อต้องการ retry API

## เดินเดโมเที่ยวบินล่าช้า

1. กด **เริ่มรอบใหม่** เพื่อให้ได้ข้อมูลตั้งต้นเดิม เปิด Commander และ Crew A17 คนละหน้าต่าง
2. กด **จำลองเหตุการณ์ → เที่ยวบินล่าช้า → สร้างเหตุการณ์** ระบบจะร่างแผนอัตโนมัติ ไม่ต้องกดวิเคราะห์
3. TG312 ล่าช้า 18 นาที ทำให้ A08 ติดงานเดิม ระบบคำนวณผลต่อ TG421 และงานถัดไป จากนั้นเสนอสามทางเลือกให้ Typhoon เลือกและอธิบาย
4. แผนแรกจาก optimizer ใช้ A09 + A17 พร้อม BL01 ให้ A21 รับช่วงงาน TG515 ของ A17 ผลจำลองลดงานเกิน deadline จาก 3 เหลือ 1 งาน งานล่าช้าที่เหลือคือ TG312
5. Commander เลือกแผนและกด **อนุมัติและส่งทีม** หน้า crew อัปเดตผ่าน SSE
6. A17 รับ mission ก่อน แต่ยังออกเดินทางไม่ได้ เปิด crew A21 จากลิงก์ผู้รับช่วง แล้ว **รับ mission → ออกเดินทาง → +1 นาที** เพื่อยืนยันรับช่วง
7. เปิด A17 และ A09 ให้ทั้งคู่รับงานและออกเดินทาง เดินเวลาจำลองอีก 5 นาที รอทั้งทีมและอุปกรณ์มาถึงแล้วกด **เริ่มทำงาน**
8. ยืนยัน checklist ของทั้งสองคน เดินเวลาจนครบระยะเวลางาน แล้วกด **ยืนยันเสร็จงาน** ทั้งคู่ Incident เปลี่ยนเป็นจัดการแล้วและ timeline อัปเดต

Typhoon อาจแนะนำทางเลือกอื่นที่ผ่านข้อจำกัดแล้ว จึงให้ดูรายชื่อและผู้รับช่วงในแผนที่เลือกจริงเสมอ

## สถานการณ์อื่น

| สถานการณ์ | พฤติกรรม |
|---|---|
| Gate change | TG421 ย้าย B6 → B5 แผนและ route เดิมต้องตรวจใหม่ |
| Crew absence | A08 ไม่พร้อม จัดหาทีมที่มี qualification และไม่ติดงานอื่น |
| GSE failure | BL01 ขัดข้อง เลือก belt loader อื่นที่พร้อมและเดินทางทัน |
| Injury | แยกผู้ประสานงาน ผู้มีคุณสมบัติปฐมพยาบาล และทีม medical พร้อมอุปกรณ์ |
| Smoke/fire | ปิด B3 พักงานในพื้นที่ ย้ายคนออก และให้ทีม fire response เข้าพื้นที่ ส่วนผู้ช่วยทั่วไปไปจุดประสานงานปลอดภัย |
| Scheduled What-if | กำหนดเหตุการณ์ล่วงหน้า 5/10/20 นาที แล้วดูผลใน Forecast ก่อนเหตุการณ์เริ่ม |

เหตุฉุกเฉินใช้รายการหน้าที่จำลองที่กำหนดไว้ ไม่ใช้ข้อความโมเดลเป็นขั้นตอนรักษาหรือดับเพลิง และไม่มีการแจ้งหน่วยงานภายนอก

## โครงสร้างและข้อจำกัดการจัดคน

- `backend/domain.py`: ข้อมูลตั้งต้น 6 gates, 8 flights, 24 crew, 8 GSE
- `backend/engine.py`: สถานะกลาง คำสั่ง mission การส่งต่องาน นาฬิกาจำลอง และ SQLite event log
- `backend/forecast.py`, `backend/routing.py`: คาดการณ์ตามทรัพยากรและลำดับงาน พร้อมเส้นทางที่ไม่ผ่านพื้นที่ปิด
- `backend/optimizer.py`: CP-SAT เลือกทีมที่ครบ skills อายุคุณสมบัติ กะ เวลาเดินทาง จำนวนคนขั้นต่ำ ผู้รับช่วง และอุปกรณ์
- `backend/ai.py`: Typhoon เลือกเฉพาะแผนที่ตรวจแล้ว หากข้อความมีสถิติหรือหน่วยที่ไม่ผ่านการตรวจ ให้ใช้คำอธิบายจาก snapshot พร้อมแสดงที่มา การเลือกแผนยังมาจาก API จริง ส่วนตัวเลข UI มาจาก server
- `src/`: React สอง layout, Fluent UI, Phosphor icons และ self-hosted Thai/Latin fonts
- `tokens.css`: semantic design tokens ชุดเดียวกันสำหรับทั้งสองแอป

การอนุมัติตรวจ revision และข้อจำกัดล่าสุดก่อนจองทรัพยากรพร้อมกัน ถ้าสถานะเปลี่ยน ระบบร่างแผนใหม่อัตโนมัติ งานที่หยุดไม่ได้ต้องจบก่อนออกเดินทาง งานที่ต้องรับช่วงต้องรอผู้แทนมาถึง ครบทีมและอุปกรณ์ก่อนเริ่ม mission ได้

Forecast มอง 10/20/30 นาที ใช้เวลาเริ่ม/เสร็จและ slack ก่อน deadline ค่า slack ติดลบคือเสี่ยงเกินเวลา ความเสี่ยงนี้เป็นผลจากตารางและสถานการณ์ที่กำหนด ไม่ใช่โมเดลทำนายว่าจะเกิดอุบัติเหตุ

ตัวเลือก crew ใช้สลับตัวตนสำหรับเดโม ไม่ใช่ระบบ authentication ไม่มีข้อมูลสนามบินจริง GPS หรือระบบแจ้งเหตุจริง

## ทดสอบ

```powershell
npm run test
npm run build
```

ชุด pytest ตรวจ primary recovery, handoff, อายุคุณสมบัติ, minimum staffing, route closure, double reservation, stale plan, refusal/replanning, What-if, persistence, API validation และคำตอบโมเดลที่ผิดรูปแบบ/timeout โดยไม่เรียก API ภายนอกใน unit tests

เปิด `npm run dev` ค้างไว้ แล้วตรวจผ่าน Chrome จริง:

```powershell
npm run test:browser
```

ต้องมี Google Chrome ติดตั้งไว้ การทดสอบนี้เริ่มรอบจำลองใหม่ เดิน workflow ทั้งสองแอป ตรวจ SSE ภายใน 2 วินาที ตรวจ layout 320/375/414/768/1536 px, axe WCAG AA, reduced motion, keyboard และบันทึก screenshots ลง `output/playwright/` หาก server มี key จะเรียก Typhoon จริงหนึ่งครั้งเพื่อสร้างแผน การตรวจ axe ข้ามเฉพาะ focus sentinels ว่างของ Fluent/Tabster ที่ทำหน้าที่ส่ง focus ต่อ โดยยังตรวจทุก element ของแอป

## เปิด production build ในเครื่อง

```powershell
npm run build
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

FastAPI เสิร์ฟ frontend build และ API ใน origin เดียวกัน เปิด `/commander` และ `/crew/A17` ที่พอร์ต 8000 ได้ ใช้โหมด local นี้เป็นค่าเริ่มต้น มี hosted demo บน Vercel และ source พร้อมเอกสารอยู่ที่ [RoboTarn/Sky-ICT-Hack](https://github.com/RoboTarn/Sky-ICT-Hack)

## Hosted demo และ AI อัตโนมัติ

- Commander: https://commander-aigcs-skyhack.robotarn.org
- Crew: https://crew-aigcs-skyhack.robotarn.org
- สำรอง: https://aigcs-skyhack.vercel.app/commander และ `/crew`

สองโดเมนใช้ Vercel project `aigcs-skyhack` และฐานข้อมูลกลาง Neon แผน Free ใน Singapore เดียวกัน Root ของโดเมน Crew เปิดหน้าเลือกตำแหน่งหรือสมาชิกเสมอ ส่วนลิงก์ mission เปิดสมาชิกที่ระบุได้โดยตรง

เมื่อเกิด incident ระบบเรียก CP-SAT และ Typhoon ฝั่ง backend อัตโนมัติ เหตุบาดเจ็บและควัน/ไฟเปิด popup สีแดงพร้อมรายละเอียดและแผน เหตุด้าน operation แสดงในแถบขวา Commander ยังคงต้องอนุมัติทุก mission การรับทราบ popup บันทึกเฉพาะ session ของ browser จึงไม่เปิดซ้ำหลัง refresh แต่เหตุใหม่ยังแจ้งได้

การปฏิเสธ mission หรือรายงานอุปสรรคทำให้ร่างแผนใหม่ แผน stale ถูกตรวจใหม่อัตโนมัติ และ lease ป้องกัน API ซ้ำเมื่อมีหลายหน้าต่าง การลอง AI อีกครั้งยังมีให้เมื่อ API ล้มเหลวหรือไม่พบแผน ไม่วนเรียก provider เมื่อไม่มีทรัพยากร

Local ใช้ SQLite + SSE ตามเดิม Hosted ใช้ Postgres transaction/row lock ป้องกันการจองซ้ำและโหลดสถานะล่าสุดทุกคำสั่ง ไม่ใช้ไฟล์ SQLite ชั่วคราวบน Vercel นาฬิกา hosted เดินตามเวลาจริงที่ผ่านไปเมื่ออ่านสถานะ จึงไม่พึ่ง loop ที่ต้องทำงานต่อหลัง Function จบ หน้าเว็บ hosted poll ทุก 1.2 วินาทีและ refresh เมื่อกลับมาที่หน้า

`DATABASE_URL` และ `TYPHOON_API_KEY` เป็น Vercel server environment เท่านั้น ไฟล์ `.env*`, `.runtime`, `.vercel` ไม่ถูกส่งพร้อม source deployment ตั้ง `DATABASE_URL` ว่างเมื่อต้องการรัน SQLite ในเครื่อง

ตรวจหน้าเลือก crew, popup, keyboard, contrast และ responsive เพิ่มได้ด้วย `npm run test:ui` เมื่อเปิด dev server การทดสอบเริ่มรอบใหม่ ชุด unit tests รวมการร่างแผนอัตโนมัติ, scheduled incident, refusal, stale result, no-plan และหมดอายุ lease

อัปเดต deployment: `npx vercel deploy --prod --yes --scope combine1234s-projects` จากโฟลเดอร์นี้ ต้อง login บัญชีเจ้าของ project ก่อน ไม่จำเป็นต้อง push GitHub
