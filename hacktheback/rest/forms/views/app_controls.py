from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from hacktheback.rest.permissions import AdminSiteModelPermissions
from hacktheback.forms.models import Form
from hacktheback.rest.forms.serializers import FormControllerSerializer

class AppControlsViewSet(viewsets.ModelViewSet):
    queryset = Form.objects.all()
    permission_classes = (AdminSiteModelPermissions,)
    serializer_class = FormControllerSerializer

    def partial_update(self, request, *args, **kwargs):
        """
        The request from the frontend will be in the form of:
        {
            "start_at": "respective ISO time string",
            "end_at": "respective ISO time string",    
        }
        """
        instance = self.get_object()

        new_start_at = request.data.get("start_at")
        new_end_at = request.data.get("end_at")

        response = super().partial_update(request, *args, **kwargs)
        return Response(data=self.get_serializer(instance).data, status=status.HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        form = self.get_queryset().first()
        serializer = self.get_serializer(form)
        return Response(serializer.data)
