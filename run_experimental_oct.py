"""
Ekstrakcja danych OCT dla pacjentów z ramienia doświadczalnego (Experimental arm).

Algorytm:
  1. Logowanie do eCRF (CombInterv study)
  2. Pobierz listę wszystkich site'ów ze Study.aspx (z paginacją)
  3. Dla każdego site → BrowseSubjects.aspx?site=XXXX
     - Pobierz WSZYSTKICH pacjentów (z paginacją)
     - Zachowaj tylko ramię "Experimental arm"
  4. Dla każdego pacjenta z Experimental arm:
     - Wyciągnij dane OCT z formularza "Lesion imaging and measurements"
  5. Buduj wyniki pogrupowane po site i patient ID
  6. Zapis do CSV (z delimiter=";") i Excel

Uruchom: python3 run_experimental_oct.py
Wyniki:  wyniki_experimental/  (JSON per pacjent)
         baza_oct_experimental.csv
"""

import json
import csv
import sys
import time
import re
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from ecrf_extractor import ECRFExtractor, PatientData, build_clean_json

# ── Konfiguracja ──────────────────────────────────────────────────────────────
LOGIN    = "roledert"
PASSWORD = "Troleder79!"
STUDY_ID = "4b40cced-3ab5-4f05-91bb-4a2f9bcc9b74"
BASE     = "https://www.ecrfdiagram.com/eCRF"

# Słowa kluczowe ramienia doświadczalnego (dopasowanie częściowe, case-insensitive)
EXPERIMENTAL_KW = ["experimental", "ffr + oct", "ffr+oct", "oct guided"]

OUT_DIR = Path(__file__).parent / "wyniki_experimental"
OUT_DIR.mkdir(exist_ok=True)


# ── Pomocnicze ────────────────────────────────────────────────────────────────

def is_experimental_arm(arm_text: str) -> bool:
    arm_lower = (arm_text or "").lower()
    return any(kw in arm_lower for kw in EXPERIMENTAL_KW)


def get_all_sites(ex: ECRFExtractor) -> list:
    """
    Zwraca listę (site_num, site_name) ze Study.aspx — obsługuje paginację DevExpress.
    Grida site'ów: ctl00_Content_tabStudySummary_grdSummary
    Paginacja przez: ASPx.GVPagerOnClick('...grdSummary', 'PNn')
    """
    from bs4 import BeautifulSoup
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    GRID_ID = "ctl00_Content_tabStudySummary_grdSummary"

    print(f"\n[*] Pobieranie listy site'ów ze Study.aspx...")
    ex.driver.get(f"{BASE}/Study.aspx?ID={STUDY_ID}")
    ex._wait_dx(20)

    sites = []
    visited_site_nums = set()
    page = 0
    MAX_PAGES = 20

    def collect_sites_from_page():
        soup = BeautifulSoup(ex.driver.page_source, "lxml")
        added = 0
        for el in soup.find_all(onclick=True):
            oc = el.get("onclick", "")
            m = re.search(r"BrowseSubjects\.aspx\?site=(\d+)", oc)
            if m:
                site_num = m.group(1)
                if site_num not in visited_site_nums:
                    txt = el.get_text(strip=True)
                    if txt and not txt.isdigit() and len(txt) > 5:
                        sites.append((site_num, txt))
                        visited_site_nums.add(site_num)
                        added += 1
        return added

    while page < MAX_PAGES:
        page += 1
        collect_sites_from_page()
        print(f"    Strona {page}: {len(sites)} site'ów łącznie")

        # Znajdź przycisk numerowanej strony (strona page+1) lub "Next Page"
        # DevExpress site grid: kliknij element z onclick zawierającym GVPagerOnClick i 'PN{page}'
        soup = BeautifulSoup(ex.driver.page_source, "lxml")
        next_pn = f"PN{page}"  # PN0=page1, PN1=page2, ...
        found_next = False

        for el in soup.find_all(onclick=True):
            oc = el.get("onclick", "")
            if GRID_ID in oc and next_pn in oc and "GVPagerOnClick" in oc:
                try:
                    # Znajdź ten element w Selenium i kliknij
                    driver_els = ex.driver.find_elements(
                        By.XPATH,
                        f"//*[contains(@onclick, '{GRID_ID}') and contains(@onclick, '{next_pn}') and contains(@onclick, 'GVPagerOnClick')]"
                    )
                    if driver_els:
                        driver_els[0].click()
                        ex._wait_dx(10)
                        found_next = True
                        break
                except Exception as e:
                    print(f"    [!] Błąd kliknięcia strony {page+1}: {e}")
                    break

        # Alternatywnie: execute_script
        if not found_next:
            # Sprawdź czy jest "Next Page" jako przycisk
            nxt_btns = ex.driver.find_elements(
                By.CSS_SELECTOR,
                f"#{GRID_ID}_DXPagerBottom a[title='Next Page'], "
                f"#{GRID_ID}_DXPagerTop a[title='Next Page']"
            )
            if not nxt_btns:
                # Ostatnia strona
                break
            nxt = nxt_btns[0]
            nxt_class = (nxt.get_attribute("class") or "").lower()
            if any(d in nxt_class for d in ("disabled", "dxp-bi")):
                break
            nxt.click()
            ex._wait_dx(10)

    print(f"    Łącznie znaleziono {len(sites)} site'ów")
    return sites


