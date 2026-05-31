"""
eCRF Diagram – Ekstraktor danych angiograficznych (Streamlit)
Uruchom: streamlit run streamlit_app.py
"""

import json
import re
import time
import threading
from pathlib import Path

import pandas as pd
import streamlit as st

from ecrf_extractor import ECRFExtractor, build_clean_json

st.set_page_config(
    page_title="eCRF Diagram – Ekstraktor",
    page_icon="🏥",
    layout="wide",
)

if "loaded_patients" not in st.session_state:
    st.session_state.loaded_patients = {}   # {rand_num: data}
if "bulk_log" not in st.session_state:
    st.session_state.bulk_log = []


# ── Helpers ───────────────────────────────────────────────────────────────────

def timi_label(val):
    if val is None:
        return "—"
    return ["0", "I", "II", "III"][val] if 0 <= val <= 3 else str(val)


CELL_STYLE = (
    "display:inline-block;font-size:18px;padding:4px 14px 4px 0;"
    "min-width:140px;vertical-align:top;"
)
LABEL_STYLE = "font-size:12px;color:#999;display:block;margin-bottom:1px;"


def _cell(label: str, value: str, color: str = "") -> str:
    val_style = (
        f"font-size:18px;font-weight:600;color:{color};"
        if color else "font-size:18px;font-weight:600;"
    )
    return (
        f'<span style="{CELL_STYLE}">'
        f'<span style="{LABEL_STYLE}">{label}</span>'
        f'<span style="{val_style}">{value}</span>'
        f'</span>'
    )


def _bool_val(val, true_color: str = "", false_color: str = "") -> str:
    if val is True:
        return (
            f'<span style="color:{true_color};font-size:18px;font-weight:600;">TAK</span>'
            if true_color else "TAK"
        )
    if val is False:
        return (
            f'<span style="color:{false_color};font-size:18px;font-weight:600;">NIE</span>'
            if false_color else "NIE"
        )
    return "—"


def _colored(val, color):
    return f'<span style="color:{color};font-size:18px;font-weight:600;">{val}</span>'


def _run_extraction(login, password, patient_val, result_container):
    try:
        with ECRFExtractor(headless=True) as ex:
            raw = ex.extract(login, password, patient_val)
        result_container["data"] = build_clean_json(raw)
    except RuntimeError as exc:
        result_container["error"] = str(exc)
    except Exception as exc:
        result_container["error"] = f"Błąd ekstrakcji: {exc}"


def _wait_thread(thread, start_time, steps, status_box):
    step_i = 0
    while thread.is_alive():
        elapsed = time.time() - start_time
        step_i = min(int(elapsed / 12), len(steps) - 1)
        status_box.info(f"{steps[step_i]}  ({int(elapsed)}s)")
        time.sleep(0.5)
    thread.join()


