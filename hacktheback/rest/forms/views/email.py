from rest_framework import generics
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from hacktheback.rest.account.serializers import SendCustomUrlSerializer


class SendCustomUrlAPIView(generics.GenericAPIView):
    permission_classes = (IsAdminUser, )
    serializer_class = SendCustomUrlSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.send(request=request)
        return Response(data={"success": True})
