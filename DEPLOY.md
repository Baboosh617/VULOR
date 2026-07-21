VULOR Deployment Guide — Render Starter ($7/mo) + Supabase Free
=================================================================

Cost Breakdown
--------------

  • Render Web Service (Starter — 0.5 vCPU, 512 MB RAM) ......... $7.00/mo
  • Supabase PostgreSQL (Free — 500 MB, always-on) .............. $0
  • Render Persistent Disk (1 GB for payment receipts) .......... $0.25/mo
  • ---------------------------------------------------------------
  • Total ........................................................ $7.25/mo

No Celery, no Redis. Emails go out synchronously (the app already
defaults to EMAIL_ASYNC_ENABLED=False — no extra config needed).
The weekly sales report is run manually via Shell when desired.

Why This Setup Works Without Changes
-------------------------------------

The app's settings.py already handles everything needed:

  1. Database: when ON_RENDER=True, it reads DATABASE_URL and
     connects to any PostgreSQL provider (Supabase, Neon, etc.)
     via dj_database_url with SSL required.
  2. Caching: LocMemCache is the built-in fallback when no REDIS_URL
     is set — no Redis dependency for rate-limiting or sessions.
  3. Emails: EMAIL_ASYNC_ENABLED defaults to False, so all customer
     emails (order confirmation, shipping updates, password resets)
     send synchronously over SMTP during the request.
  4. Media: product images are tracked in git and live under
     media/products/. Payment receipts go to media/payment_receipts/
     which is gitignored and lives on the persistent disk.

The only file changed is render.yaml — settings.py stays untouched.

---

STEP 1 — Create the Supabase Database
---------------------------------------

  1. Go to https://supabase.com and sign up (free, no credit card)

  2. Create a new project:
       Name:       vulor
       Password:   generate a strong one — save it immediately
       Region:     pick the same region Render will use (us-east-1
                   / Ohio is a safe choice for Render's us-east
                   region)
       Wait ~2 minutes for provisioning to finish.

  3. Go to Project Settings → Database → Connection string

  4. Copy the Session pooler string (port 5432 — IPv4 compatible):
       postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-[REGION].pooler.supabase.com:5432/postgres
     Keep this handy for Step 3.

---

STEP 2 — Generate Django Secret Key
--------------------------------------

Run this in your terminal (anywhere with Django installed, or just
use Python directly):

    python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

Copy the long random string that prints out.

---

STEP 3 — Deploy to Render
---------------------------

  1. Push your repo to GitHub if you haven't already:
       git remote add origin https://github.com/YOUR_USER/vulor.git
       git push -u origin main

  2. Go to https://dashboard.render.com → New + → Blueprint

  3. Connect your GitHub repo — Render reads render.yaml and
     auto-detects the service configuration.

  4. Before the first deploy completes, go to your new Render web
     service → Environment tab → add these variables.
     Paste them in as "Secret Files" or individual env vars:

     Variable                    Value
     ─────────────────────────────────────────────────────────────
     SECRET_KEY                  The key from Step 2
     DATABASE_URL                The Supabase connection string
     BANK_TRANSFER_BANK_NAME     e.g. "GTBank"
     BANK_TRANSFER_ACCOUNT_NAME  e.g. "VULOR Store"
     BANK_TRANSFER_ACCOUNT_NUMBER Your bank account number
     GOOGLE_CLIENT_ID            Your Google OAuth client ID
     GOOGLE_CLIENT_SECRET        Your Google OAuth client secret
     EMAIL_HOST                  Your SMTP server hostname
     EMAIL_HOST_USER             SMTP login username
     EMAIL_HOST_PASSWORD         SMTP login password
     DEFAULT_FROM_EMAIL          e.g. "VULOR <noreply@your.com>"
     ADMIN_EMAIL                 Where you get admin notifications

     The render.yaml already sets these automatically:
       DJANGO_SETTINGS_MODULE  → vulor.settings
       PORT                    → 10000
       ON_RENDER               → True
       DEBUG                   → False
       ALLOWED_HOSTS           → vulor.onrender.com
       CSRF_TRUSTED_ORIGINS    → https://vulor.onrender.com
       SITE_URL                → https://vulor.onrender.com
       EMAIL_PORT              → 587
       EMAIL_USE_TLS           → True
       EMAIL_ASYNC_ENABLED     → False

  5. Verify the Persistent Disk: go to the Disks tab on your
     service and confirm there's a 1 GB disk named "receipts"
     mounted at /app/media/payment_receipts (defined in render.yaml)

  6. Click Deploy Blueprint and wait 5-10 minutes. The build runs:
       • pip install -r requirements.txt
       • npm ci && npm run build:css (compiles Tailwind)
       • python manage.py collectstatic --noinput --clear
       • python manage.py migrate --noinput (creates all tables
         on Supabase)

