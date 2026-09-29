"""Conversation and message administration.
Message bodies are deliberately not searchable from the changelist: an
administrator can open a conversation when a dispute needs it, but the admin
is not a tool for reading private chat at scale.
"""
from django.contrib import admin
from apps.messaging.models import Conversation, ConversationParticipant, Message

class ParticipantInline(admin.TabularInline):
    model=ConversationParticipant
    extra=0
    autocomplete_fields=("user",)

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display=("created_at","conversation_type","job","agreement","status","message_count","updated_at")
    list_filter=("conversation_type","status","created_at")
    search_fields=("job__title","public_id")
    autocomplete_fields=("job",)
    date_hierarchy="created_at"
    inlines=[ParticipantInline]
    readonly_fields=("public_id","message_count","created_at","updated_at")

    @admin.display(description="Messages")
    def message_count(self,obj):
        return obj.messages.count()

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display=("created_at","conversation","sender","kind","preview")
    list_filter=("kind","created_at")
    search_fields=("sender__email",)
    date_hierarchy="created_at"
    readonly_fields=[f.name for f in Message._meta.fields]

    def has_add_permission(self,request):
        return False

    def has_change_permission(self,request,obj=None):
        return False