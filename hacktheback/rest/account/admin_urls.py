from rest_framework.routers import SimpleRouter

from hacktheback.rest.account.views import (
    GroupAdminViewSet,
    PermissionAdminViewSet,
    UserAdminViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register("users", UserAdminViewSet)
router.register("permissions", PermissionAdminViewSet)
router.register("groups", GroupAdminViewSet)

urlpatterns = router.urls
