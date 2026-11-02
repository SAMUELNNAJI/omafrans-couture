from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from site_app.models import Collection, SiteSettings


class AdminDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            username="atelier-admin",
            email="admin@example.com",
            password="secure-test-password",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_dashboard_lists_seeded_collections_and_settings(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blush Silk")
        self.assertContains(response, "Tone: Style 12")
        self.assertContains(response, "+234 916 690 1393")
        self.assertContains(response, "Add collection")
        self.assertNotContains(response, "Sort order")

    def test_dashboard_collections_are_paginated_newest_first(self):
        newest_collection = Collection.objects.create(
            name="Newest Dashboard Dress",
            category=Collection.Category.GOWNS,
            tone="t2",
        )

        first_page = self.client.get(reverse("dashboard:index"))
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.context["collections"].number, 1)
        self.assertEqual(first_page.context["collections"].paginator.count, 13)
        self.assertEqual(
            first_page.context["collections"].object_list[0],
            newest_collection,
        )
        self.assertContains(first_page, "Page 1 of 2")

        second_page = self.client.get(reverse("dashboard:index"), {"page": 2})
        self.assertEqual(second_page.context["collections"].number, 2)
        self.assertEqual(len(second_page.context["collections"]), 5)


    def test_admin_can_add_and_edit_a_collection(self):
        response = self.client.post(
            reverse("dashboard:collection-add"),
            {
                "name": "Custom Test Dress",
                "category": Collection.Category.GOWNS,
                "description": "A test design",
                "tone": "t2",
                "is_active": True,
            },
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        collection = Collection.objects.get(name="Custom Test Dress")

        response = self.client.post(
            reverse("dashboard:collection-edit", args=[collection.pk]),
            {
                "name": "Updated Test Dress",
                "category": Collection.Category.OCCASION,
                "description": "Updated",
                "tone": "t3",
                "is_active": True,
            },
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        collection.refresh_from_db()
        self.assertEqual(collection.name, "Updated Test Dress")
        self.assertEqual(collection.category, Collection.Category.OCCASION)

    def test_admin_can_upload_a_collection_photo(self):
        image_bytes = BytesIO()
        Image.new("RGB", (4, 4), color="purple").save(image_bytes, format="PNG")
        upload = SimpleUploadedFile(
            "dress.png", image_bytes.getvalue(), content_type="image/png"
        )

        with TemporaryDirectory() as media_dir, override_settings(MEDIA_ROOT=media_dir):
            response = self.client.post(
                reverse("dashboard:collection-add"),
                {
                    "name": "Photo Test Dress",
                    "category": Collection.Category.GOWNS,
                    "description": "",
                    "tone": "t1",
                    "is_active": True,
                    "image": upload,
                },
            )

        self.assertRedirects(response, reverse("dashboard:index"))
        self.assertTrue(Collection.objects.get(name="Photo Test Dress").image.name)

    def test_admin_can_update_public_phone_and_email(self):
        settings = SiteSettings.load()
        response = self.client.post(
            reverse("dashboard:settings"),
            {"phone_number": "+234 800 123 4567", "email": "hello@example.com"},
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        settings.refresh_from_db()
        self.assertEqual(settings.phone_number, "+234 800 123 4567")
        self.assertEqual(settings.email, "hello@example.com")

        contact = self.client.get(reverse("site:contact"))
        self.assertContains(contact, "+234 800 123 4567")
        self.assertContains(contact, "hello@example.com")
        self.assertContains(contact, "https://wa.me/2348001234567")

    def test_invalid_phone_number_is_not_saved(self):
        response = self.client.post(
            reverse("dashboard:settings"),
            {"phone_number": "not-a-phone", "email": "hello@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid phone number")
        self.assertEqual(SiteSettings.load().phone_number, "+234 916 690 1393")

    def test_non_superuser_cannot_manage_collections_or_settings(self):
        user = get_user_model().objects.create_user(
            username="staff-user",
            password="staff-test-password",
            is_staff=True,
        )
        self.client.force_login(user)
        for route in (
            reverse("dashboard:index"),
            reverse("dashboard:collection-add"),
            reverse("dashboard:settings"),
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 403)