def render_patient(data):
    p = data.get("patient", {})
    vessels = data.get("vessels", [])
    rand = p.get("randomization_number", "?")
    arm  = p.get("arm") or "—"

    st.markdown(
        f"### Pacjent {rand}<br>"
        f"<span style='font-size:24px;font-weight:600;color:#e6a817'>{arm}</span>",
        unsafe_allow_html=True,
    )

    if not vessels:
        st.info("Brak danych o naczyniach.")
        return

    st.markdown("**Naczynia**")
    for i, v in enumerate(vessels):
        is_culprit = v.get("culprit")
        culprit_html = (
            ' <span style="color:#c0392b;font-weight:700;">★ CULPRIT</span>'
            if is_culprit else ""
        )

        with st.expander(f"Naczynie {i+1}: {v.get('segment', '?')}", expanded=True):
            ffr_val = v.get("ffr_adenosine")
            ffr_str = _colored(ffr_val, "#e6a817") if ffr_val is not None else "—"
            pci_str = _bool_val(v.get("pci_performed"), true_color="#1a7f47")
            culprit_str = (
                '<span style="color:#c0392b;font-size:18px;font-weight:600;">TAK ★</span>'
                if is_culprit else "NIE"
            )
            oct_pre_str = (
                _colored("TAK", "#e67e22") if v.get("oct_pre") else "NIE"
            )

            html = f'<div style="line-height:2.2;">{culprit_html}<br>'

            # ── Wiersz 1: angiografia ───────────────────────────────────────
            html += _cell("Stenoza",   f"{v['stenosis_pct']}%" if v.get("stenosis_pct") is not None else "—")
            html += _cell("TIMI pre",  timi_label(v.get("timi_pre")))
            html += _cell("TIMI post", timi_label(v.get("timi_post")))
            html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">FFR</span>{ffr_str}</span>'

            # ── Wiersz 2: PCI / stent ───────────────────────────────────────
            html += "<br>"
            html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">OCT pre</span>{oct_pre_str}</span>'
            html += _cell("Bifurcation",  _bool_val(v.get("bifurcation")))
            html += _cell("Predilatacja", _bool_val(v.get("predilatation")))
            html += _cell("Stent",        _bool_val(v.get("stent_placed")))

            # ── Wiersz 3: PCI / fizjologia ─────────────────────────────────
            html += "<br>"
            html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">PCI</span>{pci_str}</span>'
            html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">Culprit</span>{culprit_str}</span>'
            if v.get("pci_successful") is not None:
                html += _cell("PCI sukces", _bool_val(v.get("pci_successful"), true_color="#1a7f47", false_color="#c0392b"))

            # Pd/Pa + RFR
            if v.get("pd_pa") is not None or v.get("rfr") is not None:
                html += "<br>"
                pd_pa_val = v.get("pd_pa")
                rfr_val2  = v.get("rfr")
                html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">Pd/Pa</span>{_colored(pd_pa_val, "#e6a817") if pd_pa_val is not None else "—"}</span>'
                html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">RFR</span>{_colored(rfr_val2, "#e6a817") if rfr_val2 is not None else "—"}</span>'

            # ── Wiersz OCT (pola 6.2–6.12) — tylko gdy OCT wykonane ───────
            if v.get("oct_pre"):
                html += "<br><hr style='border:none;border-top:1px solid #eee;margin:6px 0'>"
                html += f'<span style="font-size:12px;color:#e67e22;font-weight:700;text-transform:uppercase;letter-spacing:.05em">OCT — szczegóły</span><br>'
                html += _cell("Przygotowanie", _bool_val(v.get("oct_lesion_prep")))
                html += _cell("Cewnik",        v.get("oct_catheter") or "—")
                html += _cell("Pullback",       v.get("oct_pullback") or "—")
                html += "<br>"
                tcfa_str = _colored("TAK", "#c0392b") if v.get("oct_tcfa") else ("NIE" if v.get("oct_tcfa") is False else "—")
                rup_str  = _colored("TAK", "#c0392b") if v.get("oct_plaque_rupture") else ("NIE" if v.get("oct_plaque_rupture") is False else "—")
                ero_str  = _colored("TAK", "#c0392b") if v.get("oct_plaque_erosion") else ("NIE" if v.get("oct_plaque_erosion") is False else "—")
                html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">TCFA</span>{tcfa_str}</span>'
                html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">Plaque rupture</span>{rup_str}</span>'
                html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">Plaque erosion</span>{ero_str}</span>'
                html += "<br>"
                html += _cell("MLA (mm²)",       str(v["oct_mla_mm2"])      if v.get("oct_mla_mm2")      is not None else "—")
                html += _cell("Stenoza OCT (%)", str(v["oct_pct_lumen_stenosis"]) if v.get("oct_pct_lumen_stenosis") is not None else "—")
                html += _cell("Dł. zmiany (mm)", str(v["oct_lesion_length_mm"]) if v.get("oct_lesion_length_mm") is not None else "—")
                html += "<br>"
                html += _cell("Prox. diam. (mm)", str(v["oct_proximal_diam_mm"]) if v.get("oct_proximal_diam_mm") is not None else "—")
                html += _cell("Dist. diam. (mm)", str(v["oct_distal_diam_mm"])   if v.get("oct_distal_diam_mm")   is not None else "—")

            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)

            if v.get("stents"):
                parts = [
                    f"{s.get('type') or 'stent'} {s.get('diameter_mm')}×{s.get('length_mm')}mm"
                    if s.get("diameter_mm") and s.get("length_mm")
                    else s.get("type") or "stent"
                    for s in v["stents"]
                ]
                st.info("Stenty: " + " | ".join(parts))


