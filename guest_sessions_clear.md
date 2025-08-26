Коротко: помечаем истёкшие гостевые сессии «неактивными», даём им «период удержания», и удаляем только те, у которых **нет связанных заказов**. Если заказы были и уже «подняты» на пользователя (guest\_session=NULL), такую сессию тоже можно удалять. Запускаем чистку по cron / systemd-timer’у, маленькими батчами.

Вот рабочая схема под вашу модель `GuestSession(id, expires_at, last_seen, is_active, claimed_by_user_id)` и `Order(user, guest_session)`:

---

## Политика хранения (рекомендуемая)

* **TTL гостя =** срок жизни guest-JWT (например, 7 дней).
* **Истечение:** если `expires_at < now()` → `is_active = False`.
* **Удержание (grace period):** ещё `K` дней (например, 7–14) держим неактивные сессии для возможного «подъёма» заказов при поздней авторизации.
* **Удаляем, если:**

  1. `is_active = False`
  2. `expires_at < now() - INTERVAL K DAY`
  3. **нет связанных заказов** (`Order.objects.filter(guest_session=gs).exists() == False`)

  Дополнительно: удаляем «поглощённые» сессии (`claimed_by_user_id IS NOT NULL`) даже раньше, *если* у них уже нет связанных заказов (после reassignment вы делаете `Order.update(guest_session=None)`).

> Совет: измените FK у `Order.guest_session` на `on_delete=models.SET_NULL` (не `CASCADE`), чтобы удаление сессии **не** сносило заказы. Ранее мы ставили `CASCADE` — лучше заменить.

```python
guest_session = models.ForeignKey(
    GuestSession, null=True, blank=True, on_delete=models.SET_NULL
)
```

И оставьте check-constraint «ровно один из (user, guest\_session)», но учтите, что после «подъёма» заказов `guest_session` станет NULL.

---

## Индексы

На `GuestSession`: `expires_at`, `is_active`, `last_seen`.
На `Order`: индекс по `guest_session_id`.

---

## Management command (Django) для чистки

`django_project/apps/domain/management/commands/cleanup_guests.py`

```python
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from django_project.apps.domain.models import GuestSession, Order

BATCH_SIZE = 500
GRACE_DAYS = 14  # период удержания после истечения

class Command(BaseCommand):
    help = "Cleanup expired guest sessions safely"

    def handle(self, *args, **options):
        now = timezone.now()
        cutoff = now - timedelta(days=GRACE_DAYS)

        # 1) Деактивируем истёкшие
        deactivated = (
            GuestSession.objects
            .filter(is_active=True, expires_at__lt=now)
            .update(is_active=False)
        )
        if deactivated:
            self.stdout.write(f"Deactivated: {deactivated}")

        # 2) Удаляем неактивные, старше grace, без заказов
        qs = GuestSession.objects.filter(
            is_active=False,
            expires_at__lt=cutoff,
        ).order_by("expires_at").values_list("id", flat=True)

        deleted = 0
        processed = 0

        # батчами, чтобы не держать большие транзакции
        while True:
            ids = list(qs[processed:processed + BATCH_SIZE])
            if not ids:
                break
            # отфильтровать те, у которых нет заказов
            ids_without_orders = list(
                GuestSession.objects
                .filter(id__in=ids)
                .exclude(order__isnull=False)  # related_name по FK: order_set → order
                .values_list("id", flat=True)
            )
            if ids_without_orders:
                with transaction.atomic():
                    deleted += GuestSession.objects.filter(id__in=ids_without_orders).delete()[0]
            processed += len(ids)

        self.stdout.write(f"Deleted: {deleted}")
```

> Если у FK нет `related_name`, обратитесь как `.exclude(order__isnull=False)` (Django сам сделает `order_set`). Если укажете `related_name="orders"`, пишите `.exclude(orders__isnull=False)`.

---

## Планировщик

**systemd timer** (bare-metal):

`/etc/systemd/system/stars_guest_cleanup.service`

```
[Unit]
Description=Cleanup guest sessions

[Service]
WorkingDirectory=/opt/stars_site_backend
EnvironmentFile=/opt/stars_site_backend/.env
ExecStart=/usr/bin/env bash -lc 'source .venv/bin/activate && python django_project/manage.py cleanup_guests'
User=www-data
Group=www-data
```

`/etc/systemd/system/stars_guest_cleanup.timer`

```
[Unit]
Description=Run guest cleanup daily

[Timer]
OnCalendar=*-*-* 03:17:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl daemon-reload
systemctl enable --now stars_guest_cleanup.timer
```

---

## Ещё нюансы

* **Согласуйте TTL токенов сессии и `expires_at`**: guest-JWT не должен жить дольше, чем сама `GuestSession`.
* **Принудительная инвалидция**: если нужно «выкинуть» гостя (фрод/дубль), просто `is_active=False`. При проверке токена вы и так сверяете это поле.
* **«Поднятие» сессии**: после reassignment заказов на пользователя делайте:

  ```python
  Order.objects.filter(guest_session=gs).update(user=user, guest_session=None)
  gs.is_active = False
  gs.claimed_by_user_id = user.pk
  gs.save(update_fields=["is_active","claimed_by_user_id"])
  ```

  Тогда такая сессия попадёт под удаление при ближайшей чистке.
* **SQLite**: после массовых удалений можно периодически делать `VACUUM` (только в maintenance-окно). Для MariaDB это не нужно.
* **Производительность**: если UUID в MariaDB — рассмотрите хранение как `BINARY(16)` (а не `CHAR(36)`), но это уже микрооптимизация.

---

Если хотите, дам миграцию на смену `on_delete` и добавлю `related_name="orders"` для удобных запросов, а также обновлю команду под это имя.
