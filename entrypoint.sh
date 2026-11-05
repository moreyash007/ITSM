#!/bin/sh
set -e

# Allow running one-off commands (e.g. cron: ./entrypoint.sh python manage.py check_sla)
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

echo "==> Waiting for database..."
until python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'itsm.settings')
django.setup()
from django.db import connection
connection.ensure_connection()
print('Database ready.')
"; do
  echo "Database not ready, retrying in 2s..."
  sleep 2
done

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Seeding initial data..."
python manage.py shell << 'PYEOF'
from users.models import User
from tickets.models import Category
from assets.models import AssetCategory

# Create superuser if not exists
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@itsm.local',
        password=__import__('os').environ['ADMIN_PASSWORD'],
        role='admin',
        first_name='System',
        last_name='Admin',
    )
    print("Created superuser: admin")

# Seed default ticket categories
default_categories = [
    'Hardware', 'Software', 'Network', 'Access & Permissions',
    'Email', 'Printing', 'Security', 'Other'
]
for name in default_categories:
    Category.objects.get_or_create(name=name)

# Seed default asset categories
asset_categories = [
    'Laptop', 'Desktop', 'Server', 'Network Device',
    'Mobile Device', 'Printer', 'Monitor', 'Software License'
]
for name in asset_categories:
    AssetCategory.objects.get_or_create(name=name)

# Default SLA policies (minutes) so new tickets get an SLA attached
from tickets.models import SLAPolicy
for prio, resp, res in [('critical', 15, 240), ('high', 60, 480),
                        ('medium', 240, 1440), ('low', 480, 4320)]:
    SLAPolicy.objects.get_or_create(
        priority=prio,
        defaults=dict(response_time_minutes=resp, resolution_time_minutes=res),
    )

print("Seed data applied.")
PYEOF

echo "==> Starting Gunicorn..."
exec gunicorn itsm.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
