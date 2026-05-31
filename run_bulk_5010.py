"""
Masowa ekstrakcja danych dla site 5010.
Uruchom: python3 run_bulk_5010.py
"""

import json
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ecrf_extractor import ECRFExtractor, build_clean_json

LOGIN    = "roledert"
PASSWORD = "Troleder79!"
SITE     = "5010"
OUT_DIR  = Path(__file__).parent / "wyniki_5010"
OUT_DIR.mkdir(exist_ok=True)

def main():
    print(f"\n{'='*60}")
    print(f"  Masowa ekstrakcja — site {SITE}")
    print(f"  Wyniki: {OUT_DIR}")
    print(f"{'='*60}\n")

    with ECRFExtractor(headless=False) as ex:
        # 1. Logowanie
        ex.login(LOGIN, PASSWORD)

        # 2. Lista pacjentów
        patient_list = ex.list_site_patients(SITE)
        total = len(patient_list)
        print(f"\n>>> Znaleziono {total} pacjentów\n")

        if total == 0:
            print("[!] Brak pacjentów — sprawdź numer site lub uprawnienia konta.")
            return

        errors = []
        ok_count = 0

        # 3. Ekstrakcja każdego pacjenta
        for idx, rand_num in enumerate(patient_list, 1):
            out_file = OUT_DIR / f"result_{rand_num}.json"

            # Pomiń jeśli już pobrano
            if out_file.exists():
                print(f"[{idx}/{total}] {rand_num} — już pobrano, pomijam")
                ok_count += 1
                continue

            print(f"[{idx}/{total}] {rand_num}...", end=" ", flush=True)
            try:
                raw   = ex.extract(LOGIN, PASSWORD, rand_num)
                clean = build_clean_json(raw)
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(clean, f, ensure_ascii=False, indent=2)
                oct_vessels = sum(1 for v in clean.get("vessels", []) if v.get("oct_pre"))
                print(f"OK  (naczynia z OCT: {oct_vessels})")
                ok_count += 1
            except Exception as e:
                print(f"BŁĄD: {e}")
                errors.append((rand_num, str(e)))

    # 4. Buduj bazę OCT z wyników
    print(f"\n\n{'='*60}")
    print(f"  Pobrano: {ok_count}/{total}  |  Błędy: {len(errors)}")
    print(f"{'='*60}\n")

    build_oct_csv()

    if errors:
        print("\nBłędy:")
        for rand_num, err in errors:
            print(f"  {rand_num}: {err}")


def build_oct_csv():
    """Buduje baza_oct_5010.csv ze wszystkich plików JSON w wyniki_5010/"""
    rows = []
    json_files = sorted(OUT_DIR.glob("result_*.json"))
    print(f"Budowanie bazy OCT z {len(json_files)} plików...")

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue

        p   = data.get("patient", {})
        arm = p.get("arm") or "—"
        rand = p.get("randomization_number", jf.stem)

        for v in data.get("vessels", []):
            if not v.get("oct_pre"):
                continue
            rows.append({
                "Pacjent":              rand,
                "Ramię":               arm,
                "Naczynie":            v.get("segment", "—"),
                "Culprit":             "TAK" if v.get("culprit") else "NIE",
                "Cewnik OCT":          v.get("oct_catheter") or "—",
                "Pullback":            v.get("oct_pullback") or "—",
                "TCFA":                "TAK" if v.get("oct_tcfa") is True else ("NIE" if v.get("oct_tcfa") is False else "—"),
                "Plaque rupture":      "TAK" if v.get("oct_plaque_rupture") is True else ("NIE" if v.get("oct_plaque_rupture") is False else "—"),
                "Plaque erosion":      "TAK" if v.get("oct_plaque_erosion") is True else ("NIE" if v.get("oct_plaque_erosion") is False else "—"),
                "MLA (mm2)":           v.get("oct_mla_mm2"),
                "Stenoza OCT (%)":     v.get("oct_pct_lumen_stenosis"),
                "Dl. zmiany (mm)":     v.get("oct_lesion_length_mm"),
                "Prox. diam. (mm)":    v.get("oct_proximal_diam_mm"),
                "Dist. diam. (mm)":    v.get("oct_distal_diam_mm"),
                "FFR":                 v.get("ffr_adenosine"),
                "Pd/Pa":               v.get("pd_pa"),
                "RFR":                 v.get("rfr"),
                "Stenoza angio (%)":   v.get("stenosis_pct"),
                "TIMI pre":            v.get("timi_pre"),
                "TIMI post":           v.get("timi_post"),
                "PCI":                 "TAK" if v.get("pci_performed") else "NIE",
                "Stent":               "TAK" if v.get("stent_placed") is True else "NIE",
            })

    if not rows:
        print("Brak naczyń z OCT — baza OCT pusta.")
        return

    csv_path = OUT_DIR.parent / "baza_oct_5010.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Baza OCT zapisana: {csv_path}")
    print(f"   Pacjentów z OCT: {len(set(r['Pacjent'] for r in rows))}")
    print(f"   Naczyń z OCT:    {len(rows)}")


if __name__ == "__main__":
    main()
