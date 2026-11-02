from django.contrib import admin

from .models import Collection, SiteSettings


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "is_active", "created_at")
    list_filter = ("category", "is_active")
    search_fields = ("name", "description")
    ordering = ("-created_at", "-pk")


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "email", "updated_at")

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()
