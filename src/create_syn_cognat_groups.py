# from datetime import datetime
from typing import Callable, Optional
from anki.collection import Collection
from loguru import logger

from utils.note_utils import find_notes_to_change, get_col_path

# TODO: make as arg


# create groups

def get_last_id(query_field,group_separator):
    COL_PATH = get_col_path("src/config.yaml")
    col = Collection(COL_PATH)
    original_type_name = "Chinois"
    
    i=0
    while True:
        i+=1
        query = f'"{query_field}:re:(^|{group_separator}){i}({group_separator}|$)"'

        notesID, _ = find_notes_to_change(
            col,
            query=query,
            note_type_name=original_type_name,
        )
        if not notesID:
            return i-1
    

hint_field = "Synonym"
current_max_id = get_last_id(f"{hint_field} group",group_separator= ", ")
print(current_max_id)