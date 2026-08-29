from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from users.models import Profile, Subscription, User, UserSettings


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "is_active", "is_staff", "accept_anonymous", "created_at")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("أنظمة مجهولة", {"fields": ("accept_anonymous",)}),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "is_verified", "created_at")
    search_fields = ("user__username", "display_name")
    list_filter = ("is_verified",)


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "allow_anonymous", "gap_minutes", "notify_new_message")
    search_fields = ("user__username",)


@admin.action(description="موافقة وتفعيل التوثيق 30 يومًا")
def approve_subscriptions(modeladmin, request, queryset):
    for sub in queryset:
        sub.activate()


@admin.action(description="رفض الطلب وإزالة التوثيق")
def reject_subscriptions(modeladmin, request, queryset):
    for sub in queryset:
        sub.reject()


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "reference", "user", "status", "amount_egp", "transfer_note",
        "created_at", "expires_at",
    )
    list_filter = ("status",)
    search_fields = ("reference", "user__username")
    actions = (approve_subscriptions, reject_subscriptions)