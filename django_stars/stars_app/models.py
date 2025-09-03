from django.db import models


class User(models.Model):
    wallet_address = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        verbose_name="Адрес кошелька",
        help_text="Уникальный адрес TON-кошелька пользователя",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
        help_text="Дата и время регистрации пользователя",
    )
    referrer = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referrals",
        verbose_name="Реферер",
        help_text="Пользователь, по приглашению которого зарегистрировался данный пользователь",
    )
    ref_alias = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        default=None,
        verbose_name="Алиас реферера",
        help_text="Псевдоним реферальной ссылки",
    )

    class Meta:
        verbose_name_plural = "Пользователи"
        verbose_name = "Пользователь"

    def __str__(self):
        return self.wallet_address


class GuestSession(models.Model):
    id = models.UUIDField(
        primary_key=True,
        editable=False,
        verbose_name="ID",
        help_text="Уникальный идентификатор гостевой сессии",
    )
    claimed_by_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Закреплён за пользователем",
        help_text="Пользователь, к которому привязана эта гостевая сессия",
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
        help_text="Тип подписки или тарифа",
    )
    price = models.FloatField(
        verbose_name="Цена",
        help_text="Публичная цена, отображаемая на сайте",
    )
    white_price = models.FloatField(
        verbose_name="Цена на fragment",
        default=0,
        help_text="Цена на fragment",
    )

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

    id = models.AutoField(primary_key=True, unique=True, verbose_name="ID")
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
        help_text="Пользователь, оформивший заказ",
    )
    guest_session = models.ForeignKey(
        GuestSession,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Гостевая сессия",
        help_text="Гостевая сессия, если заказ был сделан без аккаунта",
    )
    type = models.IntegerField(
        choices=Type.choices,
        verbose_name="Тип заказа",
        help_text="Категория заказа (звёзды, премиум, TON и т.д.)",
    )
    status = models.IntegerField(
        choices=Status.choices,
        default=Status.CREATING,
        verbose_name="Статус заказа",
        help_text="Текущий статус выполнения заказа",
    )
    amount = models.BigIntegerField(
        default=0,
        verbose_name="Количество",
        help_text="Количество единиц заказа (звёзды, TON и т.д.)",
    )
    created_at = models.DateTimeField(
        verbose_name="Дата создания",
        auto_now_add=True,
        help_text="Дата и время оформления заказа",
    )
    price = models.FloatField(default=0, verbose_name="Цена", help_text="Цена в USD")
    price_ton = models.FloatField(
        default=0, verbose_name="Цена в TON", help_text="Цена в криптовалюте TON"
    )
    white_price = models.FloatField(
        default=0, verbose_name="Цена на сайте", help_text="Цена на fragment"
    )
    take_in_work = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Взято в работу",
        help_text="Дата и время, когда заказ был принят в обработку",
    )
    is_refund = models.BooleanField(
        default=False,
        verbose_name="Возврат",
        help_text="Отмечает, был ли произведён возврат по заказу",
    )
    recipient = models.CharField(
        blank=True,
        null=True,
        verbose_name="Получатель",
        max_length=500,
        help_text="Идентификатор получателя",
    )
    recipient_username = models.CharField(
        blank=True,
        null=True,
        verbose_name="Никнейм получателя",
        max_length=500,
        help_text="Юзернейм получателя",
    )
    referrals_reward = models.FloatField(
        default=0,
        verbose_name="Доход рефералов",
        help_text="Вознаграждение за реферальную систему по заказу",
    )
    msg_hash = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        verbose_name="Хэш сообщения",
        help_text="Хэш сообщения в блокчейне",
    )
    ton_sent = models.FloatField(
        default=0,
        verbose_name="Отправлено TON",
        null=True,
        blank=True,
        help_text="Количество отправленных монет TON",
    )
    inner_message_hash = models.CharField(
        blank=True,
        null=True,
        verbose_name="Hash внутреннего сообщения",
        max_length=255,
        db_index=True,
        help_text="Хэш внутреннего сообщения TON",
    )
    tx_hash = models.CharField(
        blank=True,
        null=True,
        verbose_name="Хэш транзакции",
        max_length=255,
        db_index=True,
        help_text="Хэш транзакции в блокчейне",
    )
    anonymous_sent = models.BooleanField(
        default=False,
        verbose_name="Анонимно отправлено",
        help_text="Отмечает, был ли заказ отправлен анонимно",
    )
    payload = models.JSONField(
        blank=True,
        null=True,
        verbose_name="Дополнительные данные",
        default=dict,
        help_text="Служебные данные по заказу",
    )

    class Meta:
        verbose_name_plural = "Заказы"
        verbose_name = "Заказ"

        # constraints = [
        #     # Ровно один из (user, guest_session) должен быть задан
        #     models.CheckConstraint(
        #         check=(
        #             (Q(user__isnull=False) & Q(guest_session__isnull=True))
        #             | (Q(user__isnull=True) & Q(guest_session__isnull=False))
        #         ),
        #         name="order_exactly_one_principal",
        #     )
        # ]

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
    class Names(models.TextChoices):
        CRYPTOPAY = "cryptopay", "CryptoPay"
        CARDLINK = "cardlink", "CardLink"
        TON_CONNECT = "ton_connect", "TonConnect"
        HELEKET = "heleket", "Heleket"
        FREEKASSA = "freekassa", "FreeKassa"
        LOLZTEAM = "lolzteam", "LolzTeam"

    name = models.CharField(
        max_length=100,
        unique=True,
        choices=Names.choices,
        verbose_name="Название платёжной системы",
    )
    shop_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ID магазина",
        help_text="Идентификатор магазина в платёжной системе",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна",
        help_text="Включена ли данная платёжная система",
    )
    access_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Ключ доступа",
        help_text="Публичный ключ/токен для API",
    )
    secret_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Секретный ключ",
        help_text="Секретный API-ключ",
    )

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
        verbose_name="Платёжная система",
        help_text="К какой платёжной системе относится метод",
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Название метода",
        help_text="Человекочитаемое название метода оплаты",
    )
    code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Код метода",
        help_text="Внутренний код метода в системе платёги",
    )
    min_amount = models.FloatField(
        default=0,
        verbose_name="Минимальная сумма (USD)",
        help_text="Минимально допустимая сумма для оплаты",
    )
    icon = models.ImageField(
        upload_to="payment_methods/",
        null=True,
        blank=True,
        default=None,
        verbose_name="Иконка метода оплаты",
        help_text="Иконка, отображаемая для метода в интерфейсе",
    )
    order = models.IntegerField(
        default=0,
        verbose_name="Порядок отображения",
        help_text="Приоритет отображения метода (чем выше число, тем выше в списке)",
    )

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
        help_text="Уникальный идентификатор платежа",
    )
    method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Метод оплаты",
        help_text="Метод, с помощью которого был совершен платёж",
    )
    sum = models.FloatField(
        verbose_name="Сумма",
        help_text="Сумма платежа в USD",
    )
    status = models.IntegerField(
        choices=Status.choices,
        default=Status.CREATED,
        verbose_name="Статус платежа",
        db_index=True,
        help_text="Текущий статус платежа",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Заказ",
        related_name="payment",
        help_text="Заказ, с которым связан платёж",
    )
    payment_id = models.CharField(
        blank=True,
        null=True,
        verbose_name="ID платежа (служебный)",
        max_length=500,
        db_index=True,
        help_text="Служебный ID платежа во внешней системе",
    )
    created_at = models.DateTimeField(
        verbose_name="Дата создания",
        db_index=True,
        auto_now_add=True,
        help_text="Дата и время создания платежа",
    )

    class Meta:
        verbose_name_plural = "Платежи"
        verbose_name = "Платёж"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["status", "created_at", "method"]),
        ]

    def __str__(self):
        return f"#{self.id}"


