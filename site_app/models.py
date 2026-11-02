import re

from django.core.exceptions import ValidationError
from django.db import models


def validate_phone_number(value):
    if not re.fullmatch(r"\+?[\d\s().-]+", value) or not 7 <= len(
        re.sub(r"\D", "", value)
    ) <= 15:
        raise ValidationError("Enter a valid phone number with 7 to 15 digits.")


class Collection(models.Model):
    class Category(models.TextChoices):
        GOWNS = "Gowns", "Gowns"
        DAY_WEAR = "Day wear", "Day wear"
        OCCASION = "Occasion", "Occasion"

    TONES = [(f"t{i}", f"Style {i}") for i in range(1, 13)]

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="collections/", blank=True)
    tone = models.CharField(max_length=10, choices=TONES, default="t1")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name_plural = "collections"

    def __str__(self):
        return self.name


class SiteSettings(models.Model):
    phone_number = models.CharField(
        max_length=30,
        default="+234 916 690 1393",
        validators=[validate_phone_number],
    )
    email = models.EmailField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"

    def __str__(self):
        return "Site contact settings"

    @classmethod
    def load(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
