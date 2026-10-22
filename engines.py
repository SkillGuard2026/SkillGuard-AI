"""AI engines for the 3 SIH 26245 modules: attendance, safety, infrastructure."""
import os, cv2, numpy as np, pandas as pd
from ultralytics import YOLO

_models = {}
def model(path):
    if path not in _models:
        _models[path] = YOLO(path)   # auto-downloads yolov8n.pt if missing
    return _models[path]

# ---------- Module 1: Attendance (barcode/QR + AI headcount) ----------
def decode_codes(img):
    """Return list of trainee IDs found in the image (QR + 1D barcodes)."""
    found = []
    try:
        ok, txt, _, _ = cv2.QRCodeDetector().detectAndDecodeMulti(img)
        if ok: found += [t for t in txt if t]
    except Exception: pass
    try:
        ok, txt, _, _ = cv2.barcode.BarcodeDetector().detectAndDecodeMulti(img)
        if ok: found += [t for t in txt if t]
    except Exception: pass
    return sorted(set(found))

def count_people(img, conf=0.4):
    r = model("yolov8n.pt")(img, classes=[0], conf=conf, verbose=False)[0]
    return len(r.boxes), r.plot()

def verify_attendance(marked, detected, tol=1):
    """Compare software-marked attendance with AI-counted people in class."""
    if marked > detected + tol:
        return "PROXY RISK", f"{marked} marked but only {detected} seen"
    if detected > marked + tol:
        return "UNREGISTERED", f"{detected} seen but only {marked} marked"
    return "OK", "Marked attendance matches classroom headcount"

# ---------- Module 2: Safety (PPE) ----------
def ppe_analyse(img, weights="best.pt", conf=0.5):
    path = weights if os.path.exists(weights) else "yolov8n.pt"
    r = model(path)(img, conf=conf, verbose=False)[0]
    names = r.names; items, viol = {}, 0; persons = 0
    for c in r.boxes.cls.int().tolist():
        n = names[c]; items[n] = items.get(n, 0) + 1
        l = n.lower()
        if l.startswith(("no-", "no_", "no ")): viol += 1
        if l == "person": persons += 1
    persons = persons or max(items.get("Hardhat", 0) + items.get("NO-Hardhat", 0), viol, 1 if items else 0)
    comp = 100.0 if persons == 0 else max(0.0, 100 * (1 - viol / persons))
    return r.plot(), dict(persons=persons, violations=viol, compliance=round(comp, 1), items=items,
                          custom_model=path == weights)

def ppe_video(path, weights, conf, skip, progress=None, cancel=lambda: False):
    cap = cv2.VideoCapture(path); n = int(cap.get(7)) or 1; i = 0; rows = []; last = None
    while cap.isOpened() and not cancel():
        ok, f = cap.read()
        if not ok: break
        if i % skip == 0:
            ann, s = ppe_analyse(f, weights, conf)
            rows.append(dict(frame=i, compliance=s["compliance"], violations=s["violations"]))
            if s["violations"]: last = ann
        i += 1
        if progress: progress(min(i / n, 1.0))
    cap.release()
    return pd.DataFrame(rows), last

# ---------- Module 3: Infrastructure ----------
def equipment_check(img, expected, weights="yolov8n.pt", conf=0.35):
    r = model(weights)(img, conf=conf, verbose=False)[0]
    seen = {r.names[c] for c in r.boxes.cls.int().tolist()}
    missing = [e for e in expected if e not in seen]
    return r.plot(), sorted(seen), missing

def maintenance_status(df):
    """df columns: equipment_id, name, last_service, interval_days -> adds due_date, status."""
    d = df.copy()
    d["last_service"] = pd.to_datetime(d["last_service"])
    d["due_date"] = d["last_service"] + pd.to_timedelta(d["interval_days"], unit="D")
    days = (d["due_date"] - pd.Timestamp.today().normalize()).dt.days
    d["status"] = np.where(days < 0, "OVERDUE", np.where(days <= 7, "DUE SOON", "OK"))
    d["due_date"] = d["due_date"].dt.date
    return d
