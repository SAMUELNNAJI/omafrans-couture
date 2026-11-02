import base64
from html import unescape
from io import BytesIO
import re
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .dress_generator import ImageGenerationError
from .models import Collection, SiteSettings


class GeminiGenerationTests(TestCase):
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    @patch("site_app.dress_generator.requests.post")
    def test_requests_a_realistic_human_worn_image(self, post):
        image_bytes = BytesIO()
        Image.new("RGB", (4, 4), color="purple").save(image_bytes, format="PNG")
        generated_bytes = BytesIO()
        Image.new("RGB", (6, 8), color="blue").save(generated_bytes, format="PNG")
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": base64.b64encode(generated_bytes.getvalue()).decode(),
                        }
                    }]
                }
            }]
        }

        from .dress_generator import _generate_with_gemini

        result = _generate_with_gemini(
            dress_bytes=image_bytes.getvalue(),
            size="M",
            fabric="Premium Satin",
            colour_filter="none",
            notes="",
        )

        self.assertIsNotNone(result)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(
            payload["generationConfig"]["responseModalities"],
            ["TEXT", "IMAGE"],
        )
        self.assertEqual(payload["generationConfig"]["imageConfig"]["aspectRatio"], "3:4")
        prompt = payload["contents"][0]["parts"][1]["text"]
        self.assertIn("real adult woman wearing that exact garment", prompt)
        self.assertIn("realistic human anatomy", prompt)
        self.assertIn("Do not show the reference picture itself", prompt)

    @patch.dict("os.environ", {"GEMINI_API_KEY": ""})
    def test_missing_api_key_fails_instead_of_returning_compositor_image(self):
        from .dress_generator import generate_try_on

        with self.assertRaisesRegex(ImageGenerationError, "Set GEMINI_API_KEY"):
            generate_try_on(dress_bytes=b"not-used")

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    @patch("site_app.dress_generator.requests.post")
    def test_quota_error_is_reported_instead_of_returning_compositor_image(self, post):
        post.return_value.status_code = 429
        post.return_value.text = '{"error":{"message":"quota exceeded"}}'

        from .dress_generator import generate_try_on

        with self.assertRaisesRegex(ImageGenerationError, "quota is exhausted"):
            generate_try_on(dress_bytes=b"not-used")


