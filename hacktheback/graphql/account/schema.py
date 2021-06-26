import graphene
import graphql_jwt
import graphql_social_auth
from graphql_jwt.decorators import login_required

from hacktheback.graphql.account.mutations.current_user import (
    CurrentUserSetPassword,
    CurrentUserUpdate,
)
from hacktheback.graphql.account.mutations.user import (
    UserActivation,
    UserCreate,
    UserResendActivation,
    UserResetPassword,
    UserResetPasswordConfirm,
)
from hacktheback.graphql.account.types.user import UserType


class AccountMutations(graphene.ObjectType):
    """
    Mutations involving user accounts and authentication.
    """

    basic_auth_token = graphql_jwt.ObtainJSONWebToken.Field(
        description="Authenticate a user with their email and password. "
        "Returns a JWT (JSON Web Token) to be used for "
        "authenticated requests on this server. "
    )
    social_auth_token = graphql_social_auth.SocialAuthJWT.Field(
        description="Authenticate a user using an OAuth token from an "
        "authentication provider. Returns a JWT (JSON Web Token) "
        "to be used for authenticated requests on this server. "
    )
    refresh_auth_token = graphql_jwt.Refresh.Field(
        description="Refresh a user authentication token (JWT). "
    )
    verify_auth_token = graphql_jwt.Verify.Field(
        description="Confirm if a user authentication token (JWT) is valid."
    )
    user_create = UserCreate.Field()
    user_activation = UserActivation.Field()
    user_resend_activation = UserResendActivation.Field()
    user_reset_password = UserResetPassword.Field()
    user_reset_password_confirm = UserResetPasswordConfirm.Field()
    current_user_update = CurrentUserUpdate.Field()
    current_user_set_password = CurrentUserSetPassword.Field()


class AccountQueries(graphene.ObjectType):
    current_user = graphene.Field(UserType)

    @login_required
    def resolve_current_user(self, info, **kwargs):
        return info.context.user