def get_experimental_patients(ex: ECRFExtractor, site_num: str) -> list:
    """
    Zwraca listę (rand_num, arm, guid) pacjentów z ramienia Experimental
    dla danego site'u.
    """
    from bs4 import BeautifulSoup
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    print(f"\n  [*] Pacjenci site {site_num}...")
    ex.driver.get(f"{BASE}/BrowseSubjects.aspx?site={site_num}")

    # Poczekaj na grid lub komunikat "brak danych"
    try:
        WebDriverWait(ex.driver, 45).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "tr[id*='DXDataRow']")
                      or d.find_elements(By.CSS_SELECTOR, ".dxgvEmptyDataRow")
                      or d.find_elements(By.CSS_SELECTOR, "td.dxgvEmptyDataCell")
        )
    except Exception:
        print(f"    [!] Timeout dla site {site_num} — brak dostępu lub brak pacjentów")
        return []
    ex._wait_dx(5)

    patients = []
    page = 0
    MAX_PAGES = 200  # 200 stron × 20 pacjentów = 4000 pacjentów max

    while page < MAX_PAGES:
        page += 1
        soup = BeautifulSoup(ex.driver.page_source, "lxml")
        rows = soup.find_all("tr", id=re.compile(r"DXDataRow"))

        for row in rows:
            row_text = row.get_text(" ", strip=True)

            # Wyciągnij numer randomizacji
            rand_m = re.search(r'\b(\d{4}-\d{4})\b', row_text)
            if not rand_m:
                continue
            rand_num = rand_m.group(1)

            # Wyciągnij ramię — szukaj słów kluczowych w treści całego wiersza
            # kolumna "Randomized to" zawiera "arm", "Experimental", "Comparative"
            arm_text = ""
            cells = [td.get_text(" ", strip=True) for td in row.find_all("td")]
            for cell in cells:
                cl = cell.lower()
                if "arm" in cl or "experimental" in cl or "comparative" in cl or "ffr" in cl:
                    arm_text = cell
                    break
            # Fallback: szukaj w treści całego wiersza
            if not arm_text:
                m_arm = re.search(
                    r'(Experimental arm[^|,\n]*|Comparative arm[^|,\n]*)',
                    row_text, re.IGNORECASE
                )
                if m_arm:
                    arm_text = m_arm.group(1).strip()

            if not is_experimental_arm(arm_text):
                continue  # pomijamy Comparative arm i nieznane

            # Wyciągnij GUID
            guid = None
            for el in row.find_all(onclick=True):
                m = re.search(r"GotoStudySubject\(['\"]([0-9a-f-]{36})['\"]", el.get("onclick", ""))
                if m:
                    guid = m.group(1)
                    break
            # Szukaj też w <a href>
            if not guid:
                for a in row.find_all("a", href=True):
                    m = re.search(r"StudySubject\.aspx\?ID=([0-9a-f-]{36})", a["href"])
                    if m:
                        guid = m.group(1)
                        break
            # Szukaj GUID w całym wierszu (onclick może być na <tr>)
            if not guid:
                for el in row.find_all(True):
                    oc = el.get("onclick", "")
                    m = re.search(r"GotoStudySubject\(['\"]([0-9a-f-]{36})['\"]", oc)
                    if m:
                        guid = m.group(1)
                        break

            patients.append((rand_num, arm_text, guid))

        if not rows:
            break  # pusta strona — koniec

        # Sprawdź paginację
        nxt_btns = ex.driver.find_elements(
            By.CSS_SELECTOR,
            "a[title='Next Page'], td[title='Next Page']"
        )
        if not nxt_btns:
            break
        nxt = nxt_btns[0]
        nxt_class = (nxt.get_attribute("class") or "").lower()
        if any(d in nxt_class for d in ("disabled", "dxp-bi", "dxp-disabledbutton")):
            break
        try:
            parent_class = (nxt.find_element(By.XPATH, "..").get_attribute("class") or "").lower()
            if any(d in parent_class for d in ("disabled", "dxp-bi", "dxp-disabledbutton")):
                break
        except Exception:
            pass
        nxt.click()
        ex._wait_dx(5)

    # Deduplicate
    seen = set()
    result = []
    for p in patients:
        if p[0] not in seen:
            seen.add(p[0])
            result.append(p)

    print(f"    Znaleziono {len(result)} pacjentów z Experimental arm")
    return result


