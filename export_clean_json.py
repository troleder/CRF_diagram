"""
Konwertuje surowy result_*.json (z ecrf_extractor.py) na czysty, ustrukturyzowany JSON
gotowy do importu w zewnętrznym oprogramowaniu.

Użycie:
    python3 export_clean_json.py result_1701-0031.json
    python3 export_clean_json.py result_1701-0031.json --output clean_1701-0031.json
"""

import json
import re
import sys
import argparse
from pathlib import Path


# ── Mapowania wartości ────────────────────────────────────────────────────────

TIMI_MAP = {"0": 0, "I": 1, "II": 2, "III": 3, "1": 1, "2": 2, "3": 3}

YES_VALUES  = {"yes", "tak", "true", "1", "+", "checked"}
NO_VALUES   = {"no", "nie", "false", "0", "-"}

def to_bool(val: str) -> bool | None:
    if not val:
        return None
    v = val.strip().lower()
    if v in YES_VALUES:
        return True
    if v in NO_VALUES:
        return False
    return None

def to_float(val: str) -> float | None:
    if not val:
        return None
    try:
        return float(val.replace(",", ".").strip())
    except ValueError:
        return None

def to_int(val: str) -> int | None:
    if not val:
        return None
    m = re.search(r"\d+", val)
    return int(m.group()) if m else None

def clean_segment(val: str) -> str:
    """'01= RCA proximal' → '01 = RCA proximal'"""
    return val.strip() if val else ""


# ── Ekstrakcja pól z sekcji ───────────────────────────────────────────────────

def first(sections: dict, *keys: str, default="") -> str:
    """Zwraca pierwszą wartość pasującą do klucza (case-insensitive) z dowolnej sekcji."""
    for sec_fields in sections.values():
        for k, v in sec_fields.items():
            if any(key.lower() in k.lower() for key in keys):
                if v and v.strip():
                    return v.strip()
    return default


def extract_patient(sections: dict, rand: str, site: str) -> dict:
    """Wyciąga dane na poziomie pacjenta."""
    arm_raw = first(sections, "Patient is randomized to", "randomized to")
    if not arm_raw:
        # fallback: szukaj zaznaczonego radio
        if first(sections, "Experimental arm"):
            arm_raw = "Experimental arm (FFR + OCT guided PCI)"
        elif first(sections, "Comparative arm"):
            arm_raw = "Comparative arm (FFR guided PCI)"

    return {
        "randomization_number": rand,
        "site": site,
        "arm": arm_raw or None,
        "sex":          first(sections, "Male", "Female", "Sex"),
        "indication":   first(sections, "ACS", "Indication", "IAP", "STEMI", "NSTEMI"),
        "lvef":         first(sections, "LVEF", "lvef", "ejection fraction"),
        "nyha":         first(sections, "NYHA"),
        "diabetes":     to_bool(first(sections, "Diabetes")),
        "smoking":      first(sections, "Smoking", "Current smoker", "Former smoker"),
        "hypertension": to_bool(first(sections, "Hypertension")),
        "previous_pci": to_bool(first(sections, "Previous PCI")),
        "date_angio":   first(sections, "Date coronary angiography", "Date procedure"),
    }


