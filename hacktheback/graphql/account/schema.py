import graphene
import graphql_jwt
import graphql_social_auth


class AccountMutations(graphene.ObjectType):
    """
    Mutations involving user accounts and authentication.
    """

    basic_auth_token = graphql_jwt.ObtainJSONWebToken.Field(
        description="Mutation that authenticates a user with their email "
        + "and password. Returns a JWT (JSON Web Token) to be used for "
        + "authenticated requests on this server."
    )
    social_auth_token = graphql_social_auth.SocialAuthJWT.Field(
        description="Mutation that authenticates a user using an OAuth token "
        + "from an authentication provider. Returns a JWT (JSON Web Token) "
        + "to be used for authenticated requests on this server."
    )
    refresh_auth_token = graphql_jwt.Refresh.Field(
        description="Mutation that refreshes a user authentication token ("
        "JWT). "
    )
    verify_auth_token = graphql_jwt.Verify.Field(
        description="Mutation that confirms if a user authentication token "
        + "(JWT) is valid."
    )
