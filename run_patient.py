"""
Skrypt dedykowany do wyciągnięcia danych dla konkretnego pacjenta z eCRF Diagram.
Używa Selenium z pełnym czekaniem na JavaScript/AJAX.
"""

import time
import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

STUDY_ID   = "4b40cced-3ab5-4f05-91bb-4a2f9bcc9b74"
BASE_URL   = "https://www.ecrfdiagram.com/eCRF"
STUDY_URL  = f"{BASE_URL}/Study.aspx?ID={STUDY_ID}"

LOGIN    = "roledert"
PASSWORD = "Chorwacja2023@"
PATIENT  = "1701-0030"


def wait_no_loading(driver, timeout=20):
    """Czeka aż zniknie 'Loading...' z DOM."""
    try:
        WebDriverWait(driver, timeout).until_not(
            lambda d: "Loading…" in d.page_source or "Loading..." in d.page_source
        )
    except TimeoutException:
        pass
    time.sleep(1)


def dump_html(driver, fname):
    with open(fname, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"  → HTML zapisany: {fname}")


def screenshot(driver, fname):
    driver.save_screenshot(fname)
    print(f"  → Screenshot: {fname}")


def get_all_text_fields(driver):
    """Zbiera wszystkie widoczne pary label→wartość ze strony."""
    soup = BeautifulSoup(driver.page_source, "lxml")
    result = {}

    # Pary z tabel (th/td lub td/td)
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) == 2:
                k = cells[0].get_text(" ", strip=True)
                v = cells[1].get_text(" ", strip=True)
                if k and v and len(k) < 100:
                    result[k] = v
            elif len(cells) > 2:
                # Wiersz z wieloma kolumnami — zapisz wszystkie
                texts = [c.get_text(" ", strip=True) for c in cells]
                if any(texts):
                    result[f"row_{len(result)}"] = " | ".join(t for t in texts if t)

    # Label + input/select
    for label in soup.find_all("label"):
        k = label.get_text(strip=True)
        if not k:
            continue
        for_id = label.get("for")
        v = ""
        if for_id:
            el = soup.find(id=for_id)
            if el:
                if el.name == "select":
                    opt = el.find("option", selected=True)
                    v = opt.get_text(strip=True) if opt else ""
                elif el.name == "input":
                    v = el.get("value", "")
                else:
                    v = el.get_text(strip=True)
        if k and v:
            result[k] = v

    # Span/div z wartościami (DevExpress style)
    for el in soup.find_all(["span", "div"],
                             class_=re.compile(r"dx-field|dxeLabel|dxeEdit|field-value|"
                                               r"readonly|display-field", re.I)):
        k = el.get_text(strip=True)
        if k and len(k) < 200:
            result[f"span_{len(result)}"] = k

    return result


def click_patient_in_list(driver, patient_number):
    """Klikaj na pacjenta w liście po numerze randomizacji."""
    wait = WebDriverWait(driver, 20)

    # Czekaj na załadowanie listy pacjentów
    wait_no_loading(driver, 30)
    screenshot(driver, "after_login.png")

    # Szukaj w tabeli/gridzie
    page = driver.page_source
    soup = BeautifulSoup(page, "lxml")

    # Szukaj linku zawierającego numer randomizacji
    for a in soup.find_all("a"):
        text = a.get_text(strip=True)
        href = a.get("href", "")
        if patient_number in text or patient_number in href:
            print(f"  Znaleziono link: '{text}' → {href}")
            full_url = href if href.startswith("http") else BASE_URL + "/" + href.lstrip("/")
            driver.get(full_url)
            wait_no_loading(driver, 30)
            return True

    # Szukaj w komórkach tabeli
    for row in soup.find_all("tr"):
        row_text = row.get_text()
        if patient_number in row_text:
            link = row.find("a")
            if link and link.get("href"):
                href = link["href"]
                full_url = href if href.startswith("http") else BASE_URL + "/" + href.lstrip("/")
                print(f"  Znaleziono wiersz → {full_url}")
                driver.get(full_url)
                wait_no_loading(driver, 30)
                return True
            else:
                # Spróbuj kliknąć pierwszą komórkę z linkiem
                try:
                    cells = driver.find_elements(By.XPATH, "//tr[contains(., '" + patient_number + "')]//td")
                    if cells:
                        cells[0].click()
                        wait_no_loading(driver, 20)
                        return True
                except Exception as e:
                    print(f"  Błąd kliknięcia: {e}")

    return False


