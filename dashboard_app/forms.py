from django import forms

from site_app.models import Collection, SiteSettings


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = (
            "name",
            "category",
            "description",
            "image",
            "tone",
            "is_active",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ("phone_number", "email")
