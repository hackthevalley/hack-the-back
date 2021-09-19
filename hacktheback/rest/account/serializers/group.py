from django.contrib.auth.models import Group, Permission
from rest_framework import serializers

from .user import UserSerializer


class GroupSerializer(serializers.ModelSerializer):
    permissions = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(), many=True
    )
    users = UserSerializer(many=True, source="user_set")

    class Meta:
        model = Group
        fields = ["id", "name", "permissions", "users"]
