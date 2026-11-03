@echo off
REM nicebot: PyPI'ga yuklash va hujjat saytini surge.sh'ga joylash (Windows)
cd /d %~dp0
echo.
echo === 1/2  PyPI: token so'ralganda pypi-... bilan boshlanadigan tokenni kiriting ===
python -m pip install --upgrade twine
python -m twine upload dist/*
echo.
echo === 2/2  surge.sh: birinchi marta email va parol so'raydi (akkaunt shu yerda ochiladi) ===
call npx --yes surge site nicebot-docs.surge.sh
echo.
echo Tayyor!  https://pypi.org/project/nicebot/   va   https://nicebot-docs.surge.sh
pause
