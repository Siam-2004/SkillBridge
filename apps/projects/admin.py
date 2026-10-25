from django.contrib import admin
from django.utils import timezone
from apps.projects.models import Project, Team, TeamMember, TeamInvitation, ProjectFile, ProjectComment, Review, Dispute

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('public_id', 'title', 'client', 'freelancer', 'final_price', 'status', 'deadline', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('public_id', 'title', 'client__username', 'freelancer__username')
    ordering = ('-created_at',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'reviewer', 'reviewee', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('project__title', 'reviewer__username', 'reviewee__username', 'feedback')
    ordering = ('-created_at',)

@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'raised_by', 'against', 'reason', 'status', 'created_at', 'resolved_at')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('project__title', 'raised_by__username', 'against__username', 'description', 'admin_resolution')
    ordering = ('-created_at',)
    readonly_fields = ('project', 'raised_by', 'against', 'reason', 'description', 'evidence', 'created_at', 'resolved_by', 'resolved_at')
    fields = ('project', 'raised_by', 'against', 'reason', 'description', 'evidence', 'created_at', 'status', 'admin_resolution', 'resolved_by', 'resolved_at')
    actions = ['resolve_disputes', 'dismiss_disputes']

    def save_model(self, request, obj, form, change):
        if obj.status in [Dispute.Status.RESOLVED, Dispute.Status.DISMISSED] and not obj.resolved_at:
            obj.resolved_by = request.user
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.action(description="Mark selected disputes as Resolved")
    def resolve_disputes(self, request, queryset):
        count = queryset.update(
            status=Dispute.Status.RESOLVED,
            resolved_by=request.user,
            resolved_at=timezone.now(),
            admin_resolution="Resolved by Admin action."
        )
        self.message_user(request, f"Resolved {count} dispute(s).")

    @admin.action(description="Dismiss selected disputes")
    def dismiss_disputes(self, request, queryset):
        count = queryset.update(
            status=Dispute.Status.DISMISSED,
            resolved_by=request.user,
            resolved_at=timezone.now(),
            admin_resolution="Dismissed by Admin action."
        )
        self.message_user(request, f"Dismissed {count} dispute(s).")