---

STEP 4 — Post-Deploy Setup
----------------------------

4a — Create admin account

  In the Render dashboard → your web service → Shell tab, run:

    python manage.py createsuperuser

  Enter email, optional username, and password.

4b — Create the Site record (allauth needs this to match the domain)

  In the same Shell, run:

    python manage.py shell -c "
from django.contrib.sites.models import Site
Site.objects.update_or_create(
    id=1,
    defaults={'domain': 'vulor.onrender.com', 'name': 'VULOR'}
)
"

4c — Google OAuth callback URL

  In your Google Cloud Console, add this to the authorized redirect
  URIs:

    https://vulor.onrender.com/accounts/google/login/callback/

---

STEP 5 — Verification Checklist
---------------------------------

  [ ] Homepage loads: https://vulor.onrender.com
  [ ] Products display (images load from git-tracked media)
  [ ] Django Admin: /admin/ — log in with superuser
  [ ] Staff Dashboard: /dashboard/ — accessible for staff users
  [ ] Register a test user account
  [ ] Browse products, add to cart, go through checkout
  [ ] Upload a test payment receipt
  [ ] Check dashboard for the pending payment verification
  [ ] Confirm/reject payment in dashboard
  [ ] Order confirmation email arrives in test user's inbox
  [ ] Password reset email works
  [ ] Google OAuth login works

---

Custom Domain (optional)
--------------------------

  1. Render Dashboard → your service → Settings → Custom Domain
  2. Add your domain and follow Render's DNS instructions
  3. Update these env vars in Render:
       ALLOWED_HOSTS=yourstore.com,www.yourstore.com
       CSRF_TRUSTED_ORIGINS=https://yourstore.com,https://www.yourstore.com
       SITE_URL=https://yourstore.com
  4. Update the Site record in the Django shell to match your domain

---

Running Admin Tasks
---------------------

These commands can be run from the Render Shell tab:

  • Send weekly sales report:
      python manage.py send_weekly_report

  • Abandon stale unpaid orders (>48h):
      python manage.py abandon_stale_orders

  • Send review requests to customers with delivered orders:
      python manage.py send_review_request

  • Send abandoned cart reminder emails:
      python manage.py send_abandoned_cart_emails

---

What About Celery & Background Tasks?
---------------------------------------

This setup runs without Celery or Redis. If you later need async
emails (e.g., checkout feels too slow with synchronous SMTP):

  1. Create a free Redis Cloud account (30 MB, TCP Redis) at
     https://redis.io/try-free/
  2. Set REDIS_URL to the Redis Cloud connection string
  3. Set EMAIL_ASYNC_ENABLED=True
  4. Add a Render Background Worker ($7/mo) running:
       celery -A vulor worker --loglevel=info
  5. Add a second worker for the beat scheduler if desired:
       celery -A vulor beat --loglevel=info

---

Known Limitations
------------------

  • Supabase free tier pauses after 7 days of zero traffic. If the
    store goes quiet for a week, resume it manually from Supabase
    dashboard (one click, no data loss). With daily traffic this
    never triggers.

  • 500 MB database cap on Supabase free. For a fashion store this
    handles thousands of products + orders. When exceeded, upgrade
    to Supabase Pro at $25/mo.

  • Synchronous emails add ~1 second to page loads on checkout and
    payment submission. If this becomes an issue, the Celery upgrade
    path above solves it.

  • The weekly sales report is manual via Shell instead of automated
    (since celery-beat isn't running). Takes one command.

---

Files Changed
--------------

  File              Change              Reason
  ──────────────────────────────────────────────────────────────
  render.yaml       Full rewrite        Removed Render managed DB,
                                        switched to external Postgres
                                        (Supabase), adjusted gunicorn
                                        to 1 worker (0.5 CPU limit),
                                        added all env vars, added 1 GB
                                        persistent disk for receipts
  vulor/settings.py No changes needed   Already handles everything
                                        via ON_RENDER + DATABASE_URL,
                                        sync email fallback, and
                                        LocMemCache
