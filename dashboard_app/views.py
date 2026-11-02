from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView

from site_app.models import Collection, SiteSettings
from .forms import CollectionForm, SiteSettingsForm


class SuperuserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


class DashboardView(SuperuserRequiredMixin, TemplateView):
    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        users = get_user_model().objects
        context["total_users"] = users.count()
        context["active_users"] = users.filter(is_active=True).count()
        context["staff_users"] = users.filter(is_staff=True).count()
        context["collection_count"] = Collection.objects.count()
        context["active_collection_count"] = Collection.objects.filter(is_active=True).count()
        collections = Collection.objects.order_by("-created_at", "-pk")
        context["collections"] = Paginator(collections, 8).get_page(
            self.request.GET.get("page")
        )
        context["site_settings"] = SiteSettings.load()
        return context


class CollectionCreateView(SuperuserRequiredMixin, CreateView):
    form_class = CollectionForm
    template_name = "dashboard/collection_form.html"
    success_url = reverse_lazy("dashboard:index")

    def form_valid(self, form):
        messages.success(self.request, "Collection added successfully.")
        return super().form_valid(form)


class CollectionUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Collection
    form_class = CollectionForm
    template_name = "dashboard/collection_form.html"
    success_url = reverse_lazy("dashboard:index")

    def form_valid(self, form):
        messages.success(self.request, "Collection updated successfully.")
        return super().form_valid(form)


class CollectionDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Collection
    template_name = "dashboard/collection_confirm_delete.html"
    success_url = reverse_lazy("dashboard:index")

    def form_valid(self, form):
        messages.success(self.request, "Collection deleted.")
        return super().form_valid(form)


class SiteSettingsUpdateView(SuperuserRequiredMixin, UpdateView):
    form_class = SiteSettingsForm
    template_name = "dashboard/settings_form.html"
    success_url = reverse_lazy("dashboard:index")

    def get_object(self, queryset=None):
        return SiteSettings.load()

    def form_valid(self, form):
        messages.success(self.request, "Site contact settings saved.")
        return super().form_valid(form)
