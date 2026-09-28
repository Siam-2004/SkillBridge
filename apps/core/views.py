"""Shared view helpers, the home page and the static content pages."""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render

from apps.core.exceptions import (
    DomainError,
    NotVerified,
    PermissionDenied,
    ValidationFailed,
)
from apps.core.selectors import category_tree, homepage_blocks, platform_stats


# --------------------------------------------------------------------------- #
# Helpers used by every app's views
# --------------------------------------------------------------------------- #
def paginate(request, queryset, per_page: int = 20):
    paginator = Paginator(queryset, per_page)
    number = request.GET.get("page") or 1
    try:
        page = paginator.page(number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    params = request.GET.copy()
    params.pop("page", None)
    return page, params.urlencode()


def handle_domain_errors(view):

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except DjangoValidationError as exc:
            # A field validator that reached a view unwrapped is still a
            # validation failure, not a server error.
            return _respond(request, ValidationFailed("; ".join(exc.messages)))
        except DomainError as exc:
            return _respond(request, exc)

    return wrapper


def _respond(request, exc: DomainError):
    """One shape for a domain failure, whether the caller wants HTML or JSON."""
    if wants_json(request):
        body = {"detail": exc.message, "code": exc.code}
        if isinstance(exc, ValidationFailed) and exc.errors:
            body["errors"] = exc.errors
        return JsonResponse(body, status=exc.status_code)

    if isinstance(exc, PermissionDenied):
        return render(request, "errors/403.html", {"reason": exc.message}, status=403)
    if isinstance(exc, NotVerified):
        messages.warning(request, exc.message)
        return redirect("accounts:verify_notice")

    messages.error(request, exc.message)
    return redirect(request.META.get("HTTP_REFERER") or "/")


def wants_json(request) -> bool:
    return bool(
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def home(request):

    from apps.profiles.selectors import featured_freelancers

    return render(
        request,
        "core/home.html",
        {
            "stats": platform_stats(),
            "blocks": homepage_blocks(),
            "categories": category_tree()[:8],
            "featured_jobs": [],
            "featured_freelancers": featured_freelancers(limit=4),
        },
    )


def categories(request):
    return render(request, "core/categories.html", {"categories": category_tree()})


def _static_page(template: str, title: str):
    def view(request):
        return render(request, template, {"page_title": title})

    return view


about = _static_page("core/about.html", "About Skillbridge")
how_it_works = _static_page("core/how_it_works.html", "How it works")
help_centre = _static_page("core/help.html", "Help centre")
terms = _static_page("core/terms.html", "Terms of service")
privacy = _static_page("core/privacy.html", "Privacy policy")
contact = _static_page("core/contact.html", "Contact us")


def jobs(request):
    """Browse jobs, projects and freelance opportunities."""
    return redirect("marketplace:job_list")


def search(request):
    """Global search across freelancers, skills, categories, portfolios."""
    from apps.portfolios.selectors import search_portfolio
    from apps.profiles.models import Category, Skill
    from apps.profiles.selectors import search_freelancers

    query = (request.GET.get("q") or "").strip()
    results = {
        "jobs": [],
        "freelancers": [],
        "portfolios": [],
        "skills": [],
        "categories": [],
    }
    if query:
        results = {
            "jobs": [],
            "freelancers": search_freelancers(keyword=query)[:10],
            "portfolios": search_portfolio(keyword=query)[:10],
            "skills": Skill.objects.filter(name__icontains=query, is_active=True)[:10],
            "categories": Category.objects.filter(
                name__icontains=query, is_active=True
            )[:10],
        }
    total = sum(len(v) for v in results.values())
    return render(
        request,
        "core/search.html",
        {"query": query, "results": results, "result_count": total},
    )


def dashboard(request):
    """Send a signed-in user to the dashboard that matches their role."""
    user = request.user
    if not user.is_authenticated:
        return redirect("accounts:login")
    if user.is_platform_admin:
        return redirect("/admin/")
    if user.is_freelancer:
        return redirect("profiles:freelancer_dashboard")
    return redirect("profiles:client_dashboard")


# --------------------------------------------------------------------------- #
# Error pages
# --------------------------------------------------------------------------- #
def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)
