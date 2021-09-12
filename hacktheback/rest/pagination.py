from rest_framework.pagination import PageNumberPagination


class StandardResultsPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = "per_page"
    page_size_query_description = "Number of results per page. Default is 12."
