from django.http.response import FileResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from hacktheback.forms.models import AnswerFile, Form
from hacktheback.forms.serializers.answer_file import (
    HackerApplicationAnswerFileSerializer,
)
from hacktheback.rest.permissions import IsOwner


@extend_schema(tags=["Forms"])
class HackerApplicationAnswerFileViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = AnswerFile.objects.filter(
        question__form__type=Form.FormType.HACKER_APPLICATION,
        question__form__is_draft=False,
    )
    serializer_class = HackerApplicationAnswerFileSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        """
        Query by the current user as well.
        """
        self.queryset = self.queryset.filter(user=self.request.user)
        return super().get_queryset()

    @extend_schema(
        summary="List Files for the Current User's Hacker Application"
    )
    def list(self, request, *args, **kwargs):
        """
        List all files uploaded by the current user for their hacker
        application.
        """
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Retrieve a File for the Current User's Hacker Application"
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a files uploaded by the current user for their hacker
        application.
        """
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Upload a File for the Current User's Hacker Application",
    )
    @action(methods=["POST"], detail=False)
    def upload(self, request):
        """
        Upload a file for the current user's hacker application.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(
        summary="Download a File for the Current User's Hacker Application",
        responses={
            "200": OpenApiResponse(
                description="A file that can be downloaded."
            )
        },
    )
    @action(methods=["GET"], detail=True)
    def download(self, request, pk=None):
        """
        Download a file for the current user's hacker application.
        """
        answer_file = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(self.request, answer_file)
        return FileResponse(answer_file.file.open())
