import re

from .models import SiteSettings


def site_contact(request):
    settings = SiteSettings.load()
    return {
        "site_settings": settings,
        "site_phone_digits": re.sub(r"\D", "", settings.phone_number),
    }
