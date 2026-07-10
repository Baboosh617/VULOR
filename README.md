# VULOR

VULOR is a full-stack e-commerce web application for a fashion brand, built with
Django, Tailwind CSS, vanilla JavaScript, and Paystack for payments. It supports
product listings, a shopping cart, orders, payments, user accounts (email + Google
OAuth), and an admin dashboard.

Prices are denominated in Nigerian Naira (₦).

## Tech Stack

- **Backend:** Django 5.0.4, django-allauth (email + Google OAuth), Paystack API
- **Async / scheduling:** Celery 5.6 + Redis, django-celery-beat (weekly sales report)
- **Frontend:** Tailwind CSS (django-tailwind), vanilla JS (`cart.js`, `toast.js`)
- **Database:** PostgreSQL (production) / SQLite (local development)
- **Media / static:** WhiteNoise + gunicorn in production
- **Deployment:** Render (`render.yaml`) or self-hosted via Docker (`docker-compose.yaml`)

## Features

- Product catalog with categories, sizes, colors, and per-category measurements
- Customer reviews with moderation (admin approval) and aggregate ratings
- Shopping cart with per-item size/color variants
- Checkout with shipping details and Paystack payment integration
- Order lifecycle (pending → processing → shipped → completed / cancelled) with
  automated email notifications and inventory adjustment
- Email + Google OAuth authentication (django-allauth)
- Custom admin dashboard (products, orders, customers, reviews)
- Custom error pages (400/403/404/500) in production
- Celery-driven weekly sales report emailed to the store admin

## Project Structure

```
VULOR/
├── accounts/        # CustomUser, signup/social forms, auth signals
├── products/        # Product, Review, Category, ProductImage, StoreReview
├── cart/            # Cart, CartItem, context processor
├── orders/          # Order, OrderItem, status/payment signals
├── payments/        # Payment, PaymentTransaction (Paystack)
├── dashboard/       # Custom admin UI (not Django admin)
├── services/        # email_service, inventory_service, admin_report_service, tasks
├── error_pages/     # Custom HTTP error handlers
├── frontend/        # Tailwind templates, static assets, email templates
├── vulor/           # Django project settings, URLs, WSGI/ASGI
├── docker-compose.yaml
├── docker-file.dockerfile
├── nginx.conf
├── render.yaml
├── requirements.txt
└── manage.py
```

## Local Development

### Prerequisites

- Python 3.11+
- (Optional) Redis, for running Celery workers locally

### Setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root (see **Environment Variables** below).

4. Apply migrations and run the development server:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

   The site is served at `http://127.0.0.1:8000`.

5. (Optional) Run Celery worker and beat scheduler:

   ```bash
   celery -A vulor worker --loglevel=info
   celery -A vulor beat --loglevel=info
   ```

## Environment Variables

Create a `.env` file in the project root. Key variables:

| Variable | Description |
| --- | --- |
| `SECRET_KEY` | Django secret key |
| `DEBUG` | Set automatically from `ON_RENDER` (True locally, False on Render) |
| `DATABASE_URL` | PostgreSQL connection string (used on Render) |
| `PAYSTACK_SECRET_KEY` | Paystack secret key |
| `PAYSTACK_PUBLIC_KEY` | Paystack public key |
| `PAYSTACK_WEBHOOK_SECRET` | Paystack webhook secret |
| `SITE_URL` | Public site URL (default `http://127.0.0.1:8000`) |
| `GOOGLE_CLIENT_ID` | Google OAuth client id |
| `GOOGLE_SECRET_KEY` | Google OAuth secret |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP credentials for sending mail |
| `ADMIN_EMAIL` | Recipient for admin / sales-report emails |
| `REDIS_URL` | Redis connection string for cache/broker |
| `ON_RENDER` | `True` when running on Render (flips DB + security settings) |
| `ADMIN_URL` | Admin URL prefix (default `admin/`) |

## Running Tests

```bash
python manage.py test
```

Tests use SQLite and an in-memory email backend, so no external services are
required. `SECRET_KEY` must be set (via `.env` or environment).

## Deployment

### Render

`render.yaml` defines a Python web service that installs dependencies, runs
`collectstatic` and `migrate` at build time, and starts gunicorn at runtime.
Set `ON_RENDER=True` and provide the environment variables above. A managed
PostgreSQL database is provisioned automatically.

### Docker (self-hosted)

`docker-compose.yaml` spins up `web` (gunicorn + nginx), `db` (PostgreSQL),
`redis`, `celery`, and `celery-beat`. Configure `nginx.conf` and supply
`.env.production` (referenced by the compose services).
