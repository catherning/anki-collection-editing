# from datetime import datetime
from typing import Callable, Optional
from anki.collection import Collection
from loguru import logger
from langdetect import detect
import re

from src.utils.note_utils import find_notes, get_col_path
from src.utils.field_utils import extract_text_from_field
# TODO: make as arg


# create groups

def get_last_id(col,original_type_name,query_field,group_separator):
    
    i=0
    while True:
        i+=1
        query = f'"{query_field}:re:(^|{group_separator}){i}({group_separator}|$)"'

        try: 
            notesID, _ = find_notes(
                col,
                query=query,
                note_type_name=original_type_name,
                override_confirmation = True
            )
        except ValueError:
            return i-1

def get_notes_to_edit(col,original_type_name):
    query = f'-is:suspended tag:marked'
    return find_notes(
                col,
                query=query,
                note_type_name=original_type_name,
                override_confirmation = True
            )

COL_PATH = get_col_path("src/config.yaml")
col = Collection(COL_PATH)
hint_field = "Synonyms"
main_signification_field = "Simplified"
original_type_name = "Chinois"
current_max_id = get_last_id(col,
                             original_type_name,
                             f"{hint_field} group",group_separator= ", ")

print(current_max_id)

notesID, _ = get_notes_to_edit(col,original_type_name)
for noteID in notesID:
    note = col.get_note(noteID)
    print(note[main_signification_field])
    
    if note[hint_field] and not note[f"{hint_field} group"]:
        # It's a group that I created manually : 
        # just need to find the other notes in the group and create the group ID
        print(note[hint_field])
        hints = note[hint_field].split()
        field_text = extract_text_from_field(note,hint_field)
        match original_type_name:
            # TODO: make it more flexible
            case "Chinois":
                # TODO: important !!! take into account the spaces in the hints that mean that they are different groups
                # Find the notes with the same signification/cognats, id est, that are in the same group 
                group_elements = re.findall("[\u4e00-\u9FFF]+|\n", field_text)
                notes_of_the_group = []
                for el in group_elements:
                    query = f"{main_signification_field}:{el}"
                    found_group_notes, _ = find_notes(
                        col,
                        query=query,
                        note_type_name=original_type_name,
                        override_confirmation = True
                    )
                    if len(found_group_notes) == 1:
                        print("ok")
                        notes_of_the_group += found_group_notes
                    else:
                        logger.warning("TODO: what to do if there's several notes with the same signification?")
                
                # TODO: assign the same group number to all the notes of the group
                    
            case "Allemand":
                lines = field_text.splitlines()
                group_elements = [line for line in lines if detect(line) == 'de']
       
    
    elif note[hint_field] and note[f"{hint_field} group"]:
        # The group ID is already set: what do I need to edit?
        pass
    else:
        # It's a new group to create
        pass
    
print(len(notesID))