"""A deterministic, explicitly fictional apron and resource dataset."""
from datetime import datetime

SCENARIOS = {
    "flight_delay": {"label": "เที่ยวบินล่าช้า", "description": "TG312 ล่าช้า 18 นาที ทำให้ทีมเดิมติดงาน", "severity": "high"},
    "gate_change": {"label": "เปลี่ยน Gate", "description": "TG421 ย้ายจาก B6 ไป B5 ต้องปรับคนและเส้นทาง", "severity": "medium"},
    "staff_absence": {"label": "Crew ไม่พร้อม", "description": "A08 ไม่พร้อมทำงาน ต้องหาผู้รับช่วง", "severity": "high"},
    "gse_failure": {"label": "อุปกรณ์เสีย", "description": "Belt loader BL01 ขัดข้อง ต้องเปลี่ยนอุปกรณ์", "severity": "high"},
    "injury": {"label": "บาดเจ็บในพื้นที่", "description": "จัดผู้ช่วยประสานงานและทีมปฐมพยาบาลที่มีคุณสมบัติ", "severity": "critical"},
    "fire": {"label": "พบควัน / ไฟ", "description": "ปิดพื้นที่ B3 และจัดทีมตอบสนองเหตุไฟ", "severity": "critical"},
}

def seed():
    gates = [{"id": f"B{i}", "x": 160 + (i - 1) * 137, "y": 190,
              "label": f"Gate B{i}", "closed": False} for i in range(1, 7)]
    nodes = [{"id": "HUB", "x": 92, "y": 400, "label": "Crew hub"},
             {"id": "MED", "x": 885, "y": 400, "label": "Response station"}]
    nodes += [{"id": f"J{i}", "x": g["x"], "y": 328, "label": f"Apron lane {i}"} for i, g in enumerate(gates, 1)]
    edges = [{"from": f"B{i}", "to": f"J{i}", "seconds": 45} for i in range(1, 7)]
    edges += [{"from": f"J{i}", "to": f"J{i+1}", "seconds": 40} for i in range(1, 6)]
    edges += [{"from": "HUB", "to": "J1", "seconds": 70}, {"from": "MED", "to": "J6", "seconds": 60}]
    flights = [
        {"id": "TG312", "destination": "ภูเก็ต", "gate": "B2", "aircraft": "A320", "etd": 1320, "delay": 0},
        {"id": "TG421", "destination": "สิงคโปร์", "gate": "B6", "aircraft": "A320", "etd": 1800, "delay": 0},
        {"id": "TG515", "destination": "เชียงใหม่", "gate": "B4", "aircraft": "A320", "etd": 1980, "delay": 0},
        {"id": "FD338", "destination": "กระบี่", "gate": "B1", "aircraft": "A320", "etd": 1560, "delay": 0},
        {"id": "PG219", "destination": "สมุย", "gate": "B3", "aircraft": "A320", "etd": 1680, "delay": 0},
        {"id": "SL104", "destination": "เชียงราย", "gate": "B5", "aircraft": "B737", "etd": 2100, "delay": 0},
        {"id": "TG608", "destination": "ฮ่องกง", "gate": "B2", "aircraft": "A320", "etd": 2700, "delay": 0},
        {"id": "FD552", "destination": "หาดใหญ่", "gate": "B1", "aircraft": "A320", "etd": 3000, "delay": 0},
    ]
    names = ["ปกรณ์", "นภัส", "ธันวา", "กิตติ", "ชลธิชา", "วีรภัทร", "ณัฐวุฒิ", "ศรัณย์", "รวิศ", "พิมพ์ชนก", "ภาณุ", "อรัญ", "ศุภกร", "ณิชา", "ธีรดนย์", "วรินทร์", "มินตรา", "อชิระ", "พีรวิชญ์", "อัญชิสา", "อาทิตยา", "วรพล", "ณรงค์", "ธนากร"]
    crew = []
    for i in range(1, 25):
        role = "Ramp agent" if i <= 12 or i in (17, 18, 21, 22) else "Cabin service" if i <= 16 else "Medical response" if i <= 20 else "Fire response"
        skills = ["ramp", "baggage", "A320"] if role == "Ramp agent" else ["cabin", "A320"] if role == "Cabin service" else ["medical", "first_aid"] if role == "Medical response" else ["fire_response"]
        if i in (3, 6, 11, 18, 22): skills += ["B737"]
        if i in (17, 21): skills += ["first_aid", "coordination"]
        if i in (1, 2, 9, 12): skills += ["coordination"]
        if role == "Ramp agent" and i not in (3, 6, 8, 9, 17, 18, 22):
            skills = [s for s in skills if s != "baggage"]
        if i in (3, 6): skills.remove("A320")
        zone = "MED" if i in (19, 20, 23, 24) else "B4" if i in (17, 21) else "HUB" if i in (18, 22) else f"B{(i - 1) % 6 + 1}"
        crew.append({"id": f"A{i:02}", "name": names[i-1], "role": role, "skills": skills,
                     "certValidUntil": 28800, "shiftEnd": 9000, "zone": zone,
                     "allowedZones": [g["id"] for g in gates], "status": "available",
                     "workload": 20 + (i * 7) % 49, "currentTaskId": None})
    def task(id, flight, title, zone, start, duration, deadline, skills, staff, equipment=None, interruptible=True, coverage=False, deps=None):
        return {"id": id, "flightId": flight, "title": title, "zone": zone, "earliest": start,
                "duration": duration, "deadline": deadline, "requiredSkills": skills, "minStaff": len(staff),
                "assignedCrew": staff, "gseIds": equipment or [], "gseType": "belt_loader" if equipment else None,
                "status": "in_progress" if start < 0 else "scheduled", "actualStart": start if start < 0 else None,
                "actualEnd": None, "interruptible": interruptible, "requiresCoverage": coverage,
                "dependencies": deps or [], "priority": "normal", "incidentId": None}
    tasks = [
        task("T312", "TG312", "ขนสัมภาระ TG312", "B2", -420, 600, 900, ["baggage", "A320"], ["A08"], ["BL02"], False),
        task("T421", "TG421", "ขนสัมภาระ TG421", "B6", 300, 480, 960, ["baggage", "A320"], ["A08", "A09"], ["BL01"]),
        task("T515", "TG515", "ดูแลจุดขนถ่าย TG515", "B4", -300, 900, 900, ["ramp", "A320"], ["A17"], coverage=True),
        task("T338", "FD338", "เตรียมอุปกรณ์ภาคพื้น", "B1", -180, 660, 840, ["ramp", "A320"], ["A01", "A02"]),
        task("T219", "PG219", "เตรียมเครื่องบิน PG219", "B3", -300, 780, 960, ["ramp", "A320"], ["A04", "A05"], interruptible=False),
        task("T104", "SL104", "ขนสัมภาระ SL104", "B5", 960, 420, 1680, ["baggage", "B737"], ["A03", "A06"]),
        task("T608", "TG608", "เตรียม turnaround TG608", "B2", 1260, 480, 2100, ["ramp", "A320"], ["A10", "A11"]),
        task("T552", "FD552", "เตรียม turnaround FD552", "B1", 1620, 420, 2460, ["ramp", "A320"], ["A12", "A22"]),
        task("C421", "TG421", "เตรียมห้องโดยสาร TG421", "B6", 120, 480, 1080, ["cabin", "A320"], ["A13", "A14"]),
        task("C515", "TG515", "เตรียมห้องโดยสาร TG515", "B4", 180, 480, 1200, ["cabin", "A320"], ["A15", "A16"]),
        task("D421", "TG421", "ตรวจความพร้อมก่อนออก TG421", "B6", 840, 240, 1560, ["ramp", "A320"], ["A07"], deps=["T421", "C421"]),
    ]
    for t in tasks:
        if t["status"] == "in_progress":
            for cid in t["assignedCrew"]:
                c = next(c for c in crew if c["id"] == cid)
                c["zone"], c["currentTaskId"], c["status"] = t["zone"], t["id"], "busy"
    gse = [{"id": id, "type": kind, "label": label, "zone": zone, "status": "available"} for id, kind, label, zone in [
        ("BL01", "belt_loader", "Belt loader 01", "B6"), ("BL02", "belt_loader", "Belt loader 02", "B2"),
        ("BL03", "belt_loader", "Belt loader 03", "B4"), ("TG01", "tug", "Tug 01", "B1"),
        ("TG02", "tug", "Tug 02", "B5"), ("BUS01", "bus", "Apron bus", "HUB"),
        ("MED01", "medical_vehicle", "Medical response vehicle", "MED"), ("FR01", "fire_vehicle", "Fire response vehicle", "MED")]]
    return {"runId": datetime.now().strftime("%Y%m%d%H%M%S%f"), "revision": 1, "now": 0,
            "baseTime": "14:30", "date": "2026-10-12", "playing": False, "speed": 1,
            "gates": gates, "nodes": nodes, "edges": edges, "flights": flights, "crew": crew,
            "tasks": tasks, "gse": gse, "incidents": [], "plans": [], "missions": [],
            "events": [], "ai": {"status": "idle", "source": "optimizer", "message": "ยังไม่มีคำขอวิเคราะห์"}}
