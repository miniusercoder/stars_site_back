from django.db import models


class GuestSession(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)
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
