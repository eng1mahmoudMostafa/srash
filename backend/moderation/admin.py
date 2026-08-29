from django.contrib import admin

from moderation.models import AbuseEvent, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "reporter", "reason", "status", "created_at")
    list_filter = ("status", "reason", "created_at")
    search_fields = ("message__id", "reporter__username")
    actions = ["mark_resolved"]

    @admin.action(description="حلّ البلاغات المحددة")
    def mark_resolved(self, request, queryset):
        queryset.update(status=Report.Status.RESOLVED)


@admin.register(AbuseEvent)
class AbuseEventAdmin(admin.ModelAdmin):
    list_display = ("ip_hmac", "action", "created_at", "expires_at")
    list_filter = ("action", "created_at")
    search_fields = ("ip_hmac",)