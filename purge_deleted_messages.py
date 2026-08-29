"""Permanently purge soft-deleted messages older than the retention window.

Run periodically (e.g. via a cron scheduler) as part of the data-retention
policy: `python manage.py purge_deleted_messages`.
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from messages_app.models import Message


class Command(BaseCommand):
    help = "Permanently delete soft-deleted messages past the retention window."

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=settings.RETENTION_PURGE_DAYS)
        queryset = Message.objects.filter(
            status=Message.Status.DELETED,
            deleted_at__lt=cutoff,
        )
        count = queryset.count()
        queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"Purged {count} message(s)."))