def extract_vessels(sections: dict) -> list:
    """
    Grupuje sekcje imaging + intervention + stents po nazwie segmentu.
    Zwraca listę naczyń jako słowniki.
    """
    # --- zbierz sekcje imaging (mają "Initial TIMI flow" lub "Culprit lesion") ---
    imaging_sections = []
    intervention_sections = []
    stent_sections = []

    for sec_name, fields in sections.items():
        fkeys = {k.lower() for k in fields}
        fvals = {v.lower() for v in fields.values() if v}

        has_segment = any("target lesion segment" in k for k in fkeys)
        has_timi_pre = any("initial timi flow" in k for k in fkeys)
        has_pci = any("pci procedure performed" in k for k in fkeys)
        has_stent_type = any("type of stent" in k for k in fkeys)

        if has_stent_type:
            stent_sections.append(fields)
        elif has_segment and has_timi_pre:
            imaging_sections.append(fields)
        elif has_segment and has_pci:
            intervention_sections.append(fields)

    # --- indeksuj po segmencie ---
    def get_segment(fields: dict) -> str:
        for k, v in fields.items():
            if "target lesion segment" in k.lower():
                return clean_segment(v)
        return ""

    imaging_by_seg   = {get_segment(f): f for f in imaging_sections if get_segment(f)}
    interv_by_seg    = {get_segment(f): f for f in intervention_sections if get_segment(f)}

    # --- wszystkie segmenty ---
    all_segments = sorted(
        set(imaging_by_seg) | set(interv_by_seg),
        key=lambda s: s[:2]  # sortuj po numerze segmentu
    )

    # --- dopasuj stenty do naczyń (przez ParentSequenceNumber w URL / kolejność) ---
    # Stenty są już wyekstrahowane w kolejności — przyporządkuj je do naczyń przez
    # liczbę stentów w sekcji intervention
    vessels = []
    stent_idx = 0

    for seg in all_segments:
        img  = imaging_by_seg.get(seg, {})
        inv  = interv_by_seg.get(seg, {})

        def fv(fields, *keys):
            for k, v in fields.items():
                if any(key.lower() in k.lower() for key in keys):
                    return v.strip() if v else ""
            return ""

        # Imaging fields
        culprit_raw  = fv(img, "Culprit lesion")
        culprit      = to_bool(culprit_raw)
        stenosis_raw = fv(img, "Visually estimated diameter stenosis", "stenosis")
        timi_pre_raw = fv(img, "Initial TIMI flow")
        phys_done    = to_bool(fv(img, "Physiology measurements performed"))
        pd_pa        = to_float(fv(img, "Pd/Pa"))
        rfr          = to_float(fv(img, "RFR"))
        ffr_aden     = to_float(fv(img, "FFR adenosine"))
        oct_pre      = to_bool(fv(img, "OCT performed"))
        oct_system   = fv(img, "OCT system", "Optis", "Opstar") or None
        oct_pullback = fv(img, "pullback", "54 mm", "75 mm") or None

        # Intervention fields
        pci_done     = to_bool(fv(inv, "PCI procedure performed"))
        bifurc       = to_bool(fv(inv, "Bifurcation"))
        calcif       = fv(inv, "Calcification") or None
        predilatation= to_bool(fv(inv, "Balloon predilatation"))
        predil_size  = to_float(fv(inv, "Predilation-balloon size"))
        predil_press = to_int(fv(inv, "Highest pressure largest predilation"))
        stent_placed = to_bool(fv(inv, "Stent placement"))
        n_stents     = to_int(fv(inv, "Number of stents"))
        postdil_size = to_float(fv(inv, "Balloon size (max. diameter)"))
        postdil_press= to_int(fv(inv, "Highest pressure largest balloon"))
        timi_post_raw= fv(inv, "TIMI post")
        resid_sten   = fv(inv, "Visual Ds post", "residual stenosis") or None
        pci_success  = to_bool(fv(inv, "PCI successful"))
        oct_post     = to_bool(fv(inv, "OCT performed post stenting"))

        # Stenty dla tego naczynia
        vessel_stents = []
        if n_stents and stent_idx < len(stent_sections):
            for _ in range(n_stents):
                if stent_idx >= len(stent_sections):
                    break
                sf = stent_sections[stent_idx]
                def sv(fields, *keys):
                    for k, v in fields.items():
                        if any(key.lower() in k.lower() for key in keys):
                            return v.strip() if v else ""
                    return ""
                vessel_stents.append({
                    "type":        sv(sf, "Type of stent", "Stent form") or None,
                    "diameter_mm": to_float(sv(sf, "Diameter")),
                    "length_mm":   to_int(sv(sf, "Length")),
                })
                stent_idx += 1

        vessel = {
            "segment":    seg,
            "culprit":    culprit,
            # imaging
            "stenosis_pct":      to_int(stenosis_raw),
            "timi_pre":          TIMI_MAP.get(timi_pre_raw) if timi_pre_raw else None,
            "physiology_done":   phys_done,
            "pd_pa":             pd_pa,
            "rfr":               rfr,
            "ffr_adenosine":     ffr_aden,
            "oct_pre":           oct_pre,
            "oct_system":        oct_system,
            "oct_pullback_mm":   oct_pullback,
            # intervention
            "pci_performed":     pci_done,
            "bifurcation":       bifurc,
            "calcification":     calcif,
            "predilatation":     predilatation,
            "predil_balloon_mm": predil_size,
            "predil_pressure_atm": predil_press,
            "stent_placed":      stent_placed,
            "n_stents":          n_stents,
            "stents":            vessel_stents,
            "postdil_balloon_mm": postdil_size,
            "postdil_pressure_atm": postdil_press,
            "timi_post":         TIMI_MAP.get(timi_post_raw) if timi_post_raw else None,
            "residual_stenosis": resid_sten,
            "pci_successful":    pci_success,
            "oct_post":          oct_post,
        }
        vessels.append(vessel)

    return vessels


# ── Główna funkcja ────────────────────────────────────────────────────────────

def build_clean_json(raw: dict) -> dict:
    rand    = raw.get("randomization_number", "")
    site    = raw.get("site", "")
    sections = raw.get("sections", {})

    patient = extract_patient(sections, rand, site)
    vessels = extract_vessels(sections)

    return {
        "schema_version": "1.0",
        "patient": patient,
        "vessels": vessels,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Konwertuje surowy result_*.json na czysty JSON per pacjent/naczynie"
    )
    parser.add_argument("input",  help="Plik wejściowy result_*.json")
    parser.add_argument("--output", "-o", default="",
                        help="Plik wyjściowy (domyślnie: clean_<input>)")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[!] Plik nie istnieje: {args.input}")
        sys.exit(1)

    with open(in_path, encoding="utf-8") as f:
        raw = json.load(f)

    clean = build_clean_json(raw)

    out_path = Path(args.output) if args.output else in_path.parent / f"clean_{in_path.name}"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)

    print(f"Zapisano: {out_path}")
    print(json.dumps(clean, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