class PublicPageTests(TestCase):
    def test_public_pages_render_with_django_static_paths(self):
        pages = (
            ("site:home", "static/images/hero.mp4"),
            ("site:about", "static/images/about.png"),
            ("site:collection", "static/js/script.js"),
            ("site:contact", "static/css/style.css"),
        )

        for route, expected_content in pages:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected_content)

    def test_public_collection_pages_render_database_collections(self):
        home = self.client.get(reverse("site:home"))
        self.assertContains(home, "Blush Silk")
        self.assertContains(home, "data-category=\"Day wear\"")

        collection_page = self.client.get(reverse("site:collection"))
        self.assertContains(collection_page, "Blush Silk")
        self.assertContains(collection_page, "data-category=\"Day wear\"")
        self.assertContains(
            collection_page,
            f'?try_on={Collection.objects.get(name="Blush Silk").pk}#dressing-room',
        )
        self.assertContains(collection_page, ">Try it on</a>")
        self.assertContains(collection_page, ">Shop</span>")

    def test_try_on_link_passes_selected_collection_image_to_dressing_room(self):
        collection = Collection.objects.get(name="Blush Silk")
        image_bytes = BytesIO()
        Image.new("RGB", (4, 4), color="purple").save(image_bytes, format="PNG")
        upload = SimpleUploadedFile(
            "blush.png", image_bytes.getvalue(), content_type="image/png"
        )

        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            collection.image.save("blush.png", upload, save=True)
            response = self.client.get(
                reverse("site:home"), {"try_on": collection.pk}
            )

        self.assertContains(response, 'data-try-on-name="Blush Silk"')
        self.assertContains(
            response,
            'data-try-on-image="/media/collections/blush.png"',
        )
        self.assertContains(
            response,
            f'?try_on={collection.pk}#dressing-room',
        )

    def test_dressing_room_has_refinable_preview_and_whatsapp_contact_controls(self):
        response = self.client.get(reverse("site:home"))
        self.assertContains(response, 'id="roomFile"')
        self.assertContains(response, 'id="generatedPreview"')
        self.assertContains(response, 'id="designNotes"')
        self.assertContains(response, 'id="generateLook"')
        self.assertContains(response, 'id="roomContact"')
        self.assertContains(response, "Contact us for this dress")
        self.assertContains(response, "This is a visual simulation, not an AI-generated fitting.")
        self.assertContains(response, "static/js/script.js")

    def test_shop_link_prefills_whatsapp_with_dress_details_and_image(self):
        collection = Collection.objects.get(name="Blush Silk")
        collection.description = "Soft rose silk with a fitted waist."
        image_bytes = BytesIO()
        Image.new("RGB", (4, 4), color="purple").save(image_bytes, format="PNG")
        upload = SimpleUploadedFile(
            "blush.png", image_bytes.getvalue(), content_type="image/png"
        )

        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            collection.image.save("blush.png", upload, save=True)
            response = self.client.get(reverse("site:collection"))

        html = response.content.decode()
        match = re.search(r'<a class="card-shop" href="([^"]+)"', html)

        self.assertIsNotNone(match)
        shop_url = unescape(match.group(1))
        self.assertIn("wa.me/2349166901393", shop_url)
        self.assertContains(response, 'class="card-shop-icon"')

        message = parse_qs(urlparse(shop_url).query)["text"][0]
        self.assertIn("I would love you to sew this dress for me", message)
        self.assertIn("Dress: Blush Silk", message)
        self.assertIn("Category: Day wear", message)
        self.assertIn("Details: Soft rose silk with a fitted waist.", message)
        self.assertIn(
            "Image: http://testserver/media/collections/blush.png",
            message,
        )

    def test_public_phone_email_and_branded_whatsapp_use_site_settings(self):
        SiteSettings.objects.update_or_create(
            pk=1,
            defaults={"phone_number": "+234 800 123 4567", "email": "hello@example.com"},
        )
        response = self.client.get(reverse("site:contact"))
        self.assertContains(response, "tel:2348001234567")
        self.assertContains(response, "https://wa.me/2348001234567")
        self.assertContains(response, "mailto:hello@example.com")
        self.assertContains(response, "whatsapp-float")

    def test_dashboard_redirects_anonymous_visitors_to_login(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertRedirects(
            response,
            f"{reverse('auth:login')}?next={reverse('dashboard:index')}",
        )

    def test_login_page_renders(self):
        response = self.client.get(reverse("auth:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome")

    def test_auth_login_route_is_available_with_or_without_trailing_slash(self):
        response = self.client.get("/auth/login")
        self.assertRedirects(
            response,
            "/auth/login/",
            status_code=301,
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.get("/auth/login/").status_code, 200)
        self.assertEqual(self.client.get("/accounts/login/").status_code, 200)

    def test_superuser_can_sign_in_to_dashboard(self):
        user = get_user_model().objects.create_user(
            username="admin",
            password="strong-admin-password",
            is_staff=True,
            is_superuser=True,
        )

        response = self.client.post(
            reverse("auth:login"),
            {"username": user.username, "password": "strong-admin-password"},
        )

        self.assertRedirects(response, reverse("dashboard:index"))
        dashboard = self.client.get(reverse("dashboard:index"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Store management")
        self.assertContains(dashboard, "Manage users")
        self.assertContains(dashboard, "Collections")

    def test_regular_user_cannot_sign_in_or_open_dashboard(self):
        user = get_user_model().objects.create_user(
            username="customer",
            password="strong-customer-password",
        )
        response = self.client.post(
            reverse("auth:login"),
            {"username": user.username, "password": "strong-customer-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not valid for a superuser account")

        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("dashboard:index")).status_code, 403)

    def test_staff_user_without_superuser_access_is_denied(self):
        user = get_user_model().objects.create_user(
            username="staff",
            password="strong-staff-password",
            is_staff=True,
        )
        response = self.client.post(
            reverse("auth:login"),
            {"username": user.username, "password": "strong-staff-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not valid for a superuser account")
