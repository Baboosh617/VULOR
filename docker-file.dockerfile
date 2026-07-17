# backend/Dockerfile

# --- Stage 1: build the compiled Tailwind CSS -------------------------------
FROM node:20-alpine AS frontend-build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# Tailwind v4's CSS-first @source directives (in
# frontend/static_src/css/style.css) scan frontend/templates, frontend/static/js,
# dashboard/templates, orders/templates, and payments/templates for class
# names, so those trees need to be present alongside the CSS source.
COPY frontend/static_src ./frontend/static_src
COPY frontend/templates ./frontend/templates
COPY frontend/static/js ./frontend/static/js
COPY dashboard/templates ./dashboard/templates
COPY orders/templates ./orders/templates
COPY payments/templates ./payments/templates

RUN npm run build:css

# --- Stage 2: the actual application image ----------------------------------
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Bring in the CSS compiled in stage 1 — frontend/static/css/dist/ is
# gitignored (rebuilt on every deploy), so it doesn't exist in the plain
# COPY . . above.
COPY --from=frontend-build /app/frontend/static/css/dist /app/frontend/static/css/dist

# Collect static files. This needs a SECRET_KEY to import settings, but the
# real runtime key must never be baked into the image — pass a throwaway
# value for this build step only (scoped to the RUN, never an ENV), so the
# running container still gets SECRET_KEY from its own environment.
ARG SECRET_KEY=build-time-placeholder-not-used-at-runtime
RUN SECRET_KEY=${SECRET_KEY} python manage.py collectstatic --noinput

# Create non-root user
RUN useradd -m -r vulor && chown -R vulor /app
USER vulor

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "vulor.wsgi:application"]
