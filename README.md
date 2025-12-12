VULOR — Clothing E-Commerce Platform (Django + Tailwind + Paystack)

VULOR is a full-stack e-commerce web application built with Django, Tailwind CSS, JavaScript, and Paystack for payments.
It supports product listings, shopping cart, orders, payments, user accounts, and admin dashboards.

This repository is structured for clean collaboration, deployment, and scalability.

🚀 Features
Frontend

Clean Tailwind-powered UI

Product pages with dynamic sizes/colors

Cart system

Checkout flow

Google Login (via Django Allauth)

Backend

Django 6 + PostgreSQL / SQLite

Paystack full integration (initialize + verify)

Orders + Payment models

Custom dashboard for admin actions

Product management w/ images & variations

Review & rating system

Notifications (Django messages)

🏗 Tech Stack

Backend: Django 6, Django Allauth, Paystack API
Frontend: Tailwind CSS, JavaScript
Database: SQLite / PostgreSQL
Auth: Email + Google OAuth
Payments: Paystack

📁 Project Structure
vulor/
├── accounts/        # Authentication + Google login
├── cart/            # Cart logic
├── dashboard/       # Admin dashboard UI
├── frontend/        # Templates + static files
├── orders/          # Orders + receipts
├── payments/        # Paystack integration
├── products/        # Product models + reviews
├── media/           # Uploaded images (ignored by git)
└── vulor/           # Project settings

🔧 Local Setup
1️⃣ Clone the repo
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>

2️⃣ Create virtual environment
python -m venv venv
venv\Scripts\activate

3️⃣ Install dependencies
pip install -r requirements.txt

4️⃣ Create .env

Copy:

cp .env.example .env


Fill with your secrets (DO NOT commit .env).

5️⃣ Run migrations
python manage.py migrate

6️⃣ Run developer server
python manage.py runserver

💳 Paystack Setup

Inside .env:

PAYSTACK_PUBLIC_KEY=pk_test_xxxxxx
PAYSTACK_SECRET_KEY=sk_test_xxxxxx
PAYSTACK_WEBHOOK_SECRET=whsec_xxxxxx


Make sure your redirect/callback URL matches:

http://127.0.0.1:8000/payments/verify/

🔐 Google Login Setup

Add these to .env:

GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxxxx


If you've seen up to this part just tell me when you've cloned it and I'll
send the .env files through whatsapp



Enable OAuth consent → whitelist:

http://127.0.0.1:8000/accounts/google/login/callback/
