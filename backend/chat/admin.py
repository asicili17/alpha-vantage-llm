from django.contrib import admin

from chat.models import Conversation, Message


class MessageInline(admin.TabularInline):
	model = Message
	extra = 0
	fields = ("message_index", "role", "content", "created_at")
	readonly_fields = ("message_index", "role", "content", "created_at")
	ordering = ("message_index",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
	list_display = ("id", "current_transcript", "created_at", "updated_at")
	list_filter = ("created_at", "updated_at")
	search_fields = ("id", "current_transcript__symbol", "current_transcript__quarter")
	ordering = ("-updated_at",)
	inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
	list_display = ("conversation", "message_index", "role", "created_at")
	list_filter = ("role", "created_at")
	search_fields = ("conversation__id", "content")
	ordering = ("conversation", "message_index")
