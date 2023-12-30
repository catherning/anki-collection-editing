# from datetime import datetime
from typing import Callable, Optional
import re
from anki.collection import Collection
from anki.models import ModelManager, NotetypeDict
from bs4 import BeautifulSoup
from loguru import logger

from src.utils.field_utils import (extract_cloze_deletion,
                   get_field_index, print_note_content, proceed, get_cloze_data, get_cleaned_field_data,
                   breaklines_by_number)
from src.utils.constants import CLOZE_TYPE

def generate_global_hint(
    col: Collection,
    notesID: list[int],
    flds_in_hint: list[str],
    cloze_field_index: Optional[int],
    separator: str = ", ",
    sorting_field=None,
) -> list[tuple[str, str]]:
    """Generate the global hint that uses information from several notes.

    Args:
        col (Collection): The Anki Collection
        notesID (list[int]): The IDs of the notes for which to add the generated hint
        flds_in_hint (list[str]): The fields of the notes to use to generate the hint
        cloze_field_index (Optional[int]): The index of the cloze field if the notes
        are Cloze
        separator (str, optional): The string to add between each info from the fields in
            flds_in_hint. Defaults to ", ".
        sorting_field (_type_, optional): The field to use to sort the hint.
        Defaults to None.

    Returns:
        list[tuple[str, str]]: The list of global hint and the field info used for sorting
    """
    note_hints = []
    c_err = 0
    for nid in notesID:
        note = col.get_note(nid)

        # TODO: check if all notes have the same type? try if it's already checked.
        # Otherwise, do I need to check note type each time, not above for loop?
        
        if note._note_type["type"] == CLOZE_TYPE:
            content = get_cloze_data(flds_in_hint, cloze_field_index, separator, sorting_field, c_err, note)
            sorting_info = extract_cloze_deletion(
                cloze_field_index, note, sorting_field
            )
        else:
            content = get_cleaned_field_data(separator, note, flds_in_hint)  
            sorting_info = BeautifulSoup(note[sorting_field], "html.parser").text
            
        content = content[:len(content)-len(separator)] # remove last separator that is useless
        note_hints.append((content, sorting_info))

    if c_err > 0:
        logger.warning("There were errors generating the hint from cloze fields.")
        proceed()

    return note_hints

def append_if_not_first_group(query, group_separator, replace, note):
    if not group_separator:
        return replace

    query_field = query.split(":")[0].replace('"','')
    p = re.compile(r"(\d+)")
    m = p.search(query)
    if m:
        current_group_ID = int(m.group(1))
    
    # If user wants to replace the hints from scratch, then we must check if current note was already edited with the script
    # If they systematically want to append, not replace, then we skip the if below 
    if group_separator in note[query_field] and replace:
        note_groups = [int(el) for el in note[query_field].split(group_separator)]
        if current_group_ID == min(note_groups):
            replace = True
        elif current_group_ID in note_groups:
            replace = False
    return replace

def get_string_hint_from_list(note_hints_sorted, idx, hidding_char):
    hint = (
        "<br>".join(note_hints_sorted[:idx])
        + ("<br>" if idx != 0 else "")
        + hidding_char
        + ("<br>" if idx != len(note_hints_sorted) - 1 else "")
        + "<br>".join(note_hints_sorted[idx + 1 :])
    )
    
    return hint

def clean_hint(
    note_hints: list[tuple[str, str]],
    sorting_key: Optional[Callable],
    break_lines: bool = False,
) -> list[str]:
    """Clean the global hint by sorting and eventually adding break lines.

    Args:
        note_hints (list[tuple[str, str]]): The generated global hint to clean
        sorting_key (Optional[Callable]): The method to use to sort the hint
        (alphabetically, numerically). Ex: lambda row: int(row[1])
        break_lines (bool, optional): If you want breaklines. For now it only works
        if the sorting field is numerical (years) and it add breaklines between decades.
        Defaults to False.

    Returns:
        list[str]: The cleaned hints
    """
    note_hints_sorted = note_hints[:]
    note_hints_sorted.sort(key=sorting_key)
    # Issue with sorting pinyin for now:
    # ex yunmi < yunan whereas it should be the opposite (yu<yun)
    note_hints_sorted = [el[0] for el in note_hints_sorted]

    # TODO: Specifics to have lines breaks between decades when the sorting field is Year
    if break_lines:
        note_hints_sorted = breaklines_by_number(note_hints_sorted)
    return note_hints_sorted

def adapt_hint_to_note(
    col: Collection,
    query: str, 
    note_hints_sorted: list[str],
    original_model: ModelManager,
    nid: int,
    cur_note_hint: str,
    hint_field: str,
    cloze_field: str,
    additional_hint_field: Optional[str],
    additional_hint_func: Optional[Callable],
    query_field: Optional[str], #TODO: remove query or (query_field, group_separator) ?
    group_separator: Optional[str],
    replace: bool = False,
    # func=None,
) -> NotetypeDict:
    """Adapt the hint to a note by hiding the hint info of that note and update the note.

    Args:
        col (Collection): The Anki collection
        note_hints_sorted (list[str]): The cleaned global hint
        original_model (ModelManager): The type of the note
        nid (int): The ID of the note
        cur_note_hint (str): The hint corresponding to the current note
        hint_field (str): The field that will be populated with the hint
        cloze_field (str): The field with the cloze text (only for
        logging purposes)
        additional_hint_field (Optional[str]): The field with the eventual
        additional hint.
        If not given, then we hide the hint info with '?'. Otherwise, for now,
        we show the first character of the info in the additional_hint_field

    Raises:
        KeyError: Additional_hint_field is wrong

    Returns:
        NotetypeDict: The updated note
    """
    note = col.get_note(nid)
    idx = note_hints_sorted.index(cur_note_hint)
    if additional_hint_field is None:
        hidding_char = "?"
    else:
        if additional_hint_func is None:
            def additional_hint_func(text):
                return text[0]
        
        if original_model["type"] == CLOZE_TYPE:
            cloze_field_index = get_field_index(original_model, cloze_field)
            field_raw_text = extract_cloze_deletion(cloze_field_index, note, additional_hint_field)
        else:
            try:
                field_raw_text = note[additional_hint_field]
            except KeyError as e:
                logger.error(
                    "The field from which you want a more precise hint is missing"
                )
                raise e
                
        field_text = BeautifulSoup(field_raw_text, "html.parser").text
        hidding_char = additional_hint_func(field_text)


    hint = get_string_hint_from_list(note_hints_sorted, idx, hidding_char)

    logger.info(
        "Hint adapted for the current note"
        f" {print_note_content(cloze_field, original_model, note)}:"
    )
    for el in hint.split("<br>"):
        print(el)

    replace = append_if_not_first_group(query, group_separator, replace, note)

    if replace:
        note[hint_field] = hint
    else:
        hint = "<br><br>" + hint
        note[hint_field] += hint
    return note