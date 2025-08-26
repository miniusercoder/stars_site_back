# Register your models here.
from django.contrib import admin

from django_stars.stars_app.models import Price


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ("type", "price", "white_price")
