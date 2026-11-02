from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class AdminAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Admin username",
        widget=forms.TextInput(
            attrs={"autofocus": True, "autocomplete": "username"}
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        if self.user_cache is not None and not self.user_cache.is_superuser:
            self.user_cache = None
            raise ValidationError(
                _("The username or password is not valid for a superuser account."),
                code="invalid_login",
            )
        return cleaned_data
