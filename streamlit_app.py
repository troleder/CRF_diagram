"""
eCRF Diagram – Ekstraktor danych angiograficznych (Streamlit)
Uruchom: streamlit run streamlit_app.py
"""

import json
import re
import time
import threading
from pathlib import Path

import streamlit as st

from ecrf_extractor import ECRFExtractor, build_clean_json

st.set_page_config(
    page_title="eCRF Diagram – Ekstraktor",
    page_icon="🏥",
    layout="wide",
)

if "loaded_patients" not in st.session_state:
    st.session_state.loaded_patients = {}  # {rand_num: data}


# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_bool(val):
    if val is True:
        return ":green[TAK]"
    if val is False:
        return ":red[NIE]"
    return "—"


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
    val_style = f"font-size:18px;font-weight:600;color:{color};" if color else "font-size:18px;font-weight:600;"
    return (
        f'<span style="{CELL_STYLE}">'
        f'<span style="{LABEL_STYLE}">{label}</span>'
        f'<span style="{val_style}">{value}</span>'
        f'</span>'
    )


def _bool_val(val, true_color: str = "", false_color: str = "") -> str:
    if val is True:
        return f'<span style="color:{true_color};font-size:18px;font-weight:600;">TAK</span>' if true_color else "TAK"
    if val is False:
        return f'<span style="color:{false_color};font-size:18px;font-weight:600;">NIE</span>' if false_color else "NIE"
    return "—"


def render_patient(data):
    p = data.get("patient", {})
    vessels = data.get("vessels", [])
    rand = p.get("randomization_number", "?")

    arm = p.get("arm") or "—"
    st.markdown(
        f"### Pacjent {rand}  <span style='font-size:.85rem;color:#888'>{arm}</span>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ramię", arm)
    c2.metric("Płeć", p.get("sex") or "—")
    c3.metric("LVEF", p.get("lvef") or "—")
    c4.metric("NYHA", p.get("nyha") or "—")

    c1, c2, c3 = st.columns(3)
    c1.metric("Cukrzyca",       "TAK" if p.get("diabetes") is True  else "NIE" if p.get("diabetes") is False else "—")
    c2.metric("Nadciśnienie",   "TAK" if p.get("hypertension") is True else "NIE" if p.get("hypertension") is False else "—")
    c3.metric("Poprzednie PCI", "TAK" if p.get("previous_pci") is True else "NIE" if p.get("previous_pci") is False else "—")

    if not vessels:
        return

    st.markdown("**Naczynia**")
    for i, v in enumerate(vessels):
        is_culprit = v.get("culprit")
        culprit_html = (
            ' <span style="color:#c0392b;font-weight:700;">★ CULPRIT</span>'
            if is_culprit else ""
        )
        header = f"Naczynie {i+1}: {v.get('segment', '?')}"

        with st.expander(header, expanded=True):
            ffr_val = v.get("ffr_adenosine")
            ffr_str = (
                f'<span style="color:#e6a817;font-size:18px;font-weight:600;">{ffr_val}</span>'
                if ffr_val is not None
                else "—"
            )
            pci_str = _bool_val(v.get("pci_performed"), true_color="#1a7f47")
            culprit_str = (
                '<span style="color:#c0392b;font-size:18px;font-weight:600;">TAK ★</span>'
                if is_culprit else "NIE"
            )

            html = '<div style="line-height:2.2;">'
            html += culprit_html  # red CULPRIT badge at top
            html += "<br>"
            html += _cell("Stenoza",    f"{v['stenosis_pct']}%" if v.get("stenosis_pct") is not None else "—")
            html += _cell("TIMI pre",   timi_label(v.get("timi_pre")))
            html += _cell("TIMI post",  timi_label(v.get("timi_post")))
            html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">FFR</span>{ffr_str}</span>'
            html += "<br>"
            oct_str = (
                '<span style="color:#e67e22;font-size:18px;font-weight:600;">TAK</span>'
                if v.get("oct_pre") else "NIE"
            )
            html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">OCT pre</span>{oct_str}</span>'
            html += _cell("Bifurcation",  _bool_val(v.get("bifurcation")))
            html += _cell("Predilatacja", _bool_val(v.get("predilatation")))
            html += _cell("Stent",        _bool_val(v.get("stent_placed")))
            html += "<br>"
            html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">PCI</span>{pci_str}</span>'
            html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">Culprit</span>{culprit_str}</span>'
            if v.get("pci_successful") is not None:
                html += _cell("PCI sukces", _bool_val(v.get("pci_successful"), true_color="#1a7f47", false_color="#c0392b"))
            if v.get("pd_pa") is not None or v.get("rfr") is not None:
                html += "<br>"
                pd_pa_val = v.get("pd_pa")
                rfr_val2  = v.get("rfr")
                pd_pa_str = f'<span style="color:#e6a817;font-size:18px;font-weight:600;">{pd_pa_val}</span>' if pd_pa_val is not None else "—"
                rfr_str2  = f'<span style="color:#e6a817;font-size:18px;font-weight:600;">{rfr_val2}</span>'  if rfr_val2  is not None else "—"
                html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">Pd/Pa</span>{pd_pa_str}</span>'
                html += f'<span style="{CELL_STYLE}"><span style="{LABEL_STYLE}">RFR</span>{rfr_str2}</span>'
            html += "</div>"

            st.markdown(html, unsafe_allow_html=True)

            if v.get("stents"):
                parts = []
                for s in v["stents"]:
                    t = s.get("type") or "stent"
                    d = s.get("diameter_mm")
                    l = s.get("length_mm")
                    parts.append(f"{t} {d}×{l}mm" if d and l else t)
                st.info("Stenty: " + " | ".join(parts))


