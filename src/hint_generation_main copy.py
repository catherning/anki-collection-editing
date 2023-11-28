# from datetime import datetime
from typing import Callable, Optional
import yaml
from anki.collection import Collection
from loguru import logger
from german_utils import romanic_additional_hint_func, romanic_sorting_key

from src.utils.hint_generation_utils import (get_field_index, generate_global_hint,
                                   clean_hint, adapt_hint_to_note)
from src.utils.note_utils import find_notes_to_change
from src.utils.constants import CLOZE_TYPE

# TODO: make as arg


# create groups

def get_last_id():
    col = Collection(COL_PATH)

    notesID, original_model = find_notes_to_change(
        col,
        query=query,
        note_type_name=original_type_name,
        cloze_text_field=cloze_text_field,
    )