from django.db import models
from django.db.models import Q


class User(models.Model):
    wallet_address = models.CharField(max_length=128, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    referrer = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referrals",
    )

    class Meta:
        verbose_name_plural = "Пользователи"
        verbose_name = "Пользователь"

    def __str__(self):
        return self.wallet_address


class GuestSession(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    claimed_by_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name_plural = "Гостевые сессии"
        verbose_name = "Гостевая сессия"


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


class Order(models.Model):
    class Type(models.IntegerChoices):
        STARS = 1, "Звёзды"
        PREMIUM = 2, "Премиум"
        TON = 3, "TON"
        TON_WALLET = 4, "TON на кошелёк"
        GIFT_REGULAR = 5, "Подарок (обычный)"

    class Status(models.IntegerChoices):
        CANCEL = -1, "Отменен"
        ERROR = -2, "Ошибка"
        CREATING = 0, "Создание"
        CREATED = 1, "Создан"
        IN_PROGRESS = 2, "В обработке"
        COMPLETED = 3, "Завершён"
        BLOCKCHAIN_WAITING = 4, "Ожидание подтверждения в блокчейне"

    id = models.AutoField(primary_key=True, unique=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    guest_session = models.ForeignKey(
        GuestSession, null=True, blank=True, on_delete=models.SET_NULL
    )
    type = models.IntegerField(
        choices=Type.choices,
        verbose_name="Тип заказа",
    )
    status = models.IntegerField(
        choices=Status.choices,
        default=Status.CREATING,
        verbose_name="Статус заказа",
    )
    amount = models.BigIntegerField(default=0, verbose_name="Количество")
    created_at = models.DateTimeField(verbose_name="Дата создания", auto_now_add=True)
    price = models.FloatField(default=0, verbose_name="Цена")
    price_ton = models.FloatField(default=0, verbose_name="Цена в TON")
    white_price = models.FloatField(default=0, verbose_name="Цена на сайте")
    take_in_work = models.DateTimeField(
        null=True, blank=True, verbose_name="Взято в работу"
    )
    is_refund = models.BooleanField(default=False, verbose_name="Возврат")
    recipient = models.CharField(
        blank=True,
        null=True,
        verbose_name="Получатель",
        max_length=500,
    )
    recipient_username = models.CharField(
        blank=True,
        null=True,
        verbose_name="Никнейм получателя",
        max_length=500,
    )
    referrals_reward = models.FloatField(default=0, verbose_name="Доход рефералов")
    msg_hash = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        verbose_name="Хэш сообщения",
    )
    ton_sent = models.FloatField(
        default=0, verbose_name="Отправлено TON", null=True, blank=True
    )
    inner_message_hash = models.CharField(
        blank=True,
        null=True,
        verbose_name="Hash внутреннего сообщения",
        max_length=255,
        db_index=True,
    )
    tx_hash = models.CharField(
        blank=True,
        null=True,
        verbose_name="Хэш транзакции",
        max_length=255,
        db_index=True,
    )
    anonymous_sent = models.BooleanField(
        default=False, verbose_name="Анонимно отправлено"
    )

    class Meta:
        verbose_name_plural = "Заказы"
        verbose_name = "Заказ"

        constraints = [
            # Ровно один из (user, guest_session) должен быть задан
            models.CheckConstraint(
                check=(
                    (Q(user__isnull=False) & Q(guest_session__isnull=True))
                    | (Q(user__isnull=True) & Q(guest_session__isnull=False))
                ),
                name="order_exactly_one_principal",
            )
        ]

        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def get_type_display(self):
        return (
            self.Type(self.type).label
            if self.type in self.Type.values
            else "Неизвестный тип"
        )

    def __str__(self):
        return f"#{self.id} {self.get_type_display()}"


class PaymentSystem(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    access_key = models.CharField(max_length=255, blank=True, null=True)
    secret_key = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Платёжные системы"
        verbose_name = "Платёжная система"

    def __str__(self):
        return self.name


class PaymentMethod(models.Model):
    system = models.ForeignKey(
        PaymentSystem,
        on_delete=models.CASCADE,
        related_name="methods",
    )
    name = models.CharField(max_length=100)
    min_amount = models.FloatField(default=0)

    class Meta:
        verbose_name_plural = "Методы оплаты"
        verbose_name = "Метод оплаты"
        unique_together = ("system", "name", "min_amount")

    def __str__(self):
        return f"{self.system.name} - {self.name}"


class Payment(models.Model):
    class Status(models.IntegerChoices):
        CREATED = 0, "Создан"
        CONFIRMED = 1, "Подтверждён"
        CANCELLED = 2, "Отменён"
        ERROR = -1, "Ошибка"

    id = models.CharField(
        unique=True,
        verbose_name="ID",
        max_length=64,
        primary_key=True,
        null=False,
        blank=False,
    )
    type = models.ForeignKey(
        PaymentSystem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        verbose_name="Платёжная система",
    )
    sum = models.FloatField(verbose_name="Сумма")
    currency = models.CharField(default="BTC", verbose_name="Валюта", max_length=20)
    status = models.IntegerField(verbose_name="Статус", db_index=True)
    order = models.ForeignKey(
        Order,
        null=True,
        blank=True,
        default=None,
        on_delete=models.SET_NULL,
        verbose_name="Заказ",
    )
    payment_id = models.CharField(
        blank=True,
        null=True,
        verbose_name="ID платежа (служебный)",
        max_length=500,
        db_index=True,
    )
    created_at = models.DateTimeField(verbose_name="Дата платежа", db_index=True)
    message_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Платежи"
        verbose_name = "Платеж"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["status", "created_at", "type"]),
        ]

    def __str__(self):
        return f"#{self.id}"
