import os

from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    os.getenv("DJANGO_SETTINGS_MODULE", "django_stars.django_stars.settings"),
)
import django  # noqa: E402

django.setup()
