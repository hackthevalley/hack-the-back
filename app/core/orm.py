from typing import Any, cast

from sqlalchemy.orm import QueryableAttribute, selectinload


def eager_load(attribute: Any):
    """Type-safe bridge for SQLModel relationships used at class level.

    SQLModel annotates a relationship by its instance value (for example,
    ``list[Forms_Answer]``), while SQLAlchemy replaces that attribute with a
    ``QueryableAttribute`` on the mapped class. Static analyzers cannot see the
    runtime replacement, so the cast belongs at this ORM boundary.
    """
    return selectinload(cast(QueryableAttribute[Any], attribute))
