from uuid import uuid4

from django.db import models


class GuestSession(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)
    ton_verify = models.CharField(
        max_length=128, unique=True, null=False, blank=False, default=""
    )
    claimed_by_user_id = models.IntegerField(
        null=True, blank=True
    )  # фиксируем, кем поглощена (если надо)
    is_active = models.BooleanField(default=True, db_index=True)


class User(models.Model):
    wallet_address = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    referrer = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referrals",
    )

    def __str__(self):
        return self.wallet_address


class Price(models.Model):
    class Type(models.TextChoices):
        PREMIUM_3 = "premium_3", "Премиум 3 месяца"
        PREMIUM_6 = "premium_6", "Премиум 6 месяцев"
        PREMIUM_12 = "premium_12", "Премиум 12 месяцев"

    id = models.AutoField(primary_key=True, unique=True, verbose_name="ID")
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        verbose_name="Тип",
        unique=True,
        db_index=True,
    )
    price = models.FloatField(verbose_name="Цена")
    white_price = models.FloatField(verbose_name="Цена на сайте", default=0)

    class Meta:
        verbose_name_plural = "Цены"
        verbose_name = "Цена"

    def get_type_display(self):
        return (
            self.Type(self.type).label
            if self.type in self.Type.values
            else "Неизвестный тип"
        )

    def __str__(self):
        return f"#{self.id} {self.get_type_display()} - {self.price} USD"
