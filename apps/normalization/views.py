from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import status
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.normalization.models import NormalizedEvent
from apps.normalization.serializers import NormalizedEventSerializer


class LowConfidenceQueueView(APIView):
    """Inspect low-confidence normalized events for manual review workflows."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(
        operation_id="low_confidence_events",
        summary="List low-confidence normalized events",
        parameters=[
            OpenApiParameter(
                name="threshold",
                type=float,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Return events where confidence_score is below this threshold (default: 0.7).",
            )
        ],
        responses={
            200: inline_serializer(
                name="LowConfidenceEventListResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "results": NormalizedEventSerializer(many=True),
                },
            )
        },
    )
    def get(self, request, *args, **kwargs):
        threshold = float(request.query_params.get("threshold", "0.7"))
        events = NormalizedEvent.objects.filter(confidence_score__lt=threshold).order_by("-created_at")[:100]
        serializer = NormalizedEventSerializer(events, many=True)
        return Response({"count": len(serializer.data), "results": serializer.data}, status=status.HTTP_200_OK)