def navigate_to_patient(driver, patient_number):
    """Nawiguje do formularza pacjenta różnymi metodami."""
    wait = WebDriverWait(driver, 20)

    # Metoda 1: URL z parametrem randomization
    url = f"{STUDY_URL}&randomization={patient_number}"
    print(f"\n[1] Próba URL: {url}")
    driver.get(url)
    wait_no_loading(driver, 30)
    screenshot(driver, "method1.png")

    if patient_number in driver.current_url or patient_number in driver.page_source:
        print("  → Pacjent znaleziony przez URL!")
        return True

    # Metoda 2: Wyszukaj przez pole wyszukiwania
    print(f"\n[2] Szukam pola wyszukiwania...")
    search_selectors = [
        "input[id*='SearchText']",
        "input[id*='search']",
        "input[placeholder*='patient']",
        "input[placeholder*='subject']",
    ]
    for sel in search_selectors:
        try:
            field = driver.find_element(By.CSS_SELECTOR, sel)
            field.clear()
            field.send_keys(patient_number)
            time.sleep(1)
            # Kliknij Enter lub przycisk szukaj
            field.submit()
            time.sleep(2)
            wait_no_loading(driver)
            screenshot(driver, "method2.png")
            if patient_number in driver.page_source:
                print(f"  → Znaleziony przez wyszukiwanie ({sel})")
                return click_patient_in_list(driver, patient_number)
        except NoSuchElementException:
            continue

    # Metoda 3: JavaScript — szukaj w gridzie DevExpress
    print(f"\n[3] Szukam przez JavaScript w gridzie...")
    try:
        # DevExpress grid często ma metodę PerformCallback
        js = f"""
        var grids = document.querySelectorAll('[id*="grid"], [id*="Grid"], [id*="subject"]');
        console.log('Gridy:', grids.length);
        grids.forEach(function(g) {{ console.log(g.id); }});
        """
        driver.execute_script(js)
        time.sleep(1)
    except Exception as e:
        print(f"  JS error: {e}")

    # Metoda 4: Kliknij bezpośrednio na pacjenta w liście
    return click_patient_in_list(driver, patient_number)


def extract_crf_sections(driver):
    """Przechodzi przez wszystkie sekcje CRF i zbiera dane."""
    all_data = {}
    wait = WebDriverWait(driver, 15)
    wait_no_loading(driver, 30)

    # Zapisz aktualny URL jako bazowy dla pacjenta
    base_patient_url = driver.current_url
    print(f"\n[*] URL pacjenta: {base_patient_url}")
    screenshot(driver, "patient_form.png")
    dump_html(driver, "patient_form.html")

    # Zbierz dane z bieżącej strony
    page_fields = get_all_text_fields(driver)
    all_data["main"] = page_fields
    print(f"  Strona główna: {len(page_fields)} pól")

    # Znajdź zakładki / sekcje
    soup = BeautifulSoup(driver.page_source, "lxml")

    # Zbierz wszystkie linki wewnętrzne
    section_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        # Linki do sekcji CRF (zazwyczaj mają page= lub section= lub są podobne do CRF.aspx)
        if any(x in href.lower() for x in ["page=", "section=", "form=", "crf", "subject"]):
            if not any(x in href.lower() for x in ["logoff", "contact", "password", "report"]):
                section_links.append((text, href))

    # Zakładki (tabs)
    tab_elements = driver.find_elements(By.CSS_SELECTOR,
        "li.tab-item a, ul.nav-tabs a, .dxpc-tab, a[id*='tab'], "
        "td[id*='tab'] a, [role='tab'] a, .tabPage a")

    if tab_elements:
        print(f"\n[*] Znaleziono {len(tab_elements)} zakładek")
        for i, tab in enumerate(tab_elements):
            tab_text = tab.text.strip()
            print(f"\n  Zakładka [{i+1}]: {tab_text}")
            try:
                driver.execute_script("arguments[0].scrollIntoView();", tab)
                tab.click()
                wait_no_loading(driver, 20)
                time.sleep(1.5)
                tab_fields = get_all_text_fields(driver)
                all_data[f"tab_{i}_{tab_text}"] = tab_fields
                print(f"    → {len(tab_fields)} pól")
                screenshot(driver, f"tab_{i}_{tab_text[:20].replace(' ','_')}.png")
            except Exception as e:
                print(f"    [!] Błąd: {e}")

    if section_links:
        print(f"\n[*] Znaleziono {len(section_links)} sekcji do odwiedzenia")
        visited = set()
        for text, href in section_links[:20]:
            full_url = href if href.startswith("http") else BASE_URL + "/" + href.lstrip("/")
            if full_url in visited:
                continue
            visited.add(full_url)
            print(f"\n  Sekcja: {text} → {full_url}")
            try:
                driver.get(full_url)
                wait_no_loading(driver, 20)
                sec_fields = get_all_text_fields(driver)
                all_data[f"section_{text}"] = sec_fields
                print(f"    → {len(sec_fields)} pól")
                driver.back()
                wait_no_loading(driver)
            except Exception as e:
                print(f"    [!] Błąd: {e}")

    return all_data


