import re
from typing import Optional

from anki.collection import Collection
from anki.models import NotetypeDict
from loguru import logger

from utils import (CLOZE_TYPE, add_field, extract_cloze_deletion,
                   find_notes_to_change, get_field_index, proceed,
                   truncate_field)


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

    if "Original cloze text" == new_fields[-1][0]:
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

    logger.info("Confirm the mappings and save notes ? (Y/n)")
    if input() == "Y":
        col.update_notes(notes)
        logger.success("New notes created and saved in the collection!")
    else:
        logger.warning(
            "The note field extraction was not saved. But the notes were already"
            " converted."
        )
    col.close()
