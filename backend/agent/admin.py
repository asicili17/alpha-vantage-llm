from django.contrib import admin

from agent.models import Artifact


@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
	list_display = (
		"transcript",
		"artifact_type",
		"model",
		"prompt_version",
		"created_at",
	)
	list_filter = ("artifact_type", "model", "prompt_version", "created_at")
	search_fields = ("transcript__symbol", "transcript__quarter", "model")
	ordering = ("-created_at",)