def extract_patient_oct(ex: ECRFExtractor, rand_num: str, guid: str, site_num: str) -> dict:
    """
    Ekstrahuje dane OCT dla jednego pacjenta.
    Jeśli GUID nieznany — szuka przez find_patient_guid.
    Zwraca clean_json dict.
    """
    if not guid:
        # Fallback: szukaj GUID przez filtr BrowseSubjects
        guid = ex.find_patient_guid(rand_num, site_num)
        if not guid:
            raise ValueError(f"Nie znaleziono GUID dla {rand_num}")

    raw = ex.collect_patient_data(guid)
    patient_data = ex._build_patient_raw(rand_num, site_num, raw)
    return build_clean_json(patient_data)


def build_oct_csv(out_dir: Path, csv_name: str) -> None:
    """Buduje CSV z danymi OCT ze wszystkich plików JSON, pogrupowany po site i pacjencie."""
    rows = []
    json_files = sorted(out_dir.glob("result_*.json"))
    print(f"\nBudowanie bazy OCT z {len(json_files)} plików...")

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue

        p     = data.get("patient", {})
        rand  = p.get("randomization_number", jf.stem)
        site  = p.get("site", "—")
        arm   = p.get("arm") or "—"

        for v in data.get("vessels", []):
            if not v.get("oct_pre"):
                continue

            rows.append({
                "Site":                 site,
                "Patient_ID":           rand,
                "Arm":                  arm,
                "Vessel":               v.get("segment", "—"),
                "Culprit":              "TAK" if v.get("culprit") else "NIE",
                "Cewnik_OCT":           v.get("oct_catheter") or "—",
                "Pullback":             v.get("oct_pullback") or "—",
                "TCFA":                 _bool_str(v.get("oct_tcfa")),
                "Plaque_rupture":       _bool_str(v.get("oct_plaque_rupture")),
                "Plaque_erosion":       _bool_str(v.get("oct_plaque_erosion")),
                "MLA_mm2":              v.get("oct_mla_mm2"),
                "Stenoza_OCT_pct":      v.get("oct_pct_lumen_stenosis"),
                "Lesion_length_mm":     v.get("oct_lesion_length_mm"),
                "Prox_diam_mm":         v.get("oct_proximal_diam_mm"),
                "Dist_diam_mm":         v.get("oct_distal_diam_mm"),
                "FFR":                  v.get("ffr_adenosine"),
                "Pd_Pa":                v.get("pd_pa"),
                "RFR":                  v.get("rfr"),
                "Stenoza_angio_pct":    v.get("stenosis_pct"),
                "TIMI_pre":             v.get("timi_pre"),
                "TIMI_post":            v.get("timi_post"),
                "PCI":                  "TAK" if v.get("pci_performed") else "NIE",
                "Stent":                "TAK" if v.get("stent_placed") is True else "NIE",
            })

    if not rows:
        print("Brak naczyń z OCT — CSV pusty.")
        return

    # Posortuj po Site, potem Patient_ID
    rows.sort(key=lambda r: (str(r["Site"]).zfill(6), str(r["Patient_ID"])))

    csv_path = out_dir.parent / csv_name
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    # Statystyki
    sites_with_oct = set(r["Site"] for r in rows)
    pats_with_oct  = set(r["Patient_ID"] for r in rows)

    print(f"\n✅ Baza OCT zapisana: {csv_path}")
    print(f"   Sites z danymi OCT:   {len(sites_with_oct)}")
    print(f"   Pacjentów z OCT:      {len(pats_with_oct)}")
    print(f"   Naczyń z OCT:         {len(rows)}")


