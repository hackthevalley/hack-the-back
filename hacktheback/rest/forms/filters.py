import django_filters
from django.db.models import Q

from hacktheback.forms.models import FormResponse


class HackerApplicationResponsesAdminFilter(django_filters.FilterSet):
    user__search = django_filters.CharFilter(
        method="user_search_by_terms",
        help_text="Search by user's full name or e-mail.",
    )

    class Meta:
        model = FormResponse
        fields = ["applicant__status", "user__search"]

    def user_search_by_terms(self, qs, name, value):
        for term in value.split():
            qs = qs.filter(
                Q(user__email__icontains=term)
                | Q(user__first_name__icontains=term)
                | Q(user__last_name__icontains=term)
            )
        return qs
