from typing import Optional

import yaml
from anki.collection import Collection
from loguru import logger

from src.utils.field_utils import add_field
from src.utils.note_utils import find_notes, create_note_type, change_note_type, extract_info_from_cloze_deletion, get_col_path
from src.utils.constants import CLOZE_TYPE, FIELD_WITH_ORIGINAL_CLOZE

def cloze2Basic(
    COL_PATH: str,
    query: str,
    new_type_name: str,
    new_fields: Optional[list[tuple[str, str]]],
    original_type_name="Cloze",
    cloze_text_field="Text",
) -> None:
    """Main method to convert Anki notes from Cloze type to a Basic type

    Args:
        query (str): The query to search for the notes to convert.
            It follows the search convention from Anki.
            Ex, if you want to add regex search, use: 're:<pattern>'
        new_type_name (str): The name of the new Basic note type
        new_fields (Optional[list[tuple]]): A list of the new fields to be added
        to the new note type.
        It is in the form (<new_field>,<old_field>).
        Ex: ("Album","c1") or ("Album","Albums") to mean that the new field Album
        will extract the c1 cloze field or the old "Albums" field
        original_type_name (str, optional): The name of the previous note type.
        Could be new_type_name if you are resuming a conversion. Defaults to "Cloze".
        cloze_text_field (str, optional): The name of the field holding the cloze text
        when the original type is a Cloze. Defaults to "Text".
    """
    col = Collection(COL_PATH)

    notesID, original_model = find_notes(
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
            new_fields.append((FIELD_WITH_ORIGINAL_CLOZE, cloze_text_field))

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

    edited_notes = extract_info_from_cloze_deletion(
        col, notesID, new_note_type, new_fields, original_field_list, cloze_text_field
    )
    
    logger.info("Confirm the mappings and save notes ? (Y/n)")
    if input() == "Y":
        col.update_notes(edited_notes)
        logger.success("New notes created and saved in the collection!")
    else:
        logger.warning(
            "The note field extraction was not saved. But the notes were already"
            " converted."
        )
    col.close()



if __name__ == "__main__":
    COL_PATH = get_col_path("src/config.yaml")
    
    # TODO: when code is correct, use args instead (don't need to debug)
    new_type_name = "Best Pictures"
    original_type_name = "Cloze"  # "Cloze Music & Sport" # "Olympic winners bis"

    clozes = ["c1", "c2"]
    
    # TODO: make a method for that
    for original_type_name, extra_field in zip(
        ["Cloze",], # "Cloze Music & Sport"], 
        ["Extra",] # "Back Extra"]
    ):
        for movie_cloze in clozes:
            for year_cloze in clozes:
                    if (
                        movie_cloze == year_cloze
                    ):
                        continue

                    logger.info(f"{movie_cloze=} {year_cloze=}")
                    new_fields = [
                        ("Movie winner", movie_cloze),
                        ("Year", year_cloze),
                        ("Extra", extra_field),
                    ]
                    query = f'"Best Picture" re:{year_cloze}::\d{{4}}'
                      # re:c\d.*c\d.*c\d "re:\{\{c2::\d"' 
                    logger.info(f"Anki query: {query}")
                    cloze_text_field = "Text"  # FIELD_WITH_ORIGINAL_CLOZE

                    try:
                        cloze2Basic(
                            COL_PATH, 
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
