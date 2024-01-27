# from datetime import datetime
from typing import Callable, Optional
from anki.collection import Collection
from loguru import logger
from langdetect import detect
import re

from src.utils.note_utils import find_notes, get_col_path
from src.utils.field_utils import extract_text_from_field
# TODO: make as arg

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

def assign_group_id(col,noteIDs,group_name,group_id):
    notes = []
    for noteID in noteIDs:
        note = col.get_note(noteID)
        note[group_name] = group_id
        notes.append(note)
    col.save_note(notes)

if __name__ == "__main__":

    COL_PATH = get_col_path("src/config.yaml")
    col = Collection(COL_PATH)
    hint_field = "Synonyms"
    group_name = f"{hint_field} group"
    main_signification_field = "Simplified"
    original_type_name = "Chinois"
    current_max_id = get_last_id(col,
                                original_type_name,
                                group_name,group_separator= ", ")

    print(current_max_id)
    overall_edited_notes = set()

    notesID, _ = get_notes_to_edit(col,original_type_name)
    for noteID in notesID:
        note = col.get_note(noteID)
        print(note[main_signification_field])

        if noteID in overall_edited_notes:
            logger.warning("The note was already found in a group! What to do ?")
            breakpoint()

        
        if note[hint_field] and not note[group_name]:
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
                    notes_of_the_group = [noteID]
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
                    
                    assign_group_id(col,notes_of_the_group,group_name,group_id)
                    overall_edited_notes.update(notes_of_the_group)

                        
                case "Allemand":
                    lines = field_text.splitlines()
                    group_elements = [line for line in lines if detect(line) == 'de']
        
        
        elif note[hint_field] and note[group_name]:
            # The group ID is already set: what do I need to edit? I must call this from the new note that is added to the group
            breakpoint()
            pass
        elif not note[hint_field] :
            # It's not in a group yet. I need to find the group using word embeddings
            pass
        else:
            # What else ?
            breakpoint()
            pass
        
    print(len(notesID))