"""Job moderation."""
from django.contrib import admin
from apps.marketplace.models import Job, JobAttachment, SavedJob

class JobAttachmentInline(admin.TabularInline):
    model = JobAttachment
    extra = 0
    readonly_fields = ("uploaded_by", "original_name", "created_at")

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "category", "budget", "reserved_amount", "status", "proposal_count", "is_featured", "is_flagged", "published_at")
    list_filter = ("status", "job_type", "complexity", "experience_level", "is_featured", "is_flagged", "team_required")
    search_fields = ("title", "description", "client__email", "public_id")
    autocomplete_fields = ("client", "category", "hired_freelancer")
    filter_horizontal = ("skills",)
    date_hierarchy = "created_at"
    inlines = [JobAttachmentInline]
    list_editable = ("is_featured",)
    ordering = ("-created_at",)
    # The budget and its reservation are money. They are set by the service
    # that moves the coins, so an administrator must not be able to nudge them
    # here and leave the wallet disagreeing with the job.
    readonly_fields = ("public_id", "slug", "budget", "reserved_amount", "budget_reserved_at", "reserve_transaction", "proposal_count", "view_count", "message_count", "search_text", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("client", "title", "slug", "category", "status")}),
        ("The work", {"fields": ("description", "requirements", "skills", "job_type", "complexity", "experience_level", "estimated_days", "people_required", "team_required")}),
        ("Money", {"fields": ("budget", "reserved_amount", "budget_reserved_at", "reserve_transaction")}),
        ("Moderation", {"fields": ("is_featured", "is_flagged", "moderation_note", "visibility_note")}),
        ("Record", {"fields": ("public_id", "proposal_count", "view_count", "message_count", "published_at", "created_at", "updated_at")}),
    )
    actions = ["flag", "unflag", "feature"]

    @admin.action(description="Flag the selected jobs for review")
    def flag(self, request, queryset):
        from apps.marketplace.services import moderate_job
        for job in queryset:
            moderate_job(job=job, admin=request.user, flagged=True, note="Flagged from the admin.")
        self.message_user(request, f"{queryset.count()} job(s) flagged.")

    @admin.action(description="Clear the flag on the selected jobs")
    def unflag(self, request, queryset):
        from apps.marketplace.services import moderate_job
        for job in queryset:
            moderate_job(job=job, admin=request.user, flagged=False)
        self.message_user(request, f"{queryset.count()} job(s) cleared.")

    @admin.action(description="Feature the selected jobs on the home page")
    def feature(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f"{updated} job(s) featured.")

@admin.register(JobAttachment)
class JobAttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "job", "uploaded_by", "created_at")
    search_fields = ("original_name", "job__title")
    autocomplete_fields = ("job", "uploaded_by")

@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ("user", "job", "created_at")
    search_fields = ("user__email", "job__title")
    autocomplete_fields = ("user", "job")