from pydantic import BaseModel
from .metadata import Metadata


def get_keyword_for_field(model_class: type[BaseModel], field_name: str) -> str | None:
    field_info = model_class.model_fields.get(field_name)
    if field_info and field_info.metadata:
        for item in field_info.metadata:
            if isinstance(item, Metadata):
                return item.keyword
    return None
