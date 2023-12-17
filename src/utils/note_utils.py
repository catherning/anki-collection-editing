import re
from typing import Optional
import yaml

from anki.collection import Collection
from anki.models import NotetypeDict
from loguru import logger

from utils.field_utils import (add_field, extract_cloze_deletion,
                   get_field_index, proceed,
                   truncate_field, print_note_content)
from utils.constants import FIELD_WITH_ORIGINAL_CLOZE, CLOZE_TYPE


def get_col_path(config_path):
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    COL_PATH = config["collection_path"]

    if COL_PATH[-6:] != ".anki2":
        COL_PATH += "collection.anki2"
    return COL_PATH

def create_note_type(
    col: Collection,
    note_name: str,
    new_fields: list[tuple[str, str]],
    original_field_list: list[str],
) -> NotetypeDict:
    """Creates the new note type and the card templates.

    Args:
        col (Collection): The full Anki collection with all models and notes
        note_name (str): The name of the new note
        new_fields (list[tuple[str,str]]): The list of new field names and how to fill it
        original_field_list (list[str]): The list of

    Returns:
        NotetypeDict: The new note type dictionary
    """
    # Create new note type
    models = col.models
    new_note_type = models.new(note_name)

    for i, field_info in enumerate(new_fields):
        add_field(col, new_note_type, field_info[0])

        if field_info[1] not in original_field_list:
            # Add template
            template = models.new_template(f"Answer: {field_info[0]}")

            models.add_template(new_note_type, template)

            new_note_type["tmpls"][i]["qfmt"] = "{{%s}}" % (
                new_fields[(i + 1) % len(new_fields)][0]
            )
            new_note_type["tmpls"][i]["afmt"] = "{{%s}}" % (field_info[0])

    models.save(new_note_type)

    return new_note_type


def change_note_type(
    col: Collection,
    old_note_type: dict,
    new_note_type: dict,
    notesID: list[int],
    new_fields: list[tuple[str, str]],
) -> None:
    """
    Convert the note type of Anki flashcards.

    Args:
        col (Collection): The Anki collection object.
        old_note_type (dict): A dictionary representing the old note type.
        new_note_type (dict): A dictionary representing the new note type.
        notesID (list[int]): A list of the IDs of the notes to be changed.
        new_fields (list[tuple[str,str]]): The new fields to be added to
        the new note type. It is in the form (<new_field>,<old_field>).
        Ex: ("Album","c1") or ("Album","Albums")

    Raises:
    ValueError: If the number of new fields is less than 2.

    Returns:
        None
    """

    if len(new_fields) < 2:
        raise ValueError("You must map at least two fields")

    fmap = dict()
    original_fields = old_note_type["flds"]

    for target_field_info in new_fields:
        try:
            # Map the ordinal position of the original field to the ordinal position
            # (f_info["ord"]) of the target field
            target_ord = next(
                filter(
                    lambda field: target_field_info[0] == field["name"],
                    new_note_type["flds"],
                )
            )["ord"]
            original_ord = [
                original_field_info["ord"]
                for original_field_info in original_fields
                if target_field_info[1] == original_field_info["name"]
            ][0]
            fmap[original_ord] = target_ord
            logger.info(
                f"Target field {target_field_info[0]} will be "
                f"mapped from the field '{target_field_info[1]}'"
            )
        except IndexError:  # When taking the index 0 of empty list
            if re.compile(r"c\d").search(target_field_info[1]):
                logger.info(
                    f"Target field {target_field_info[0]} will extract the "
                    f"{target_field_info[1]} cloze field"
                )
            else:
                logger.error(
                    f"Field not found. Wrong field name: '{target_field_info[1]}'. "
                    "Please restart the script with the correct field name or proceed. "
                    "The field will be empty"
                )
                logger.info(
                    "For your information, the fields of the original note are: "
                    + str([f_info["name"] for f_info in original_fields])
                )
        except StopIteration:
            # Should not happen as we create the missing fields before
            logger.error(
                f"Field {target_field_info[0]} is not present in new note type. "
                "It will be created"
            )

    proceed()
    col.models.change(old_note_type, notesID, new_note_type, fmap, cmap=None)
    logger.warning(
        "The notes were converted even if the extraction is not validated. "
        "If you don't confirm and save the notes, you can resume the conversion "
        "but you must change the origin note type to the name of the new note type"
    )


def extract_info_from_cloze_deletion(
    col: Collection,
    notesID: list[int],
    new_note_type: NotetypeDict,
    new_fields: list[tuple[str, str]],
    original_field_list: list[str],
    cloze_text_field: str = "Text",
):
    """Copy the information from the cloze deletion to a new field.

    Args:
        col (Collection): The Anki Collection
        notesID (list[int]): The IDs of the notes to edit
        new_note_type (NotetypeDict): The new type of all the notes to edit
        new_fields (list[tuple[str,str]]): The mapping of the new fields from
        the cloze deletions/fields
        original_field_list (list[str]): The fields of the previous note type
        cloze_text_field (str, optional): The name of the field with cloze text.
        Defaults to "Text".
    """
    
    if FIELD_WITH_ORIGINAL_CLOZE == new_fields[-1][0]:
        field_to_extract_index = -1
    else:
        field_to_extract_index = get_field_index(new_note_type, cloze_text_field)

    notes = []
    for noteID in notesID:
        note = col.get_note(noteID)
        for i, (target_field, field_origin) in enumerate(
            new_fields
        ):  # Could use last value to see if it's a regex / cloze extraction
            if field_origin not in original_field_list:
                try:
                    note.fields[i] = extract_cloze_deletion(
                        field_to_extract_index, note, field_origin
                    )
                except Exception:
                    logger.info(
                        f"Information to put in {target_field=} not found. "
                        "Maybe the original field name was wrong?"
                    )

        logger.info(
            f"Final fields of the note: {[truncate_field(fld) for fld in note.fields]}"
        )
        notes.append(note)
        
    return notes


def find_notes_to_change(
    col: Collection,
    query: str = "",
    note_type_name: str = "Cloze",
    verbose: bool = True,
    cloze_text_field: str = "Text",
    override_confirmation: bool = False,
) -> tuple[list[int], NotetypeDict | None]:
    """Retrieves the notes to change according to a query.

    Args:
        col (Collection): The full Anki collection with all models and notes
        query (str): Query to use to find the notes to change
        note_type_name (str, optional): Name of the note type. Defaults to "Cloze".
        verbose: To show more information on the notes found. Defaults to True
        cloze_text_field: Field name containing the cloze note. Defaults to "Text"

    Raises:
        ValueError: If no note was found (because the query or note type name
        is wrong)

    Returns:
        list[int]: The list of the IDs of the notes to convert
    """

    # Get the notes to edit
    new_query = query + f' note:"{note_type_name}"'
    notesID = col.find_notes(new_query)

    if len(notesID) == 0:
        raise ValueError("No notes found. Please review your query and cloze note type")
    else:
        logger.info(f"Number of notes found: {len(notesID)}")
        original_modelID = col.models.get_single_notetype_of_notes(notesID)
        original_model = col.models.get(original_modelID)
        for note in notesID:
            note_details = col.get_note(note)

            if verbose:
                if original_model["type"] != CLOZE_TYPE:
                    logger.warning(
                        "The fields of the note of Basic type are not empty "
                        "and might be replaced"
                    )
                # TODO: find cloze_text_field by getting the field with c1 ?
                logger.info(
                    print_note_content(cloze_text_field, original_model, note_details)
                )

        if not override_confirmation:
            proceed()
    return list(notesID), original_model

