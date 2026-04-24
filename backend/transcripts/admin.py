from django.contrib import admin

from transcripts.models import Transcript, TranscriptChunk, TranscriptTurn


@admin.register(Transcript)
class TranscriptAdmin(admin.ModelAdmin):
	list_display = (
		"symbol",
		"quarter",
		"source",
		"company_name",
		"call_date",
		"fetched_at",
	)
	list_filter = ("source", "quarter", "call_date")
	search_fields = ("symbol", "quarter", "company_name")
	ordering = ("-fetched_at",)


@admin.register(TranscriptTurn)
class TranscriptTurnAdmin(admin.ModelAdmin):
	list_display = ("transcript", "turn_index", "speaker", "title", "created_at")
	list_filter = ("created_at",)
	search_fields = ("transcript__symbol", "transcript__quarter", "speaker", "content")
	ordering = ("transcript", "turn_index")


@admin.register(TranscriptChunk)
class TranscriptChunkAdmin(admin.ModelAdmin):
	list_display = (
		"transcript",
		"chunk_index",
		"section",
		"speaker",
		"token_count",
		"created_at",
	)
	list_filter = ("section", "created_at")
	search_fields = ("transcript__symbol", "transcript__quarter", "speaker", "text")
	ordering = ("transcript", "chunk_index")
