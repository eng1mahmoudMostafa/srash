# pylint: disable=missing-docstring
"""Add sender_fingerprint (one-way HMAC) + backfill existing messages."""
from django.db import migrations, models


def backfill(apps, schema_editor):
    """Compute fingerprints for pre-existing messages by decrypting the
    stored (encrypted) sender username — safe, server-side only."""
    from common.crypto import decrypt_message, sender_fingerprint

    Message = apps.get_model("messages_app", "Message")
    for msg in (
        Message.objects.exclude(sender_username_ciphertext="")
        .filter(sender_fingerprint="")
        .iterator()
    ):
        try:
            username = decrypt_message(
                msg.sender_username_ciphertext, msg.sender_username_nonce
            )
        except Exception:
            continue
        msg.sender_fingerprint = sender_fingerprint(username)
        msg.save(update_fields=["sender_fingerprint"])


class Migration(migrations.Migration):

    dependencies = [
        ("messages_app", "0005_message_sender_username_ciphertext_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="sender_fingerprint",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