class TonTransaction(models.Model):
    class Currency(models.TextChoices):
        TON = "TON"
        USTD = "USDT"

    id = models.AutoField(primary_key=True, unique=True, verbose_name="ID")
    source = models.CharField(
        max_length=48,
        verbose_name="Источник",
        help_text="Адрес или источник транзакции",
    )
    hash = models.CharField(
        max_length=255,
        verbose_name="Хэш транзакции",
        null=True,
        blank=True,
        default=None,
        help_text="Уникальный идентификатор транзакции в блокчейне",
    )
    amount = models.BigIntegerField(
        verbose_name="Количество",
        null=False,
        default=0,
        help_text="Сумма перевода в выбранной валюте",
    )
    currency = models.CharField(
        max_length=10,
        choices=Currency.choices,
        default=Currency.TON,
        verbose_name="Валюта",
        help_text="Валюта транзакции (TON или USDT)",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
        null=True,
        blank=True,
        help_text="Пользователь, связанный с транзакцией",
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="ton_transaction",
        verbose_name="Платёж",
        null=True,
        blank=True,
        help_text="Связанный платёж",
    )

    class Meta:
        verbose_name_plural = "Транзакции"
        verbose_name = "Транзакция"

    def __str__(self):
        return f"#{self.id} {self.source} - {self.hash}"
