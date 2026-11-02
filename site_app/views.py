import base64
import io
import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Collection
from .dress_generator import ImageGenerationError, generate_try_on

logger = logging.getLogger(__name__)


def home(request):
    collections = Collection.objects.filter(is_active=True).order_by(
        "-created_at", "-pk"
    )[:8]
    try_on_item = Collection.objects.filter(
        pk=request.GET.get("try_on"), is_active=True
    ).first()
    return render(
        request,
        "site/index.html",
        {"collections": collections, "try_on_item": try_on_item},
    )


def about(request):
    return render(request, "site/about.html")


def collection(request):
    collections = Collection.objects.filter(is_active=True)
    return render(request, "site/collection.html", {"collections": collections})


def contact(request):
    return render(request, "site/contact.html")


@csrf_exempt
@require_POST
def dressing_room_generate(request):
    """
    POST /api/dressing-room/generate/

    Accepts multipart/form-data:
      - dress      : image file
      - size       : XS / S / M / L / XL / 2XL  (default M)
      - fabric     : fabric label string           (default Premium Gabardine)
      - colour     : CSS filter string             (default none)
      - notes      : free-text description         (optional)

    Returns JSON: { "image": "<base64 PNG>", "notes": "..." }
    """
    dress_file = request.FILES.get("dress")
    if not dress_file:
        return JsonResponse({"error": "No dress image uploaded."}, status=400)

    if dress_file.size > 10 * 1024 * 1024:
        return JsonResponse({"error": "Image too large. Max 10 MB."}, status=400)

    size   = request.POST.get("size", "M").strip().upper()
    fabric = request.POST.get("fabric", "Premium Gabardine").strip()
    colour = request.POST.get("colour", "none").strip()
    notes  = request.POST.get("notes", "").strip()[:500]

    try:
        dress_bytes = dress_file.read()
        gen_result  = generate_try_on(
            dress_bytes=dress_bytes,
            size=size,
            fabric=fabric,
            colour_filter=colour,
            notes=notes,
        )
        if isinstance(gen_result, tuple):
            result_png, is_ai = gen_result
        else:
            result_png, is_ai = gen_result, False

        b64 = base64.b64encode(result_png).decode("ascii")
        return JsonResponse({"image": b64, "notes": notes, "is_ai": is_ai})
    except ImageGenerationError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    except Exception as exc:
        return JsonResponse(
            {"error": f"Generation failed: {str(exc)}"},
            status=500
        )
