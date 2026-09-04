@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ---------------------------------------------------------------------------
rem  hole-exe.cmd - laedt die aktuellste, von GitHub Actions gebaute
rem  py-esol.exe nach dist\ herunter.
rem
rem  Gebaut wird die EXE bei jedem Push auf main, aber nur wenn die Tests
rem  gruen sind. Gebraucht wird dafuer die GitHub CLI ("gh"), einmalig
rem  angemeldet mit:  gh auth login
rem
rem  Bewusst ohne Umlaute, damit die Ausgabe in jeder cmd-Codepage lesbar ist.
rem ---------------------------------------------------------------------------

set "WORKFLOW=tests.yml"
set "BRANCH=main"
set "ARTIFACT=py-esol-exe"
set "ZIEL=dist"

echo.
echo ==========================================================
echo   py-esol - aktuelle EXE von GitHub Actions holen
echo ==========================================================
echo.

where gh >nul 2>&1
if errorlevel 1 (
    echo FEHLER: Die GitHub CLI "gh" wurde nicht gefunden.
    echo.
    echo   Installieren:  winget install --id GitHub.cli
    echo   Danach einmal: gh auth login
    echo.
    echo Alternativ die EXE im Browser holen:
    echo   Repo -^> Actions -^> letzter CI-Lauf auf main -^> Artifacts -^> py-esol-exe
    echo.
    pause
    exit /b 1
)

gh auth status >nul 2>&1
if errorlevel 1 (
    echo FEHLER: "gh" ist nicht angemeldet.
    echo.
    echo   Bitte einmalig ausfuehren:  gh auth login
    echo.
    pause
    exit /b 1
)

echo Suche letzten erfolgreichen CI-Lauf auf Branch "%BRANCH%" ...
set "RUN_ID="
for /f "usebackq delims=" %%i in (`gh run list --workflow %WORKFLOW% --branch %BRANCH% --status success --limit 1 --json databaseId --jq ".[0].databaseId"`) do set "RUN_ID=%%i"

if not defined RUN_ID (
    echo.
    echo FEHLER: Kein erfolgreicher Lauf gefunden.
    echo.
    echo Moegliche Ursachen:
    echo   - Es wurde noch nichts nach %BRANCH% gepusht.
    echo   - Der letzte Lauf ist rot ^(Tests fehlgeschlagen^) - dann gibt es
    echo     absichtlich keine EXE. Erst die Tests reparieren.
    echo   - Die Workflow-Datei heisst nicht %WORKFLOW%.
    echo.
    pause
    exit /b 1
)

echo Gefundener Lauf: %RUN_ID%
echo.

if not exist "%ZIEL%" mkdir "%ZIEL%"
if exist "%ZIEL%\py-esol.exe" (
    echo Vorhandene %ZIEL%\py-esol.exe wird ersetzt.
    del /q "%ZIEL%\py-esol.exe"
    if exist "%ZIEL%\py-esol.exe" (
        echo.
        echo FEHLER: %ZIEL%\py-esol.exe laesst sich nicht loeschen.
        echo Laeuft das Programm noch? Bitte schliessen und erneut versuchen.
        echo.
        pause
        exit /b 1
    )
)

echo Lade Artefakt "%ARTIFACT%" herunter ...
gh run download %RUN_ID% --name %ARTIFACT% --dir "%ZIEL%"
if errorlevel 1 (
    echo.
    echo FEHLER: Download fehlgeschlagen.
    echo.
    echo Haeufigste Ursache: Artefakte verfallen nach 90 Tagen. Dann einmal
    echo etwas nach %BRANCH% pushen oder den Workflow manuell starten:
    echo   gh workflow run %WORKFLOW% --ref %BRANCH%
    echo.
    pause
    exit /b 1
)

if not exist "%ZIEL%\py-esol.exe" (
    echo.
    echo FEHLER: Der Download hat keine py-esol.exe geliefert.
    echo Inhalt von %ZIEL%:
    dir /b "%ZIEL%"
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================================
echo   Fertig:  %CD%\%ZIEL%\py-esol.exe
echo ==========================================================
echo.
echo Diese Datei kann so an die Mitarbeiter weitergegeben werden -
echo sie braucht auf dem Zielrechner kein Python und keine IDE.
echo.
echo Hinweis: Beim ersten Start warnt Windows SmartScreen bei nicht
echo signierten Programmen. "Weitere Informationen" -^> "Trotzdem
echo ausfuehren". Das verschwindet erst mit einem Code-Signing-Zertifikat.
echo.
pause
