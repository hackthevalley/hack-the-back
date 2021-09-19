from django.contrib.auth import get_user_model
from django.db.models import Q
from django_filters import CharFilter, FilterSet

User = get_user_model()


class UserAdminFilter(FilterSet):
    search = CharFilter(
        method="search_by_terms", help_text="Search by full name or e-mail."
    )

    class Meta:
        model = User
        fields = ["is_staff", "is_superuser"]

    def search_by_terms(self, qs, name, value):
        for term in value.split():
            qs = qs.filter(
                Q(email__icontains=term)
                | Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
            )
        return qs
