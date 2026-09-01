@echo off
REM Pipeline automatico del lunes 08:00 (Ecuador) para sesion NY de ICT SYSTEM.
REM 1) Actualiza data/raw con la punta en vivo de MT5 (mismo terminal que SMC-SYSTEMS).
REM 2) Genera el brief de lectura ICT/WYCKOFF con el motor (venv de ICT SYSTEM).
REM Requisito: terminal FundedNext MT5 ABIERTA y LOGUEADA.

set ROOT=C:\Users\v_jac\Desktop\ICT SYSTEM
set SYS_PY=C:\Python314\python.exe
set VENV_PY=%ROOT%\.venv\Scripts\python.exe
set UPD=%ROOT%\scripts\update_mt5_ict.py
set BRIEF=%ROOT%\scripts\brief_lunes.py

echo [1/2] Actualizando datos MT5...
"%SYS_PY%" "%UPD%" --symbols "EURUSD GBPUSD XAUUSD USDJPY" --tfs "M1 M5 M15 H1 H4 D1"
if errorlevel 1 echo [WARN] update_mt5 fallo (¿MT5 cerrado?) — el brief usara data/raw previa.

echo [2/2] Generando brief...
"%VENV_PY%" "%BRIEF%" --symbols EURUSD GBPUSD XAUUSD USDJPY
exit /b %errorlevel%
