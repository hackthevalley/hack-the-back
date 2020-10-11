import json

import graphene
from graphene.test import Client

from ....schema import schema
from ...resolvers import example_data
from ...types import Form

QUERY_FORMS = """
    query {
        forms {
            id
            title
            description
        }
    }
"""


def test_forms_query():
    """
    Example test.
    """
    client = Client(schema)
    executed = client.execute(QUERY_FORMS)
    expected = []

    for form in example_data:
        form["id"] = graphene.Node.to_global_id(Form._meta.name, form["id"])
        expected.append(form)

    assert json.dumps(executed, sort_keys=True) == json.dumps(
        {"data": {"forms": expected}}, sort_keys=True
    )
