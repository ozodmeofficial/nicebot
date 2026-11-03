#!/usr/bin/env bash
# nicebot: PyPI'ga yuklash va hujjat saytini surge.sh'ga joylash (macOS / Linux)
set -e
cd "$(dirname "$0")"
echo "=== 1/2  PyPI: token so'ralganda pypi-... bilan boshlanadigan tokenni kiriting ==="
python3 -m pip install --upgrade twine
python3 -m twine upload dist/*
echo "=== 2/2  surge.sh: birinchi marta email va parol so'raydi (akkaunt shu yerda ochiladi) ==="
npx --yes surge site nicebot-docs.surge.sh
echo "Tayyor!  https://pypi.org/project/nicebot/  va  https://nicebot-docs.surge.sh"