def build_oct_dataframe(patients: dict) -> pd.DataFrame:
    """Buduje tabelę OCT ze wszystkich załadowanych pacjentów."""
    rows = []
    for rand_num, data in patients.items():
        p = data.get("patient", {})
        arm = p.get("arm") or "—"
        for v in data.get("vessels", []):
            if not v.get("oct_pre"):
                continue
            rows.append({
                "Pacjent":          rand_num,
                "Ramię":            arm,
                "Naczynie":         v.get("segment", "—"),
                "Culprit":          "TAK" if v.get("culprit") else "NIE",
                "Cewnik OCT":       v.get("oct_catheter") or "—",
                "Pullback":         v.get("oct_pullback") or "—",
                "TCFA":             "TAK" if v.get("oct_tcfa") is True else ("NIE" if v.get("oct_tcfa") is False else "—"),
                "Plaque rupture":   "TAK" if v.get("oct_plaque_rupture") is True else ("NIE" if v.get("oct_plaque_rupture") is False else "—"),
                "Plaque erosion":   "TAK" if v.get("oct_plaque_erosion") is True else ("NIE" if v.get("oct_plaque_erosion") is False else "—"),
                "MLA (mm²)":        v.get("oct_mla_mm2"),
                "Stenoza OCT (%)":  v.get("oct_pct_lumen_stenosis"),
                "Dł. zmiany (mm)":  v.get("oct_lesion_length_mm"),
                "Prox. diam. (mm)": v.get("oct_proximal_diam_mm"),
                "Dist. diam. (mm)": v.get("oct_distal_diam_mm"),
            })
    return pd.DataFrame(rows)


# ── Page title ────────────────────────────────────────────────────────────────

st.title("eCRF Diagram — Ekstraktor danych angiograficznych")

