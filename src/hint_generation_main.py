# from datetime import datetime
from typing import Callable, Optional
import yaml
from anki.collection import Collection
from loguru import logger
from german_utils import romanic_additional_hint_func, romanic_sorting_key

from hint_generation_utils import (get_field_index, generate_global_hint,
                                   clean_hint, adapt_hint_to_note)
from utils import find_notes_to_change
from constants import CLOZE_TYPE
# TODO: make as arg

def generate_hint_main(
    note_type_name: str,
    query: str,
    flds_in_hint: list[str],
    hint_field: str,
    additional_hint_field: Optional[str],
    additional_hint_func: Optional[Callable],
    sorting_key: Optional[Callable],
    sorting_field: Optional[str],
    cloze_field: Optional[str],
    query_field: Optional[str],
    group_separator: Optional[str],
    col: Optional[Collection] = None,
    separator: str = ", ",
    break_lines: bool = False,
    replace: bool = False,
) -> None:
    """Main method to generate hints for several notes using their information.

    Args:
        note_type_name (str): The name of the common note type
        query (str): The query to find the notes to update
        flds_in_hint (list[str]): The fields from where to extract the hint info.
        Ex: ["c2","c1"] if the notes are Cloze notes
        hint_field (str): The field where the hint will be stored in
        additional_hint_field (Optional[str]): The field from where to extract
        the eventual additional hint in the form of the first character of the field
        sorting_key (Optional[Callable]): The key to sort the hints
        sorting_field (Optional[str]): The field used for sorting
        cloze_field (Optional[str]): The name of the cloze field if notes are Cloze.
        separator (str, optional): The string to separate the info from flds_in_hint.
        Defaults to ", ".
        break_lines (bool, optional): If you want breaklines. For now it only works
        if the sorting field is numerical (years) and it add breaklines between decades.
        Defaults to False.
        replace (bool, optional): If you want to replace, not append the hing field.
        Defaults to False.

    Raises:
        ValueError: If there is only 0 or 1 note found with the query
    """
    if col is None:
        col = Collection(COL_PATH)
    notesID, original_model = find_notes_to_change(
        col, query, note_type_name, verbose=True, cloze_text_field=cloze_field
    )

    if len(notesID) < 2:
        raise ValueError(
            "There is only one note. You can't generate hints based on several notes."
        )

    cloze_field_index = (
        get_field_index(original_model, cloze_field)
        if original_model["type"] == CLOZE_TYPE
        else None
    )

    note_hints = generate_global_hint(
        col, notesID, flds_in_hint, cloze_field_index, separator, sorting_field
    )

    # If the first hint info is numeric, then sort as int
    # (not int as strings, otherwise "10"<"6")
    try:
        if sorting_key is None:
            [int(el[1]) for el in note_hints]

            def sorting_key(row):
                return int(row[1])

    except ValueError:
        if sorting_key is None:
            def sorting_key(row):
                return row[1].lower()
            

    try:
        note_hints_sorted = clean_hint(
            note_hints, sorting_key=sorting_key, break_lines=break_lines
        )
    except Exception as e:
        logger.error(e)
        logger.error("There might have been an error with the sorting key.")
        exit()
        # new_sorting_key = lambda row: sorting_key(
        #                       get_first_el(row))
        # note_hints_sorted = clean_hint(note_hints,break_lines,
        #               sorting_key=new_sorting_key)

    logger.info("The hint that will be repercuted to all notes is:")
    for hint in note_hints_sorted:
        logger.info(hint)

    notes = []
    for nid, cur_note_hint in zip(notesID, note_hints):
        note = adapt_hint_to_note(
            col,
            query,
            note_hints_sorted,
            original_model,
            nid,
            cur_note_hint[0],
            hint_field,
            cloze_field,
            additional_hint_field,
            additional_hint_func,
            replace = replace,
            query_field = query_field,
            group_separator = group_separator
        )
        notes.append(note)

    logger.info("Confirm the hint generation and save notes ? (Y/n)")
    if input() == "Y":
        col.update_notes(notes)
        logger.success("New note hints saved in the collection!")

    col.close()


if __name__ == "__main__":
    
    config = yaml.load(open("src/config.yaml"))
    COL_PATH = config["collection_path"]
    
    for note_type_name in ["Chinois","Allemand"]:
        break_lines = False

        cloze_field = ""  # "Text"
        group_separator = ", "

        match note_type_name:
            case "Chinois":
                flds_in_hint = ["Simplified", "Meaning"]
                separator = " "
                sorting_field = additional_hint_field = "Pinyin.1"
                sorting_key = None
                additional_hint_func = None

            case "Allemand":
                sorting_key = romanic_sorting_key
                additional_hint_func = romanic_additional_hint_func
                         
                flds_in_hint = ["German", "French/English"]
                separator = " | "  # should add spaces
                sorting_field = additional_hint_field = "German"

        for hint_field in ["Synonyms","Cognats"]:
            query_field = f"{hint_field} group"
                
            # Itère sur query : chiffre par chiffre. Si retrouve une carte, doit append le hint, pas remplacer
            i=0
            while True:
                i+=1
                query = f'"{query_field}:re:(^|{group_separator}){i}({group_separator}|$)"'
                
                try:
                    generate_hint_main(
                        note_type_name,
                        query,
                        flds_in_hint,
                        hint_field,
                        additional_hint_field,
                        additional_hint_func,
                        sorting_key,
                        sorting_field,
                        separator=separator,
                        break_lines=break_lines,
                        cloze_field=cloze_field,
                        # col=col,
                        replace = True,
                        query_field = query_field,
                        group_separator = group_separator
                    )
                except ValueError as e:
                    print(query, e)
                    break
