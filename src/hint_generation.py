# from datetime import datetime
from typing import Callable
from typing import Optional

from anki.collection import Collection
from anki.models import ModelManager
from anki.models import NotetypeDict
from anki_utils import COL_PATH
from bs4 import BeautifulSoup
from loguru import logger
from utils import CLOZE_TYPE
from utils import extract_cloze_deletion
from utils import find_notes_to_change
from utils import get_field_index
from utils import print_note_content
from utils import proceed
from utils import truncate_field

# from anki.notes import Note


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
        content = ""
        if note._note_type["type"] == CLOZE_TYPE:
            for cloze in flds_in_hint:
                try:
                    content += (
                        extract_cloze_deletion(cloze_field_index, note, cloze)
                        + separator
                    )
                except Exception:
                    logger.error(
                        "Hint could not be extracted from cloze field. Is the note type"
                        " Cloze or the given cloze number correct?"
                    )
                    c_err += 1
                # TODO: warnings / error if cloze type but fields given or the opposite
            sorting_info = extract_cloze_deletion(
                cloze_field_index, note, sorting_field
            )
        else:
            for field in flds_in_hint:
                text = BeautifulSoup(note[field], "html.parser").text
                clean_text = truncate_field(text.replace("\n", separator), 60)
                content += clean_text + separator
            sorting_info = BeautifulSoup(note[sorting_field], "html.parser").text
        note_hints.append((content, sorting_info))

    if c_err > 0:
        logger.warning("There were errors generating the hint from cloze fields.")
        proceed()

    return note_hints


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
    note_hints_sorted.sort(key=sorting_key)  # TODO: add sort field. Ex: pinyin
    # Issue with sorting pinyin for now:
    # ex yunmi < yunan whereas it should be the opposite (yu<yun)
    note_hints_sorted = [el[0] for el in note_hints_sorted]

    # Specifics to have lines breaks between decades when the sorting field is Year
    if break_lines:
        note_hints_spaced = []
        previous_decimal = note_hints_sorted[0][2]
        for i, hint in enumerate(note_hints_sorted):
            if hint[2] != previous_decimal:
                note_hints_spaced.append("")
            note_hints_spaced.append(hint)
            previous_decimal = hint[2]
        note_hints_sorted = note_hints_spaced
    return note_hints_sorted


def adapt_hint_to_note(
    col: Collection,
    note_hints_sorted: list[str],
    original_model: ModelManager,
    nid: int,
    cur_note_hint: str,
    hint_field: str,
    cloze_field: str,
    additional_hint_field: Optional[str],
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
        if original_model["type"] == CLOZE_TYPE:
            cloze_field_index = (
                get_field_index(original_model, cloze_field)
                if original_model["type"] == CLOZE_TYPE
                else None
            )
            hidding_char = BeautifulSoup(
                extract_cloze_deletion(cloze_field_index, note, additional_hint_field),
                "html.parser",
            ).text[0]
        else:
            try:
                hidding_char = BeautifulSoup(
                    note[additional_hint_field], "html.parser"
                ).text[0]
            except KeyError as e:
                logger.error(
                    "The field from which you want a more precise hint is missing"
                )
                raise e

    hint = (
        "<br>".join(note_hints_sorted[:idx])
        + ("<br>" if idx != 0 else "")
        + hidding_char
        + ("<br>" if idx != len(note_hints_sorted) - 1 else "")
        + "<br>".join(note_hints_sorted[idx + 1 :])
    )

    logger.info(
        "Hint adapted for the current note"
        f" {print_note_content(cloze_field, original_model, note)}:"
    )
    for el in hint.split("<br>"):
        print(el)

    if replace:
        note[hint_field] = hint
    else:
        note[hint_field] += hint
    return note


def generate_hint(
    note_type_name: str,
    query: str,
    flds_in_hint: list[str],
    hint_field: str,
    additional_hint_field: Optional[str],
    sorting_key: Optional[Callable],
    sorting_field: Optional[str],
    cloze_field: Optional[str],
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
        pass

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
            note_hints_sorted,
            original_model,
            nid,
            cur_note_hint[0],
            hint_field,
            cloze_field,
            additional_hint_field,
            replace
        )
        notes.append(note)

    logger.info("Confirm the hint generation and save notes ? (Y/n)")
    if input() == "Y":
        col.update_notes(notes)
        logger.success("New note hints saved in the collection!")

    col.close()


# for nid in notesID:
#     note = col.get_note(nid)
#     for i,part in enumerate(parts):
#         if part.find(content_to_hide)==0:
# #TODO: change, when german, rule could change...
# Check if no lines had the content to hide, is it really a synonym ? To notify user

#             if note_type_name=="Chinois":
#                 try:
#                     soup = BeautifulSoup(note["Pinyin.1"],"html.parser")
#                     plain_pinyin=soup.get_text(" ",strip=True)
#                     parts[i] = plain_pinyin[0]
#                 except IndexError:
#                     r = requests.get((f'https://helloacm.com/api/'
#                                   'pinyin/?cached&s={content_to_hide}')flak)
#                     parts[i]=r.json()["result"][0][0]

#             else:
#                 parts[i] = "?"
# #TODO: if option, get first letter of the content of field XXX. Else, just ?


if __name__ == "__main__":
    note_type_name = "Chinois"

    # query = ""  # '"Academy Award for Best Picture"'
    break_lines = False

    # TODO: Afterwards, for converted cloze to Basic, don't have to filter
    # by using the query, just the note type, AND the field where we have
    # the constant value (ex: Author) to generate the hints
    flds_in_hint = ["Simplified", "Meaning"]
    cloze_field = ""  # "Text"
    hint_field = "Synonyms"
    sorting_field = "Pinyin.1"
    sorting_key = None  # lambda row: row[1]

    separator = " | "  # should add spaces
    additional_hint_field = "Pinyin.1"  # "Movie winner"

    # Itère sur query : chiffre par chiffre. Si retrouve une carte, doit append le hint, pas remplacer
    i=0
    col = Collection(COL_PATH)
    while True:
        i+=1
        query = f'"Synonyms group:re:(^|, ){i}(,\W|$)"'
    
        try:
            notesID, original_model = find_notes_to_change(
                col, query, note_type_name, verbose=True, cloze_text_field=cloze_field
            )
        except ValueError:
            print(f"No more synonym groups. Last group ID is {i-1}")
            break

        # try:
        #     generate_hint(
        #         note_type_name,
        #         query,
        #         flds_in_hint,
        #         hint_field,
        #         additional_hint_field,
        #         sorting_key,
        #         sorting_field,
        #         separator=separator,
        #         break_lines=break_lines,
        #         cloze_field=cloze_field,
        #     )
        # except ValueError as e:
        #     print(query, e)
        #     continue
