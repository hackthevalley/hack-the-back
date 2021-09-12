from django.http.response import FileResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from hacktheback.forms.models import AnswerFile, Form
from hacktheback.rest.forms.serializers import (
    HackerApplicationAnswerFileAdminSerializer,
    HackerApplicationAnswerFileSerializer,
)
from hacktheback.rest.permissions import AdminSiteModelPermissions, IsOwner


@extend_schema(tags=["Hacker APIs", "Forms"])
@extend_schema_view(
    list=extend_schema(
        summary="List Files for the Current User's Hacker Application",
        description="List all files uploaded by the current user for their "
                    "hacker application."
    ),
    retrieve=extend_schema(
        summary="Retrieve a File for the Current User's Hacker Application",
        description="Retrieve a file uploaded by the current user for their "
                    "hacker application."
    ),
    upload=extend_schema(
        summary="Upload a File for the Current User's Hacker Application",
    ),
    download=extend_schema(
        summary="Download a File for the Current User's Hacker Application",
        responses={
            "200": OpenApiResponse(
                description="A file that can be downloaded."
            )
        },
    )
)
class HackerApplicationAnswerFileViewSet(viewsets.ReadOnlyModelViewSet):
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

    @action(methods=["POST"], detail=False)
    def upload(self, request):
        """
        Upload a file for the current user's hacker application.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(methods=["GET"], detail=True)
    def download(self, request, pk=None):
        """
        Download a file for the current user's hacker application.
        """
        answer_file = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(self.request, answer_file)
        return FileResponse(answer_file.file.open())


@extend_schema(tags=["Admin APIs", "Forms"])
@extend_schema_view(
    list=extend_schema(
        summary="List Files for All Hacker Applications",
        description="List all files uploaded by users for their hacker "
                    "applications."
    ),
    retrieve=extend_schema(
        summary="Retrieve a File for a Hacker Application",
        description="Retrieve a file uploaded by any user for their hacker "
                    "application."
    ),
    upload=extend_schema(
        summary="Upload a File for a User's Hacker Application",
    ),
    download=extend_schema(
        summary="Download a File for a Hacker Application",
        responses={
            "200": OpenApiResponse(
                description="A file that can be downloaded."
            )
        },
    )
)
class HackerApplicationAnswerFileAdminViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AnswerFile.objects.filter(
        question__form__type=Form.FormType.HACKER_APPLICATION,
    )
    serializer_class = HackerApplicationAnswerFileAdminSerializer
    permission_classes = (AdminSiteModelPermissions,)
    parser_classes = [MultiPartParser]

    @action(methods=["POST"], detail=False)
    def upload(self, request):
        """
        Upload a file for a user's hacker application.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(methods=["GET"], detail=True)
    def download(self, request, pk=None):
        """
        Download a file for a user's hacker application.
        """
        answer_file = get_object_or_404(self.get_queryset(), pk=pk)
        return FileResponse(answer_file.file.open())
