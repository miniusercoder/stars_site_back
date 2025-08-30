from django.contrib import admin

from django_stars.stars_app.models import (
    Price,
    User,
    Order,
    PaymentSystem,
    Payment,
    PaymentMethod,
)


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ("type", "price", "white_price")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet_address", "created_at", "referrer")
    search_fields = (
        "id",
        "wallet_address",
    )
    list_filter = ("created_at",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "type", "status", "created_at")
    search_fields = (
        "id",
        "user__wallet_address",
        "recipient_username",
    )
    list_filter = ("type", "status", "created_at")


@admin.register(PaymentSystem)
class PaymentSystemAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "sum", "status", "created_at")
    search_fields = ("order__id",)
    list_filter = ("status", "created_at")


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("system", "name", "min_amount")
    search_fields = ("name", "system__name")
