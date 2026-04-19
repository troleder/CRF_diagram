#!/bin/bash
# =====================================================
#  eCRF Diagram – uruchom dwuklikiem w Finderze
# =====================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo ""
echo "======================================"
echo "  eCRF Diagram – Uruchamianie"
echo "======================================"
echo ""

# Instaluj zależności jeśli brakuje
echo "Sprawdzam zależności..."
pip3 install -q -r requirements.txt

echo ""
echo "Adres aplikacji: http://localhost:5555"
echo "Aby zatrzymać: Ctrl+C lub zamknij okno"
echo ""

python3 app.py
