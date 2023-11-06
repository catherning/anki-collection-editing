import re

from anki.collection import Collection
from anki.models import ModelsDictProxy, NotetypeDict
from anki.notes import Note
from bs4 import BeautifulSoup
from loguru import logger

CLOZE_TYPE = 1


def proceed():
    print("Proceed ? (Y/n)")
    a = input()
    if a == "y":
        logger.info("Please write 'Y' if you want to proceed.")
        a = input()
    if a != "Y":
        logger.info("Stopping prematurely at the user's request")
        exit()


def find_notes_to_change(
    col: Collection,
    query: str = "",
    note_type_name: str = "Cloze",
    verbose: bool = True,
    cloze_text_field: str = "Text",
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

        proceed()
    return list(notesID), original_model


def truncate_field(field: str, max_length: int = 30) -> str:
    return (
        f'{BeautifulSoup(field[:max_length], "html.parser").text}...'
        if len(BeautifulSoup(field, "html.parser").text) > max_length + 3
        else BeautifulSoup(field, "html.parser").text
    )


def add_field(col: Collection, new_note_type: NotetypeDict, field: str) -> None:
    """
    Adds a new field to a note type.

    Parameters:
    col (object): The collection object.
    new_note_type (str): The name of the note type to which the field should be added.
    field (str): The name of the new field.

    Returns:
    None
    """
    fieldDict = col.models.new_field(field)
    col.models.add_field(new_note_type, fieldDict)


def get_field_index(note_type: NotetypeDict, field_name: str) -> int:
    return list(filter(lambda field: field["name"] == field_name, note_type["flds"]))[
        0
    ]["ord"]


def extract_cloze_deletion(field_to_extract_index, note, cloze_deletion) -> str:
    regex = r"\{\{%s::([^}:]*):?:?.*\}\}" % cloze_deletion
    # TODO: include case when there's several cloze for one card
    # (ex: several {{c1::...}}) => to put in different fields
    # https://regex101.com/r/usAlIw/1
    p = re.compile(regex)
    m = p.search(note.fields[field_to_extract_index])
    if m:
        return m.group(1)
    else:
        logger.error(f"Cloze text: '{note.fields[field_to_extract_index]}'")
        raise Exception(f"Regex {regex} incorrect.")


def print_note_content(
    cloze_text_field: str, original_model: ModelsDictProxy, note_details: Note
):
    if original_model["type"] == CLOZE_TYPE:
        # TODO: use note.load, note.values / keys/ items
        cloze_text_index = note_details._fmap[cloze_text_field][1]["ord"]
        return note_details.fields[cloze_text_index]
    else:
        return {
            field["name"]: truncate_field(note_details[field["name"]])
            for field in original_model["flds"]
            if note_details[field["name"]] != "" and field["name"] != cloze_text_field
        }
