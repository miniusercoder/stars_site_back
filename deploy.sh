uv run manage.py makemigrations --noinput &&
uv run manage.py collectstatic --noinput &&
uv run manage.py migrate --noinput &&
pm2 start ecosystem.config.js
