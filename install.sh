#!/bin/bash
# =====================================================
#  eCRF Diagram – Skrypt instalacyjny (macOS)
# =====================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "======================================"
echo "  eCRF Diagram – Instalacja (macOS)"
echo "======================================"
echo ""

# 1. Sprawdź Python 3
echo "[ 1/4 ] Sprawdzam Python 3..."
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}BŁĄD: Python 3 nie jest zainstalowany.${NC}"
    echo "Pobierz ze strony: https://www.python.org/downloads/"
    exit 1
fi
PY=$(python3 --version)
echo -e "${GREEN}OK – $PY${NC}"

# 2. Sprawdź pip
echo ""
echo "[ 2/4 ] Sprawdzam pip..."
if ! python3 -m pip --version &>/dev/null; then
    echo "Instaluję pip..."
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3
fi
echo -e "${GREEN}OK – $(python3 -m pip --version)${NC}"

# 3. Zainstaluj zależności Python
echo ""
echo "[ 3/4 ] Instaluję zależności Python..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install -r requirements.txt --quiet
echo -e "${GREEN}OK – wszystkie pakiety zainstalowane${NC}"

# 4. Sprawdź Google Chrome
echo ""
echo "[ 4/4 ] Sprawdzam Google Chrome..."
if [ -d "/Applications/Google Chrome.app" ]; then
    CHROME_VER=$(/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version 2>/dev/null || echo "nieznana")
    echo -e "${GREEN}OK – $CHROME_VER${NC}"
    echo -e "${YELLOW}Uwaga: webdriver-manager automatycznie pobierze odpowiednią wersję ChromeDriver.${NC}"
else
    echo -e "${YELLOW}UWAGA: Google Chrome nie znaleziony w /Applications.${NC}"
    echo "Pobierz ze strony: https://www.google.com/chrome/"
    echo "Aplikacja może nie działać bez przeglądarki Chrome."
fi

echo ""
echo "======================================"
echo -e "${GREEN}  Instalacja zakończona pomyślnie!${NC}"
echo "======================================"
echo ""
echo "Uruchom aplikację komendą:"
echo "  ./start.sh"
echo ""
echo "lub:"
echo "  python3 app.py"
echo ""
echo "Następnie otwórz przeglądarkę pod adresem:"
echo "  http://localhost:5555"
echo ""
