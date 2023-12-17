# from datetime import datetime
from typing import Callable, Optional
from anki.collection import Collection
from loguru import logger

from utils.note_utils import find_notes_to_change, get_col_path

# TODO: make as arg


# create groups

def get_last_id(col,original_type_name,query_field,group_separator):
    
    i=0
    while True:
        i+=1
        query = f'"{query_field}:re:(^|{group_separator}){i}({group_separator}|$)"'

        try: 
            notesID, _ = find_notes_to_change(
                col,
                query=query,
                note_type_name=original_type_name,
                override_confirmation = True
            )
        except ValueError:
            return i-1

def get_notes_to_edit(col,original_type_name):
    query = f'-is:suspended tag:marked'
    return find_notes_to_change(
                col,
                query=query,
                note_type_name=original_type_name,
                # override_confirmation = True
            )

COL_PATH = get_col_path("src/config.yaml")
col = Collection(COL_PATH)
hint_field = "Synonyms"
original_type_name = "Chinois"
current_max_id = get_last_id(col,
                             original_type_name,
                             f"{hint_field} group",group_separator= ", ")
print(current_max_id)

notesID, _ = get_notes_to_edit(col,original_type_name)
for noteID in notesID[:10]:
    note = col.get_note(noteID)
    print(note["Simplified"])
print(len(notesID))