from rest_framework import serializers

from moderation.models import Report


class ReportSerializer(serializers.ModelSerializer):
    reason = serializers.ChoiceField(choices=Report.Reason.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)

    class Meta:
        model = Report
        fields = ["reason", "note"]

    def create(self, validated_data):
        validated_data["message"] = validated_data.pop("message_obj")
        validated_data["reporter"] = validated_data.pop("reporter_obj")
        return Report.objects.create(**validated_data)