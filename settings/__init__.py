"""
Django settings for hacktheback project.

For more information on settings, see:
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see:
https://docs.djangoproject.com/en/3.2/ref/settings/
"""

# Authentication settings
from .auth import *

# Common settings
from .common import *

# GraphQL API (Graphene) settings
from .graphql import *

# REST API (Django Rest Framework) settings
from .rest import *
