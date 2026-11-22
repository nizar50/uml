@echo off
setlocal
cd /d "%~dp0"
echo === Plateforme e-learning adaptative ===

if not exist venv\Scripts\activate.bat (
    echo Creation de l'environnement virtuel...
    py -3.13 -m venv venv 2>nul
    if not exist venv\Scripts\activate.bat python -m venv venv
)
if not exist venv\Scripts\activate.bat (
    echo ERREUR : Python introuvable. Installez Python 3.12 ou 3.13 puis relancez.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo Installation des dependances...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERREUR pendant l'installation des dependances.
    pause
    exit /b 1
)

python manage.py makemigrations comptes elearning
python manage.py migrate
python manage.py seed_demo

echo.
echo Ouverture du site : http://127.0.0.1:8000
start "" http://127.0.0.1:8000
python manage.py runserver
pause
