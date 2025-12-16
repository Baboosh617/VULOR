#!/bin/bash
set -e  # Exit on any error

echo "🔧 Starting deployment process..."
echo "🔧 Current directory: $(pwd)"

# Wait for database to be ready (critical!)
echo "⏳ Waiting for database connection..."
until python << END
import sys
import psycopg2
from django.conf import settings
try:
    conn = psycopg2.connect(settings.DATABASES['default']['NAME'])
    conn.close()
    print("✅ Database ready!")
    sys.exit(0)
except Exception as e:
    print(f"⏳ Still waiting... ({e})")
    sys.exit(1)
END
do
  sleep 2
done

# Run migrations with explicit output
echo "🔧 Running migrations..."
python manage.py migrate --noinput --verbosity=3

# Create superuser (for admin access)
echo "🔧 Creating admin user..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'securepassword123')
    print('✅ Superuser created')
else:
    print('ℹ️ Superuser already exists')
END

# Collect static files properly
echo "🔧 Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "🚀 Starting server..."
exec gunicorn vulor.wsgi:application
