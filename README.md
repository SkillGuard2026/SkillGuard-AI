# SkillGuard AI – SIH 26245 demo (Team YUKTI)
Streamlit + YOLOv8 + SQLite, structured like the reference PPE project.

| Module | File | What it does |
|---|---|---|
| Attendance AI | engines.py `decode_codes / count_people / verify_attendance` | Barcode/QR attendance, AI headcount of classroom, flags PROXY RISK / UNREGISTERED |
| Safety AI | engines.py `ppe_analyse / ppe_video` | YOLOv8 PPE detection (best.pt), compliance %, violation alerts, video timeline |
| Infrastructure AI | engines.py `equipment_check / maintenance_status` | Detects expected equipment, flags missing; maintenance log -> OVERDUE / DUE SOON |

Run: `pip install -r requirements.txt` then `python run.py` (http://localhost:8501).
Put a PPE-trained YOLOv8 `best.pt` (classes like Hardhat, NO-Hardhat, Safety Vest, NO-Safety Vest, Person) beside app.py; otherwise yolov8n.pt is used as a fallback.
Demo tip: register trainees (ID = text in your QR/barcode), mark 3, upload a classroom photo with 6 people -> PROXY RISK alert.
