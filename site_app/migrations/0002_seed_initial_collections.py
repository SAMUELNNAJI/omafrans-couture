from django.db import migrations


COLLECTIONS = (
    ("Aurora Gown", "Gowns", "t1"),
    ("Midnight Wrap", "Occasion", "t2"),
    ("Velvet Rose", "Gowns", "t3"),
    ("Sahara Day Dress", "Day wear", "t4"),
    ("Ivory Elegance", "Occasion", "t5"),
    ("Emerald Flow", "Gowns", "t6"),
    ("Linen Breeze", "Day wear", "t7"),
    ("Plum Couture", "Occasion", "t8"),
    ("Golden Hour", "Gowns", "t9"),
    ("City Chic", "Day wear", "t10"),
    ("Royal Navy", "Occasion", "t11"),
    ("Blush Silk", "Day wear", "t12"),
)


def seed_initial_content(apps, schema_editor):
    Collection = apps.get_model("site_app", "Collection")
    SiteSettings = apps.get_model("site_app", "SiteSettings")

    for sort_order, (name, category, tone) in enumerate(COLLECTIONS, start=1):
        Collection.objects.get_or_create(
            name=name,
            defaults={
                "category": category,
                "tone": tone,
                "sort_order": sort_order,
                "is_active": True,
            },
        )

    SiteSettings.objects.get_or_create(
        pk=1,
        defaults={"phone_number": "+234 916 690 1393", "email": ""},
    )


def remove_seeded_content(apps, schema_editor):
    Collection = apps.get_model("site_app", "Collection")
    SiteSettings = apps.get_model("site_app", "SiteSettings")
    Collection.objects.filter(name__in=[item[0] for item in COLLECTIONS]).delete()
    SiteSettings.objects.filter(pk=1).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("site_app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_initial_content, remove_seeded_content),
    ]
