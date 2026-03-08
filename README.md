
# Kolige Premier League Auction Engine

Django based cricket auction engine.

## Setup

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python manage.py migrate
python load_demo_data.py
python manage.py runserver

## URLs

/
 /auction/
 /auction/upload-csv/
 /auction/audit-log/
 /auction/reset/
 /jersey/
 /admin/
