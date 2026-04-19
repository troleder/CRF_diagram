# eCRF Diagram – Ekstraktor danych angiograficznych

Aplikacja webowa do ekstrakcji danych z formularza eCRF Diagram.

## Wymagania systemowe

- macOS 12 lub nowszy
- **Google Chrome** (pobierz z: https://www.google.com/chrome/)
- **Python 3.9+** (pobierz z: https://www.python.org/downloads/)

## Instalacja (jednorazowo)

Otwórz **Terminal**, przejdź do folderu z aplikacją i uruchom:

```bash
cd ~/Downloads/ecrf-diagram-app
chmod +x install.sh start.sh
./install.sh
```

Skrypt automatycznie zainstaluje wszystkie potrzebne pakiety Python.  
ChromeDriver jest pobierany automatycznie przez `webdriver-manager`.

## Uruchomienie

```bash
./start.sh
```

Następnie otwórz przeglądarkę pod adresem:

**http://localhost:5555**

## Pliki aplikacji

| Plik | Opis |
|------|------|
| `app.py` | Serwer Flask – interfejs webowy |
| `ecrf_extractor.py` | Silnik ekstrakcji danych (Selenium) |
| `run_patient.py` | Skrypt CLI do uruchamiania z terminala |
| `export_clean_json.py` | Eksport danych do JSON |
| `install.sh` | Skrypt instalacyjny (jednorazowy) |
| `start.sh` | Skrypt startowy aplikacji |

## Użycie z linii komend (opcjonalnie)

```bash
# Pobierz dane dla pacjenta
python3 run_patient.py --patient 1701-0030 --login TWOJ_LOGIN --password TWOJE_HASLO

# Zapis do pliku JSON
python3 run_patient.py --patient 1701-0030 --login LOGIN --password PASS --output wyniki.json

# Tryb headless (bez okna przeglądarki)
python3 run_patient.py --patient 1701-0030 --login LOGIN --password PASS --headless
```

## Zmienne środowiskowe (zamiast podawania hasła w komendzie)

```bash
export ECRF_LOGIN="twoj_login"
export ECRF_PASSWORD="twoje_haslo"
python3 run_patient.py --patient 1701-0030
```

## Rozwiązywanie problemów

**Problem:** `chromedriver` nie pasuje do wersji Chrome  
**Rozwiązanie:** Zaktualizuj Chrome do najnowszej wersji lub uruchom ponownie `./install.sh`

**Problem:** Port 5555 zajęty  
**Rozwiązanie:** Zmień port w `app.py` (ostatnia linia: `port=5555`)

**Problem:** Błąd SSL / połączenia  
**Rozwiązanie:** Sprawdź połączenie z internetem i dostęp do systemu eCRF
