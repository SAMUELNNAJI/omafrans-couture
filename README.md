# Omafrans Couture

The site is structured as a Django project. Public pages and collection/settings models live in `site_app`; admin-only login lives in `auth_app`; and `dashboard_app` provides superuser-only collection and contact management.

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. The public pages are `/about/`, `/collections/`, and `/contact/`. The home-page dressing room sends the selected dress image to Gemini to generate a photorealistic full-body image of an adult woman wearing the selected garment. Clicking **Try it on** on a collection item automatically loads that item's image and starts the fitting. Set a valid `GEMINI_API_KEY` in `.env` and restart Django. If Gemini has no image-generation access, the key is rejected, or quota is exhausted, the dressing room reports the error instead of showing an illustrated mannequin fallback. Users can download/share generated previews and send their size and design notes to WhatsApp.

All Python commands and dependencies should use this project-local virtual environment. If PowerShell blocks activation, run commands directly with `.\.venv\Scripts\python.exe` instead.

Create an admin user with `python manage.py createsuperuser`, then sign in at `/auth/login/`. The legacy `/accounts/login/` URL also remains available. Only active Django superusers can sign in to the dashboard at `/dashboard/`. From the dashboard, add/edit/delete collections and update the phone and email shown across the site. Collections are listed newest first with pagination, and their tone choice is shown in the dashboard. Uploaded collection images are stored under `media/`.

## Static assets and templates

- `templates/site/`: home, about, collections, and contact templates
- `templates/auth/`: admin authentication templates
- `templates/dashboard/`: dashboard templates
- `static/css/`, `static/js/`, and `static/images/`: shared site assets

The initial migration creates the current 12 sample collection entries and default contact settings. Replace sample collection details and upload real dress photos from the dashboard. For production, configure persistent media storage and serve `MEDIA_ROOT` through your hosting platform; local media serving is enabled only in debug mode.

Before deploying, set a long, unique `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, and `DJANGO_ALLOWED_HOSTS` in the environment. Production settings redirect HTTP to HTTPS and enable secure cookies and HSTS, so deploy behind HTTPS. Run `python manage.py collectstatic` to gather production static assets; serve those assets with the deployment platform or a static-file server.
