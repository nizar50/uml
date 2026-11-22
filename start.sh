#!/bin/sh
cd "$(dirname "$0")"
[ -d venv ] || python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations comptes elearning
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
