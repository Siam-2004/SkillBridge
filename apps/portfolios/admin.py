"""Portfolio moderation."""

from django.contrib import admin

from apps.portfolios.models import Portfolio, PortfolioMedia


class PortfolioMediaInline(admin.TabularInline):
    model = PortfolioMedia
    extra = 0


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "freelancer",
        "category",
        "is_public",
        "is_featured",
        "completed_on",
        "view_count",
    )
    list_filter = ("is_public", "is_featured", "category")
    search_fields = ("title", "description", "freelancer__user__email", "public_id")
    autocomplete_fields = ("freelancer", "category")
    filter_horizontal = ("skills",)
    inlines = [PortfolioMediaInline]
    readonly_fields = (
        "public_id",
        "slug",
        "view_count",
        "search_text",
        "created_at",
        "updated_at",
    )
    list_editable = ("is_public", "is_featured")


@admin.register(PortfolioMedia)
class PortfolioMediaAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "kind", "caption", "order")
    list_filter = ("kind",)
    search_fields = ("caption", "portfolio__title")
    autocomplete_fields = ("portfolio",)
