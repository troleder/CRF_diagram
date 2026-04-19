#!/bin/bash
# =====================================================
#  eCRF Diagram – Start aplikacji
# =====================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo ""
echo "======================================"
echo "  eCRF Diagram – Uruchamianie"
echo "======================================"
echo ""
echo "Adres aplikacji: http://localhost:5555"
echo "Aby zatrzymać: Ctrl+C"
echo ""

python3 app.py
