import re
from typing import Optional

from anki.collection import Collection
from anki.models import NotetypeDict
from anki_utils import COL_PATH
from loguru import logger
from utils import add_field
from utils import CLOZE_TYPE
from utils import extract_cloze_field
from utils import get_field_index
from utils import print_note_content
from utils import proceed
from utils import truncate_field

if COL_PATH[-6:] != ".anki2":
    COL_PATH += "collection.anki2"


def find_notes_to_change(
    col: Collection,
    query: str = "",
    note_type_name: str = "Cloze",
    verbose=True,
    cloze_text_field="Text",
) -> tuple[list[int], NotetypeDict]:
    """Retrieves the notes to change according to a query.

        Args:
            col (Collection): The full Anki collection with all models and notes
            query (str): Query to use to find the notes to change
            note_type_name (str, optional): Name of the note type. Defaults to "Cloze".
            verbose: To show more information on the notes found. Defaults to True
            cloze_text_field: Field name containing the cloze note. Defaults to "Text"
    0
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
                        "The fields of the note of Basic type are not emtpy"
                        "and might be replaced"
                    )
                logger.info(
                    print_note_content(cloze_text_field, original_model, note_details)
                )

        proceed()
    return list(notesID), original_model


def create_note_type(
    col: Collection,
    note_name: str,
    new_fields: list[tuple],
    original_field_list: list[str],
) -> NotetypeDict:
    """Creates the new note type and the card templates.

    Args:
        col (Collection): The full Anki collection with all models and notes
        note_name (str): The name of the new note
        new_fields (list[tuple]): The list of new field names and how to fill it
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
    new_fields: list[tuple],
):
    """
    Convert the note type of Anki flashcards.

    Parameters:
    col (Collection): The Anki collection object.
    old_note_type (dict): A dictionary representing the old note type.
    new_note_type (dict): A dictionary representing the new note type.
    notesID (list[int]): A list of the IDs of the notes to be changed.
    new_fields (list[tuple]): A list of the new fields to be added to the new note type.
    It is in the form (<new_field>,<old_field>). Ex: ("Album","c1") or ("Album","Albums")

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


def extract_info_from_cloze(
    col,
    notesID,
    new_note_type,
    new_fields,
    original_field_list,
    cloze_text_field="Text",
):
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
                    note.fields[i] = extract_cloze_field(
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


def cloze2Basic(
    query: str,
    new_type_name: str,
    new_fields: Optional[list[tuple]],
    original_type_name="Cloze",
    cloze_text_field="Text",
):
    col = Collection(COL_PATH)

    notesID, original_model = find_notes_to_change(
        col,
        query=query,
        note_type_name=original_type_name,
        cloze_text_field=cloze_text_field,
    )

    original_field_list = [fld["name"] for fld in original_model["flds"]]

    if new_fields is None:
        logger.info(
            "No fields given for the new note type. Please write the name "
            "of the new fields and from which cloze they are extracted"
        )
        new_fields = []
        field = ""
        while field != "stop":
            logger.info(
                "Please write the field information as follow: '[Name of field],[c1]'"
            )
            field = input()
            field_info = [el.strip() for el in field.split(",")]
            if field == "stop" or len(field_info) != 2:
                break
            new_fields.append(tuple(field_info))
            logger.info(f"New field information {field_info} added")

    # If model is of type Cloze, we do the conversion,
    # otherwise we just do the regex extraction
    if original_model["type"] == CLOZE_TYPE:
        # If the user doesn't map the Text field to a target field, we do it
        if not [el for el in new_fields if cloze_text_field in el[1]]:
            new_fields.append(("Original cloze text", cloze_text_field))

        # Resume a conversion if the new type was already created before
        new_note_type = col.models.by_name(new_type_name)
        if new_note_type is None:
            new_note_type = create_note_type(
                col, new_type_name, new_fields, original_field_list
            )

        missing_fields = set(field[0] for field in new_fields) - set(
            field["name"] for field in new_note_type["flds"]
        )
        for field in missing_fields:
            logger.warning(
                f"Creation of the field '{field}' which is not present in new note type"
            )
            add_field(col, new_note_type, field)
        col.models.save(new_note_type)

        change_note_type(col, original_model, new_note_type, notesID, new_fields)
    else:
        new_note_type = original_model

    extract_info_from_cloze(
        col, notesID, new_note_type, new_fields, original_field_list, cloze_text_field
    )


if __name__ == "__main__":
    # TODO: when code is correct, use args instead (don't need to debug)
    new_type_name = "Music"
    original_type_name = "Cloze"  # "Cloze Music & Sport" # "Olympic winners bis"

    clozes = ["c1", "c2", "c3"]
    for original_type_name, extra_field in zip(
        ["Cloze", "Cloze Music & Sport"], ["Extra", "Back Extra"]
    ):
        for album_cloze in clozes:
            for year_cloze in clozes:
                for group_cloze in clozes:
                    if (
                        album_cloze == year_cloze
                        or album_cloze == group_cloze
                        or year_cloze == group_cloze
                    ):
                        continue

                    print(f"{album_cloze=} {year_cloze=} {group_cloze=}")
                    new_fields = [
                        ("Album", album_cloze),
                        ("Year", year_cloze),
                        ("Group", group_cloze),
                        ("Extra", extra_field),
                    ]
                    query = (
                        "album re:"
                        + album_cloze
                        + r".*c\d.*c\d re:\{\{"
                        + year_cloze
                        + r"::\d{4}"
                    )  # re:c\d.*c\d.*c\d "re:\{\{c2::\d"' #
                    cloze_text_field = "Text"  # "Original cloze text"

                    try:
                        cloze2Basic(
                            query=query,
                            new_type_name=new_type_name,
                            new_fields=new_fields,
                            original_type_name=original_type_name,
                            cloze_text_field=cloze_text_field,
                        )
                    except ValueError:
                        continue

# FIXME: needs to have the latest (?) version of Anki GUI.
# Or min the same version as the Anki module used here
# => Either try with older version of Anki library,
# or issues is fixed when having the script as an addon ?