def parse_angio_data(all_data):
    """Parsuje zebrane dane i wyciąga informacje angiograficzne."""

    # Spłaszcz wszystkie pola do jednego słownika
    flat = {}
    for section, fields in all_data.items():
        for k, v in fields.items():
            flat[f"{section} :: {k}"] = v

    print(f"\n{'='*65}")
    print(f"  WSZYSTKIE ZEBRANE POLA ({len(flat)} łącznie):")
    print(f"{'='*65}")
    for k, v in sorted(flat.items()):
        print(f"  {k[:70]}: {v[:80]}")

    return flat


def main():
    opts = Options()
    # opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(5)

    try:
        # ── Logowanie ──────────────────────────────────────────────────
        print(f"\n{'='*65}")
        print(f"  eCRF Diagram – Pacjent: {PATIENT}")
        print(f"{'='*65}")

        print(f"\n[*] Nawiguję do: {STUDY_URL}")
        driver.get(STUDY_URL)
        wait_no_loading(driver, 30)

        print("[*] Loguję się...")

        # Sprawdź czy jest formularz logowania
        try:
            user_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                    "input[id*='user'], input[id*='User'], input[id*='login'], "
                    "input[id*='Login'], input[name*='user'], input[name*='UserName']"))
            )
            pass_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            user_field.clear()
            user_field.send_keys(LOGIN)
            pass_field.clear()
            pass_field.send_keys(PASSWORD)

            # Przycisk
            for sel in ["input[type='submit']", "button[type='submit']",
                        "input[id*='Submit']", "input[id*='Login']",
                        "button[id*='Login']", "a[id*='login']"]:
                try:
                    btn = driver.find_element(By.CSS_SELECTOR, sel)
                    btn.click()
                    break
                except NoSuchElementException:
                    continue
            else:
                pass_field.submit()

            wait_no_loading(driver, 30)
            print(f"  → Zalogowano. URL: {driver.current_url}")

        except TimeoutException:
            print("  → Formularz logowania nie znaleziony — może sesja aktywna")

        screenshot(driver, "01_after_login.png")

        # ── Nawigacja do pacjenta ──────────────────────────────────────
        found = navigate_to_patient(driver, PATIENT)
        if not found:
            print(f"\n[!] Nie udało się automatycznie znaleźć pacjenta {PATIENT}")
            print("    Sprawdź screenshot 'method1.png', 'method2.png'")

        # ── Ekstrakcja danych ─────────────────────────────────────────
        all_data = extract_crf_sections(driver)

        # ── Parsowanie ────────────────────────────────────────────────
        flat_data = parse_angio_data(all_data)

        # Zapisz do JSON
        out = {"patient": PATIENT, "sections": all_data, "flat": flat_data}
        with open(f"data_{PATIENT}.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n[*] Dane zapisane: data_{PATIENT}.json")

    finally:
        time.sleep(3)  # chwila żeby zobaczyć ekran
        driver.quit()


if __name__ == "__main__":
    main()
