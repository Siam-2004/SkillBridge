"""Profiles, categories and skills."""

from django.contrib import admin

from apps.profiles.models import (
    Category,
    ClientProfile,
    Education,
    Experience,
    FreelancerProfile,
    FreelancerSkill,
    Skill,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "order", "is_active", "is_featured")
    list_filter = ("is_active", "is_featured", "parent")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("order", "is_active", "is_featured")
    ordering = ("order", "name")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "category", "usage_count", "is_active")
    list_filter = ("is_active", "category")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("category",)
    readonly_fields = ("usage_count",)
    ordering = ("-usage_count", "name")


class ExperienceInline(admin.TabularInline):
    model = Experience
    extra = 0


class EducationInline(admin.TabularInline):
    model = Education
    extra = 0


class FreelancerSkillInline(admin.TabularInline):
    model = FreelancerSkill
    extra = 0
    autocomplete_fields = ("skill",)


@admin.register(FreelancerProfile)
class FreelancerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "professional_title",
        "experience_level",
        "availability",
        "completed_projects",
        "is_available_for_hire",
        "is_profile_complete",
    )
    list_filter = (
        "availability",
        "experience_level",
        "is_available_for_hire",
        "is_profile_complete",
    )
    search_fields = ("user__email", "user__username", "professional_title", "bio")
    autocomplete_fields = ("user",)
    inlines = [FreelancerSkillInline, ExperienceInline, EducationInline]
    readonly_fields = (
        "completed_projects",
        "active_projects",
        "total_earned",
        "proposals_submitted",
        "proposals_accepted",
        "on_time_deliveries",
        "late_deliveries",
        "search_text",
    )


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "company_name",
        "industry",
        "jobs_posted",
        "total_hired",
        "total_spent",
    )
    list_filter = ("industry", "company_size")
    search_fields = ("user__email", "user__username", "company_name")
    autocomplete_fields = ("user",)
    readonly_fields = (
        "jobs_posted",
        "active_projects",
        "completed_projects",
        "total_hired",
        "total_spent",
        "search_text",
    )
