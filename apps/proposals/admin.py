from django.contrib import admin
from apps.proposals.models import Proposal, ProposalAttachment

class ProposalAttachmentInline(admin.TabularInline):
    model = ProposalAttachment
    extra = 0
    readonly_fields = ('created_at',)

@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ('public_id', 'job', 'freelancer', 'proposed_amount', 'estimated_days', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('public_id', 'job__title', 'freelancer__email', 'freelancer__first_name', 'freelancer__last_name', 'cover_letter')
    raw_id_fields = ('job', 'freelancer')
    inlines = [ProposalAttachmentInline]
    readonly_fields = ('public_id', 'created_at', 'updated_at', 'responded_at')