# ── Page title ────────────────────────────────────────────────────────────────

st.title("eCRF Diagram — Ekstraktor danych angiograficznych")

# ── Extraction form ───────────────────────────────────────────────────────────

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
        status_box = st.empty()
        steps = [
            "Logowanie do eCRF...",
            "Szukam pacjenta w BrowseSubjects...",
            "Ładuję sekcje CRF...",
            "Wyciągam dane formularzy...",
        ]
        result_container: dict = {"data": None, "error": None}
        start_time = time.time()

        def run_extraction():
            try:
                with ECRFExtractor(headless=True) as ex:
                    raw = ex.extract(login_input, password_input, patient_val)
                result_container["data"] = build_clean_json(raw)
            except RuntimeError as exc:
                result_container["error"] = str(exc)
            except Exception as exc:
                result_container["error"] = f"Błąd ekstrakcji: {exc}"

        thread = threading.Thread(target=run_extraction, daemon=True)
        thread.start()

        with st.spinner("Ekstrakcja danych — może potrwać ~45s..."):
            step_i = 0
            while thread.is_alive():
                elapsed = time.time() - start_time
                step_i = min(int(elapsed / 12), len(steps) - 1)
                status_box.info(f"{steps[step_i]}  ({int(elapsed)}s)")
                time.sleep(0.5)
            thread.join()

        elapsed = time.time() - start_time
        status_box.empty()

        if result_container["error"]:
            st.error(f"Błąd: {result_container['error']}")
        else:
            clean = result_container["data"]
            rand_num = clean.get("patient", {}).get("randomization_number", patient_val)
            st.session_state.loaded_patients[rand_num] = clean

            out_path = Path(f"result_{patient_val}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(clean, f, ensure_ascii=False, indent=2)

            st.success(f"Dane wyciągnięte w {elapsed:.1f}s! Zapisano: {out_path}")
            st.balloons()

# ── File upload ───────────────────────────────────────────────────────────────

st.divider()
st.subheader("Załaduj wyniki z pliku JSON")

uploaded_files = st.file_uploader(
    "Wybierz pliki JSON",
    type="json",
    accept_multiple_files=True,
    label_visibility="collapsed",
)
if uploaded_files:
    for uf in uploaded_files:
        try:
            data = json.load(uf)
            rand_num = data.get("patient", {}).get("randomization_number") or uf.name
            if rand_num not in st.session_state.loaded_patients:
                st.session_state.loaded_patients[rand_num] = data
                st.toast(f"Załadowano: {rand_num}")
        except Exception as exc:
            st.error(f"Błąd parsowania {uf.name}: {exc}")

# Loaded-patients chips + clear all
if st.session_state.loaded_patients:
    chips = " ".join([
        f'<span style="background:#e8f4fd;color:#1a6fb3;border-radius:20px;'
        f'padding:4px 14px;font-size:.82rem;font-weight:600;display:inline-block;margin:2px">{k}</span>'
        for k in st.session_state.loaded_patients
    ])
    col_chips, col_clear = st.columns([5, 1])
    col_chips.markdown(chips, unsafe_allow_html=True)
    if col_clear.button("Wyczyść wszystkie", use_container_width=True):
        st.session_state.loaded_patients = {}
        st.rerun()

# ── Results ───────────────────────────────────────────────────────────────────

if st.session_state.loaded_patients:
    st.divider()
    to_remove = None
    for rand_num, data in list(st.session_state.loaded_patients.items()):
        with st.container(border=True):
            col_data, col_actions = st.columns([6, 1])
            with col_data:
                render_patient(data)
            with col_actions:
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
