# Django promocode orders API

`POST /api/orders/` creates an order and optionally applies a promo code.

Python 3.10+ / Django 4.2+ / Django REST Framework.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run tests

```bash
pytest
```

Or a single file:

```bash
pytest tests/test_orders_api.py
```

The suite uses pytest-django with SQLite (`config.settings`).

## Run the API

```bash
python manage.py migrate
python manage.py runserver
```
