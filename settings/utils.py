import ast
import os
from typing import List, Optional


def get_list_environ(
    name: str, default: Optional[List[str]] = None, separator: str = ","
) -> List[str]:
    """
    Return a list separated by "separator" in the value of the environment
    variable "name" if it exists, or simply "default" if it doesn't. "default"
    defaults to None. "separator" defaults to ",".
    """
    if name in os.environ:
        value = os.environ.get(name)
        return [item.strip() for item in value.split(separator)]
    return default


def get_bool_environ(name: str, default: Optional[bool] = None) -> bool:
    """
    Return the boolean value of the environment variable "name" if it exists,
    or simply "default" if it doesn't. "default" defaults to None.
    """
    if name in os.environ:
        value = os.environ.get(name)
        try:
            return bool(ast.literal_eval(value))
        except ValueError as e:
            raise ValueError(f"{value} is an invalid value for {name}") from e
    return default
