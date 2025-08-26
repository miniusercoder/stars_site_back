uv run managy.py makemigrations --noinput &&
uv run manage.py collectstatic --noinput &&
uv run manage.py migrate --noinput &&
pm2 start stars_site_backend stars_site_admin
