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


class AIGenerationTests(TestCase):
    @patch.dict("os.environ", {"POLLINATIONS_API_KEY": "test-key", "GEMINI_API_KEY": ""})
    @patch("site_app.dress_generator._analyze_garment_vision", return_value="blue Ankara gown with gold trim")
    @patch("site_app.dress_generator.requests.get")
    def test_requests_pollinations_flux_realistic_image(self, mock_get, mock_analyze):
        image_bytes = BytesIO()
        Image.new("RGB", (10, 10), color="purple").save(image_bytes, format="PNG")
        mock_response = BytesIO()
        Image.new("RGB", (20, 20), color="blue").save(mock_response, format="PNG")
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = mock_response.getvalue()

        from .dress_generator import generate_try_on

        result, is_ai = generate_try_on(
            dress_bytes=image_bytes.getvalue(),
            size="M",
            fabric="Premium Gabardine",
            colour_filter="none",
            notes="longer sleeves",
        )

        self.assertTrue(is_ai)
        self.assertIsNotNone(result)
        self.assertTrue(mock_get.called)
        called_url = mock_get.call_args[0][0]
        self.assertIn("model=flux", called_url)
        self.assertEqual(mock_get.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")

    @patch.dict("os.environ", {"GEMINI_API_KEY": "gemini-key", "POLLINATIONS_API_KEY": "pollinations-key"})
    @patch("site_app.dress_generator._generate_with_gemini")
    @patch("site_app.dress_generator._generate_with_pollinations")
    def test_pollinations_is_preferred_and_gemini_is_not_called(
        self, pollinations, gemini
    ):
        pollinations.return_value = b"pollinations-image"
        from .dress_generator import generate_try_on

        result, is_ai = generate_try_on(dress_bytes=b"uploaded-image")

        self.assertEqual(result, b"pollinations-image")
        self.assertTrue(is_ai)
        pollinations.assert_called_once()
        gemini.assert_not_called()

    @patch.dict("os.environ", {"POLLINATIONS_API_KEY": "test-key", "GEMINI_API_KEY": ""})
    @patch("site_app.dress_generator._analyze_garment_vision", return_value="blue Ankara gown")
    @patch("site_app.dress_generator.requests.get")
    def test_pollinations_webp_response_is_converted_to_png(self, mock_get, _mock_analyze):
        image_bytes = BytesIO()
        Image.new("RGB", (20, 20), color="blue").save(image_bytes, format="WEBP")
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = image_bytes.getvalue()
        mock_get.return_value.headers = {"Content-Type": "image/webp"}

        from .dress_generator import generate_try_on

        result, is_ai = generate_try_on(dress_bytes=b"uploaded-image")

        self.assertTrue(is_ai)
        self.assertTrue(result.startswith(b"\x89PNG"))
        mock_get.assert_called_once()

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key", "POLLINATIONS_API_KEY": ""})
    @patch("site_app.dress_generator.requests.post")
    def test_requests_gemini_when_configured(self, post):
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
            colour_filter="hue-rotate(60deg) saturate(1.6) brightness(.9)",
            notes="",
            view="back",
        )

        self.assertIsNotNone(result)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(
            payload["generationConfig"]["responseModalities"],
            ["TEXT", "IMAGE"],
        )
        self.assertEqual(payload["generationConfig"]["imageConfig"]["aspectRatio"], "3:4")
        prompt = payload["contents"][0]["parts"][1]["text"]
        self.assertIn("rear view", prompt)
        self.assertIn("regal navy blue", prompt)
        self.assertIn("garment only", prompt)
        self.assertIn("Premium Satin", prompt)
        self.assertEqual(
            payload["contents"][0]["parts"][0]["inlineData"]["data"],
            base64.b64encode(image_bytes.getvalue()).decode(),
        )

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    @patch("site_app.dress_generator.requests.post")
    def test_gemini_quota_error_is_actionable(self, post):
        post.return_value.status_code = 429
        from .dress_generator import _generate_with_gemini

        with self.assertRaisesRegex(ImageGenerationError, "quota reached"):
            _generate_with_gemini(
                dress_bytes=b"image",
                size="M",
                fabric="Premium Gabardine",
                colour_filter="none",
                notes="",
            )

    @patch.dict("os.environ", {"GEMINI_API_KEY": "gemini-key", "POLLINATIONS_API_KEY": "pollinations-key"})
    @patch("site_app.dress_generator._generate_with_pollinations")
    @patch("site_app.dress_generator._generate_with_gemini")
    @patch("site_app.dress_generator._generate_pillow_composite")
    def test_pollinations_is_used_instead_of_gemini_when_both_are_configured(
        self, pillow_fallback, gemini, pollinations
    ):
        pollinations.side_effect = ImageGenerationError("Pollinations limit reached.")
        from .dress_generator import generate_try_on

        with self.assertRaisesRegex(
            ImageGenerationError, "Pollinations image generation failed: Pollinations limit reached"
        ):
            generate_try_on(dress_bytes=b"image")
        pollinations.assert_called_once()
        gemini.assert_not_called()
        pillow_fallback.assert_not_called()

    @patch("site_app.views.generate_try_on", return_value=(b"generated-image", True))
    def test_generate_endpoint_passes_selected_angle(self, generate):
        image_bytes = BytesIO()
        Image.new("RGB", (4, 4), color="purple").save(image_bytes, format="PNG")
        response = self.client.post(
            reverse("site:dr_generate"),
            {
                "dress": SimpleUploadedFile(
                    "dress.png", image_bytes.getvalue(), content_type="image/png"
                ),
                "view": "back",
                "size": "5XL",
                "fabric": "Premium Satin",
                "colour": "none",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate.call_args.kwargs["view"], "back")
        self.assertEqual(generate.call_args.kwargs["size"], "5XL")
        self.assertEqual(generate.call_args.kwargs["fabric"], "Premium Satin")
        self.assertEqual(generate.call_args.kwargs["colour_filter"], "none")

    def test_generate_endpoint_rejects_unknown_angle(self):
        image_bytes = BytesIO()
        Image.new("RGB", (4, 4), color="purple").save(image_bytes, format="PNG")
        response = self.client.post(
            reverse("site:dr_generate"),
            {
                "dress": SimpleUploadedFile(
                    "dress.png", image_bytes.getvalue(), content_type="image/png"
                ),
                "view": "diagonal",
            },
        )
        self.assertEqual(response.status_code, 400)

    @patch.dict("os.environ", {"GEMINI_API_KEY": "", "POLLINATIONS_API_KEY": ""})
    def test_missing_api_key_fails_instead_of_returning_compositor_image(self):
        from .dress_generator import generate_try_on

        with self.assertRaisesRegex(ImageGenerationError, "No AI generation key configured"):
            generate_try_on(dress_bytes=b"not-used")


class PublicPageTests(TestCase):
    def test_public_pages_render_with_django_static_paths(self):
        pages = (
            ("site:home", "hero."),
            ("site:about", "about."),
            ("site:collection", "script."),
            ("site:contact", "style."),
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
        self.assertContains(response, 'id="roomStatus"')
        self.assertContains(response, "script.")

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
