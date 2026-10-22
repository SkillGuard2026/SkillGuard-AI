import tempfile, numpy as np, cv2, pandas as pd, plotly.express as px, streamlit as st
import db, engines as E

st.set_page_config("SkillGuard AI – SIH 26245", "🛡️", layout="wide")
db.init()
st.markdown("<h1 style='margin-bottom:0'>🛡️ SkillGuard AI</h1>"
            "<p style='color:gray'>AI video analytics for skilling centres · SIH 26245 · Team YUKTI</p>",
            unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Settings")
    centre = st.text_input("Centre", "Skilling Centre – Chennai")
    conf = st.slider("Confidence", 0.1, 1.0, 0.5, 0.05)
    weights = st.text_input("PPE weights", "best.pt")
    st.caption("No best.pt? Falls back to yolov8n.pt (person/COCO) so the demo still runs.")

def to_bgr(f):
    return cv2.imdecode(np.frombuffer(f.getvalue(), np.uint8), 1)

tabs = st.tabs(["📊 Dashboard", "🧾 Attendance AI", "🦺 Safety AI", "🏗️ Infrastructure AI"])

# ---------------- Attendance ----------------
with tabs[1]:
    st.subheader("Barcode attendance + AI headcount verification")
    c1, c2 = st.columns(2)
    with c1:
        with st.expander("➕ Register trainee"):
            a, b, c = st.columns(3)
            tid, nm, bt = a.text_input("ID"), b.text_input("Name"), c.text_input("Batch")
            if st.button("Save trainee") and tid:
                db.add_trainee(tid, nm, bt, centre); st.success("Saved")
        st.markdown("**1 · Scan barcode / QR (image) or type ID**")
        up = st.file_uploader("Barcode image", ["jpg", "png", "jpeg"], key="bc")
        manual = st.text_input("Manual ID (demo)")
        if st.button("✅ Mark attendance"):
            ids = E.decode_codes(to_bgr(up)) if up else []
            ids += [manual] if manual else []
            if not ids: st.warning("No code detected")
            for i in ids:
                s, n = db.mark(i, centre)
                {"MARKED": st.success, "DUPLICATE": st.info, "UNKNOWN": st.error}[s](f"{i}: {s} {n or ''}")
    with c2:
        st.markdown("**2 · Classroom photo → AI headcount**")
        room = st.file_uploader("Classroom image", ["jpg", "png", "jpeg"], key="room")
        marked = db.today_marked(centre)
        if room and st.button("🔍 Verify attendance"):
            n, ann = E.count_people(to_bgr(room), conf)
            flag, msg = E.verify_attendance(len(marked), n)
            db.log("ai_checks", centre=centre, scanned=len(marked), detected=n, flag=flag)
            st.image(ann[:, :, ::-1], use_container_width=True)
            m = st.columns(3); m[0].metric("Marked", len(marked)); m[1].metric("AI headcount", n); m[2].metric("Status", flag)
            (st.success if flag == "OK" else st.error)(msg)
    st.markdown("**Today's attendance**"); st.dataframe(marked, use_container_width=True)

# ---------------- Safety ----------------
with tabs[2]:
    st.subheader("Safety equipment presence & compliance")
    mode = st.radio("Input", ["Image", "Video"], horizontal=True)
    if mode == "Image":
        f = st.file_uploader("Workshop image", ["jpg", "png", "jpeg"], key="ppei")
        if f:
            ann, s = E.ppe_analyse(to_bgr(f), weights, conf)
            st.image(ann[:, :, ::-1], use_container_width=True)
            m = st.columns(3); m[0].metric("Persons", s["persons"]); m[1].metric("Violations", s["violations"]); m[2].metric("Compliance", f"{s['compliance']}%")
            if not s["custom_model"]: st.warning("Using fallback model – add best.pt for real PPE classes.")
            if s["violations"]: st.error(f"⚠️ Alert: {s['violations']} missing-PPE violation(s)")
            db.log("safety_events", centre=centre, persons=s["persons"], violations=s["violations"],
                   compliance=s["compliance"], details=str(s["items"]))
    else:
        f = st.file_uploader("Workshop video", ["mp4", "avi", "mov"], key="ppev")
        skip = st.select_slider("Speed (frame skip)", [1, 2, 3, 5, 8], 5)
        if f and st.button("▶️ Process video"):
            t = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4"); t.write(f.read()); t.close()
            bar = st.progress(0.0)
            df, last = E.ppe_video(t.name, weights, conf, skip, bar.progress)
            if not df.empty:
                st.plotly_chart(px.line(df, x="frame", y="compliance", title="Compliance timeline"), use_container_width=True)
                st.metric("Avg compliance", f"{df.compliance.mean():.1f}%")
                if last is not None: st.image(last[:, :, ::-1], caption="Sample violation frame")
                db.log("safety_events", centre=centre, persons=0, violations=int(df.violations.sum()),
                       compliance=float(df.compliance.mean()), details="video")

# ---------------- Infrastructure ----------------
with tabs[3]:
    st.subheader("Equipment availability & maintenance-log check")
    a, b = st.columns(2)
    with a:
        exp = st.multiselect("Expected equipment (COCO classes for demo)",
                             ["laptop", "tv", "keyboard", "mouse", "chair", "monitor", "cell phone", "bottle"],
                             ["laptop", "tv", "chair"])
        img = st.file_uploader("Lab / workshop image", ["jpg", "png", "jpeg"], key="inf")
        miss = []
        if img:
            ann, seen, miss = E.equipment_check(to_bgr(img), exp, conf=min(conf, 0.4))
            st.image(ann[:, :, ::-1], use_container_width=True)
            st.write("Detected:", ", ".join(seen) or "–")
            (st.error if miss else st.success)(f"Missing: {', '.join(miss)}" if miss else "All expected equipment present")
    with b:
        st.markdown("**Maintenance log (CSV: equipment_id, name, last_service, interval_days)**")
        log = st.file_uploader("Log CSV", ["csv"], key="log")
        df = pd.read_csv(log) if log else pd.DataFrame(
            [["EQ1", "Lathe", "2026-05-01", 90], ["EQ2", "Welding set", "2026-09-20", 60], ["EQ3", "CNC", "2026-07-15", 30]],
            columns=["equipment_id", "name", "last_service", "interval_days"])
        ms = E.maintenance_status(df)
        st.dataframe(ms, use_container_width=True)
        over = ms[ms.status == "OVERDUE"].name.tolist()
        if over: st.error("Overdue maintenance: " + ", ".join(over))
        if st.button("Save infra check"):
            db.log("infra_checks", centre=centre, missing=",".join(miss), overdue=",".join(over)); st.success("Logged")

# ---------------- Dashboard ----------------
with tabs[0]:
    st.subheader("Centre overview")
    ai, sf, inf = (db.q(f"SELECT * FROM {t} ORDER BY id DESC LIMIT 20") for t in ("ai_checks", "safety_events", "infra_checks"))
    m = st.columns(4)
    m[0].metric("Present today", len(db.today_marked(centre)))
    m[1].metric("Attendance alerts", int((ai.flag != "OK").sum()) if not ai.empty else 0)
    m[2].metric("Avg safety compliance", f"{sf.compliance.mean():.0f}%" if not sf.empty else "–")
    m[3].metric("Infra checks logged", len(inf))
    if not ai.empty: st.markdown("**Attendance verification history**"); st.dataframe(ai, use_container_width=True)
    if not sf.empty: st.plotly_chart(px.bar(sf, x="ts", y="compliance", title="Safety compliance"), use_container_width=True)
    if not inf.empty: st.markdown("**Infrastructure checks**"); st.dataframe(inf, use_container_width=True)