def _bool_str(val) -> str:
    if val is True:   return "TAK"
    if val is False:  return "NIE"
    return "—"


# ── Główna pętla ──────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}")
    print(f"  Ekstrakcja OCT — Experimental arm — WSZYSTKIE SITES")
    print(f"  Wyniki: {OUT_DIR}")
    print(f"{'='*60}\n")

    with ECRFExtractor(headless=False) as ex:
        # 1. Logowanie
        ex.login(LOGIN, PASSWORD)

        # 2. Pobierz wszystkie site'y
        all_sites = get_all_sites(ex)
        print(f"\n>>> {len(all_sites)} site'ów w studium\n")

        # 3. Zapis listy site'ów do pliku
        sites_file = OUT_DIR.parent / "lista_sitow.json"
        with open(sites_file, "w", encoding="utf-8") as f:
            json.dump(all_sites, f, ensure_ascii=False, indent=2)

        total_experimental = 0
        total_errors = 0
        total_ok = 0
        all_errors = []

        # 4. Dla każdego site'u
        for site_idx, (site_num, site_name) in enumerate(all_sites, 1):
            print(f"\n{'─'*55}")
            print(f"  [{site_idx}/{len(all_sites)}] Site {site_num} — {site_name}")
            print(f"{'─'*55}")

            # Utwórz folder per site
            site_dir = OUT_DIR / f"site_{site_num}"
            site_dir.mkdir(exist_ok=True)

            # Pobierz pacjentów z Experimental arm
            try:
                exp_patients = get_experimental_patients(ex, site_num)
            except Exception as e:
                print(f"  [!] Błąd pobierania pacjentów site {site_num}: {e}")
                all_errors.append((site_num, "LIST", str(e)))
                continue

            total_experimental += len(exp_patients)
            print(f"  Experimental arm: {len(exp_patients)} pacjentów")

            # 5. Ekstrakcja OCT dla każdego pacjenta
            for p_idx, (rand_num, arm, guid) in enumerate(exp_patients, 1):
                out_file = site_dir / f"result_{rand_num}.json"

                if out_file.exists():
                    print(f"  [{p_idx}/{len(exp_patients)}] {rand_num} — już pobrano, pomijam")
                    total_ok += 1
                    continue

                print(f"  [{p_idx}/{len(exp_patients)}] {rand_num}...", end=" ", flush=True)
                try:
                    # Pobierz GUID jeśli nieznany
                    if not guid:
                        guid = ex.find_patient_guid(rand_num, site_num)
                        if not guid:
                            raise ValueError("Nie znaleziono GUID")

                    # Zbierz sekcje CRF
                    sections = ex.collect_patient_data(guid)

                    # Parsuj naczynia
                    parts    = rand_num.split("-")
                    pat_num  = parts[1] if len(parts) > 1 else ""
                    vessels  = ex._parse_vessels(sections)

                    patient_data = PatientData(
                        randomization_number = rand_num,
                        site                 = site_num,
                        patient_number       = pat_num,
                        vessels              = vessels,
                        sections             = sections,
                    )
                    clean = build_clean_json(patient_data)

                    with open(out_file, "w", encoding="utf-8") as f:
                        json.dump(clean, f, ensure_ascii=False, indent=2)

                    oct_vessels = sum(1 for v in clean.get("vessels", []) if v.get("oct_pre"))
                    print(f"OK  (naczynia z OCT: {oct_vessels})")
                    total_ok += 1

                except Exception as e:
                    print(f"BŁĄD: {e}")
                    all_errors.append((rand_num, site_num, str(e)))
                    total_errors += 1
                    time.sleep(1)

    # 6. Podsumowanie
    print(f"\n\n{'='*60}")
    print(f"  PODSUMOWANIE")
    print(f"  Sites:        {len(all_sites)}")
    print(f"  Experimental: {total_experimental} pacjentów")
    print(f"  Pobrano OK:   {total_ok}")
    print(f"  Błędy:        {total_errors}")
    print(f"{'='*60}\n")

    # 7. Buduj CSV
    build_oct_csv(OUT_DIR, "baza_oct_experimental.csv")

    if all_errors:
        print("\nBłędy:")
        for item in all_errors:
            print(f"  {item}")


if __name__ == "__main__":
    main()
