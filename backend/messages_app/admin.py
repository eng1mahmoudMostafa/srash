from django.contrib import admin

from messages_app.models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "status", "is_read", "created_at")
    list_filter = ("status", "is_read", "created_at")
    search_fields = ("recipient__username", "id")
    readonly_fields = ("body_ciphertext", "body_nonce", "created_at")