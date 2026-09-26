"""Portfolios: the public gallery and the owner's editor."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.permissions import freelancer_required
from apps.core.views import handle_domain_errors, paginate
from apps.portfolios import services
from apps.portfolios.forms import PortfolioForm, PortfolioMediaForm
from apps.portfolios.models import Portfolio
from apps.portfolios.selectors import item_detail, public_items_for
from apps.profiles.models import FreelancerProfile


def public_list(request, username: str):
    items = public_items_for(username)
    page, querystring = paginate(request, items, 12)
    profile = get_object_or_404(FreelancerProfile, user__username=username)
    return render(
        request,
        "portfolios/public_list.html",
        {
            "page": page,
            "querystring": querystring,
            "profile": profile,
            "owner": profile.user,
            "nav_section": "freelancers",
            "page_title": f"{profile.user.full_name} — portfolio",
        },
    )


def detail(request, public_id):
    item = get_object_or_404(
        Portfolio.objects.select_related("freelancer__user", "category"),
        public_id=public_id,
    )
    if not item.is_public:
        owner = (
            request.user.is_authenticated and request.user.pk == item.freelancer.user_id
        )
        if not owner and not (
            request.user.is_authenticated and request.user.is_platform_admin
        ):
            raise Http404("Not found.")

    services.record_item_view(
        item=item,
        user=request.user if request.user.is_authenticated else None,
        session_key=request.session.session_key or "",
    )

    return render(
        request,
        "portfolios/detail.html",
        {
            "item": item,
            "owner": item.freelancer.user,
            "media": item.media.all(),
            "nav_section": "freelancers",
            "page_title": item.title,
        },
    )


@freelancer_required
def my_portfolio(request):
    profile = FreelancerProfile.objects.get(user=request.user)
    items = Portfolio.objects.filter(freelancer=profile).order_by(
        "order", "-created_at"
    )
    return render(
        request,
        "portfolios/my_portfolio.html",
        {
            "items": items,
            "profile": profile,
            "nav": "portfolio",
            "page_title": "My portfolio",
        },
    )


@freelancer_required
@handle_domain_errors
@require_http_methods(["GET", "POST"])
def create(request):
    profile = FreelancerProfile.objects.get(user=request.user)
    form = PortfolioForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        skills = data.pop("skills", None)
        cover = data.pop("cover_image", None)
        item = services.create_item(
            profile=profile,
            actor=request.user,
            skills=skills,
            cover_image=cover,
            **data,
        )
        messages.success(request, "Portfolio entry added.")
        return redirect(item.get_absolute_url())
    return render(
        request,
        "portfolios/portfolio_form.html",
        {"form": form, "nav": "portfolio", "page_title": "Add work"},
    )


@freelancer_required
@handle_domain_errors
@require_http_methods(["GET", "POST"])
def edit(request, public_id):
    item = get_object_or_404(
        Portfolio, public_id=public_id, freelancer__user=request.user
    )
    form = PortfolioForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        data = dict(form.cleaned_data)
        skills = data.pop("skills", None)
        cover = data.pop("cover_image", None)
        services.update_item(
            item=item, actor=request.user, skills=skills, cover_image=cover, **data
        )
        messages.success(request, "Portfolio entry updated.")
        return redirect(item.get_absolute_url())
    return render(
        request,
        "portfolios/portfolio_form.html",
        {
            "form": form,
            "item": item,
            "media_form": PortfolioMediaForm(),
            "nav": "portfolio",
            "page_title": f"Edit {item.title}",
        },
    )


@freelancer_required
@handle_domain_errors
@require_http_methods(["POST"])
def delete(request, public_id):
    item = get_object_or_404(
        Portfolio, public_id=public_id, freelancer__user=request.user
    )
    services.delete_item(item=item, actor=request.user)
    messages.success(request, "Portfolio entry removed.")
    return redirect("portfolios:my_portfolio")


@freelancer_required
@handle_domain_errors
@require_http_methods(["POST"])
def add_media(request, public_id):
    item = get_object_or_404(
        Portfolio, public_id=public_id, freelancer__user=request.user
    )
    form = PortfolioMediaForm(request.POST, request.FILES)
    if form.is_valid():
        services.add_media(item=item, actor=request.user, **form.cleaned_data)
        messages.success(request, "Image added.")
    else:
        messages.error(request, "Choose an image to upload.")
    return redirect("portfolios:edit", public_id=item.public_id)


@freelancer_required
@handle_domain_errors
@require_http_methods(["POST"])
def from_project(request, project_id):
    messages.error(request, "Project import is not supported in this configuration.")
    return redirect("portfolios:my_portfolio")