tab1, tab2, tab3 = st.tabs(["📋 Ekstrakcja", "⚡ Masowa ekstrakcja (site)", "🔬 Baza OCT"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — pojedyncza ekstrakcja
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    with st.form("extract_form"):
        c1, c2, c3 = st.columns(3)
        patient_input  = c1.text_input("Numer pacjenta", placeholder="np. 1701-0031")
        login_input    = c2.text_input("Login")
        password_input = c3.text_input("Hasło", type="password")
        submitted = st.form_submit_button("Wyciągnij dane", type="primary", use_container_width=True)

    if submitted:
        patient_val = patient_input.strip()
        if not re.match(r"^\d{4}-\d{4}$", patient_val):
            st.error(f"Nieprawidłowy format numeru: '{patient_val}'. Oczekiwany: XXXX-AAAA")
        elif not login_input or not password_input:
            st.error("Podaj login i hasło.")
        else:
            status_box  = st.empty()
            rc: dict    = {"data": None, "error": None}
            start_time  = time.time()
            steps = ["Logowanie do eCRF...", "Szukam pacjenta...", "Ładuję sekcje CRF...", "Wyciągam dane..."]
            thread = threading.Thread(target=_run_extraction, args=(login_input, password_input, patient_val, rc), daemon=True)
            thread.start()
            with st.spinner("Ekstrakcja — ~45s..."):
                _wait_thread(thread, start_time, steps, status_box)
            status_box.empty()
            elapsed = time.time() - start_time

            if rc["error"]:
                st.error(f"Błąd: {rc['error']}")
            else:
                clean    = rc["data"]
                rand_num = clean.get("patient", {}).get("randomization_number", patient_val)
                st.session_state.loaded_patients[rand_num] = clean
                out_path = Path(f"result_{patient_val}.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(clean, f, ensure_ascii=False, indent=2)
                st.success(f"Dane wyciągnięte w {elapsed:.1f}s! Zapisano: {out_path}")
                st.balloons()

    # ── File upload ───────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Załaduj wyniki z pliku JSON")
    uploaded_files = st.file_uploader(
        "Wybierz pliki JSON", type="json",
        accept_multiple_files=True, label_visibility="collapsed",
    )
    if uploaded_files:
        for uf in uploaded_files:
            try:
                data     = json.load(uf)
                rand_num = data.get("patient", {}).get("randomization_number") or uf.name
                if rand_num not in st.session_state.loaded_patients:
                    st.session_state.loaded_patients[rand_num] = data
                    st.toast(f"Załadowano: {rand_num}")
            except Exception as exc:
                st.error(f"Błąd parsowania {uf.name}: {exc}")

    # chips + clear
    if st.session_state.loaded_patients:
        chips = " ".join([
            f'<span style="background:#e8f4fd;color:#1a6fb3;border-radius:20px;'
            f'padding:4px 14px;font-size:.82rem;font-weight:600;display:inline-block;margin:2px">{k}</span>'
            for k in st.session_state.loaded_patients
        ])
        cc, cb = st.columns([5, 1])
        cc.markdown(chips, unsafe_allow_html=True)
        if cb.button("Wyczyść wszystkie", use_container_width=True):
            st.session_state.loaded_patients = {}
            st.rerun()

    # wyniki
    if st.session_state.loaded_patients:
        st.divider()
        to_remove = None
        for rand_num, data in list(st.session_state.loaded_patients.items()):
            with st.container(border=True):
                col_data, col_act = st.columns([6, 1])
                with col_data:
                    render_patient(data)
                with col_act:
                    st.download_button(
                        "Pobierz JSON",
                        data=json.dumps(data, ensure_ascii=False, indent=2),
                        file_name=f"result_{rand_num}.json",
                        mime="application/json",
                        key=f"dl_{rand_num}",
                        use_container_width=True,
                    )
                    if st.button("Usuń", key=f"rm_{rand_num}", use_container_width=True):
                        to_remove = rand_num
        if to_remove:
            del st.session_state.loaded_patients[to_remove]
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — masowa ekstrakcja całego site
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Masowa ekstrakcja wszystkich pacjentów z danego site")
    st.info("App zaloguje się do eCRF, pobierze listę wszystkich pacjentów dla site i wyciągnie dane kolejno dla każdego. Może trwać wiele minut.")

    with st.form("bulk_form"):
        bc1, bc2, bc3 = st.columns(3)
        bulk_site  = bc1.text_input("Numer site", placeholder="np. 5010")
        bulk_login = bc2.text_input("Login", key="b_login")
        bulk_pass  = bc3.text_input("Hasło", type="password", key="b_pass")
        bulk_go    = st.form_submit_button("Rozpocznij ekstrakcję masową", type="primary", use_container_width=True)

    if bulk_go:
        if not bulk_site.strip().isdigit():
            st.error("Podaj poprawny numer site (np. 5010)")
        elif not bulk_login or not bulk_pass:
            st.error("Podaj login i hasło.")
        else:
            site_val = bulk_site.strip()
            st.session_state.bulk_log = []
            progress_bar  = st.progress(0, text="Inicjalizacja...")
            log_box       = st.empty()
            summary_box   = st.empty()

            bulk_result: dict = {"patients": [], "error": None}

            def run_bulk():
                try:
                    with ECRFExtractor(headless=True) as ex:
                        ex.login(bulk_login, bulk_pass)
                        patient_list = ex.list_site_patients(site_val)
                        bulk_result["patients"] = patient_list
                        total = len(patient_list)
                        st.session_state.bulk_log.append(f"✅ Znaleziono {total} pacjentów")

                        for idx, rand_num in enumerate(patient_list):
                            st.session_state.bulk_log.append(f"⏳ [{idx+1}/{total}] {rand_num}...")
                            try:
                                raw   = ex.extract(bulk_login, bulk_pass, rand_num)
                                clean = build_clean_json(raw)
                                st.session_state.loaded_patients[rand_num] = clean
                                out   = Path(f"result_{rand_num}.json")
                                with open(out, "w", encoding="utf-8") as f:
                                    json.dump(clean, f, ensure_ascii=False, indent=2)
                                st.session_state.bulk_log[-1] = f"✅ [{idx+1}/{total}] {rand_num}"
                            except Exception as e:
                                st.session_state.bulk_log[-1] = f"❌ [{idx+1}/{total}] {rand_num} — {e}"
                except Exception as exc:
                    bulk_result["error"] = str(exc)

            thread = threading.Thread(target=run_bulk, daemon=True)
            thread.start()

            while thread.is_alive():
                log = st.session_state.bulk_log
                log_box.text_area("Log", "\n".join(log[-30:]), height=300)
                done = sum(1 for l in log if l.startswith("✅") and "Znaleziono" not in l)
                total_found = next((int(re.search(r"\d+", l).group()) for l in log if "Znaleziono" in l), 0)
                if total_found > 0:
                    progress_bar.progress(done / total_found, text=f"{done}/{total_found} pacjentów")
                time.sleep(1)
            thread.join()

            log_box.text_area("Log", "\n".join(st.session_state.bulk_log), height=300)
            if bulk_result["error"]:
                st.error(f"Błąd: {bulk_result['error']}")
            else:
                ok  = sum(1 for l in st.session_state.bulk_log if l.startswith("✅") and "Znaleziono" not in l)
                err = sum(1 for l in st.session_state.bulk_log if l.startswith("❌"))
                progress_bar.progress(1.0, text="Gotowe!")
                summary_box.success(f"Zakończono: {ok} pobranych, {err} błędów. Przejdź do zakładki 🔬 Baza OCT.")
                st.balloons()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — baza OCT
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Baza danych OCT")

    if not st.session_state.loaded_patients:
        st.info("Brak załadowanych pacjentów. Wyciągnij dane w zakładce 📋 lub ⚡.")
    else:
        df = build_oct_dataframe(st.session_state.loaded_patients)
        total_pts   = len(st.session_state.loaded_patients)
        oct_pts     = df["Pacjent"].nunique() if not df.empty else 0
        oct_vessels = len(df)

        # ── Metryki podsumowania ──────────────────────────────────────────
        m1, m2, m3 = st.columns(3)
        m1.metric("Pacjenci ogółem",    total_pts)
        m2.metric("Pacjenci z OCT",     oct_pts)
        m3.metric("Naczynia z OCT",     oct_vessels)

        if df.empty:
            st.warning("Żaden z załadowanych pacjentów nie ma wykonanego OCT.")
        else:
            st.divider()

            # ── Filtry ───────────────────────────────────────────────────
            f1, f2, f3, f4 = st.columns(4)
            arms     = ["Wszystkie"] + sorted(df["Ramię"].unique().tolist())
            culprits = ["Wszystkie", "TAK", "NIE"]
            tcfas    = ["Wszystkie", "TAK", "NIE", "—"]
            ruptures = ["Wszystkie", "TAK", "NIE", "—"]

            sel_arm     = f1.selectbox("Ramię",         arms)
            sel_culprit = f2.selectbox("Culprit",       culprits)
            sel_tcfa    = f3.selectbox("TCFA",          tcfas)
            sel_rupture = f4.selectbox("Plaque rupture", ruptures)

            fdf = df.copy()
            if sel_arm     != "Wszystkie": fdf = fdf[fdf["Ramię"]          == sel_arm]
            if sel_culprit != "Wszystkie": fdf = fdf[fdf["Culprit"]        == sel_culprit]
            if sel_tcfa    != "Wszystkie": fdf = fdf[fdf["TCFA"]           == sel_tcfa]
            if sel_rupture != "Wszystkie": fdf = fdf[fdf["Plaque rupture"] == sel_rupture]

            st.markdown(f"**Wyświetlono: {len(fdf)} naczyń**")
            st.dataframe(fdf, use_container_width=True, hide_index=True)

            # ── Eksport ───────────────────────────────────────────────────
            st.divider()
            ex1, ex2 = st.columns(2)

            csv_data = fdf.to_csv(index=False, sep=";").encode("utf-8-sig")
            ex1.download_button(
                "⬇ Pobierz CSV",
                data=csv_data,
                file_name="baza_oct.csv",
                mime="text/csv",
                use_container_width=True,
            )

            try:
                import io
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    fdf.to_excel(writer, index=False, sheet_name="Baza OCT")
                buf.seek(0)
                ex2.download_button(
                    "⬇ Pobierz Excel",
                    data=buf,
                    file_name="baza_oct.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            except ImportError:
                ex2.info("Zainstaluj openpyxl dla eksportu Excel.")
