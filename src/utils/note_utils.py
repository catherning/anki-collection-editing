import re
from typing import Optional
import yaml

from anki.collection import Collection
from anki.errors import InvalidInput
from anki.models import NotetypeDict
from loguru import logger

from src.utils.field_utils import (NoteFieldsUtils, proceed, truncate_field)
from src.utils.constants import FIELD_WITH_ORIGINAL_CLOZE, CLOZE_TYPE

class NoteConverter:
    def __init__(self, 
                 config_path: str,
                 new_note_name: str,
                 new_fields: Optional[list[tuple[str, str]]] = None,
                 original_type_name: Optional[str] = "Cloze",
                 cloze_text_field: Optional[str] = "Text",

                 ):
        self.config_path = config_path
        self.COL_PATH = get_col_path(self.config_path)
        self.col = Collection(self.COL_PATH)
        self.original_type_name = original_type_name
        self.new_type_name = new_note_name
        self.new_fields = new_fields
        if self.new_fields is None:
            self.interactive_field_mapping()
        self.original_field_list = []
        self.cloze_text_field = cloze_text_field
        self.note_field_utils = NoteFieldsUtils(new_note_name,new_fields+[cloze_text_field])
        
    def interactive_field_mapping(self):
        """Interactive method to map the fields of the new note type from the cloze fields
        of the original note type
        """
        
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
            
        self.new_fields = new_fields
        
    def run_cloze2Basic(
        self,
        query: str,
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
        col = self.col
        notesID, original_model = find_notes(
            col,
            query=query,
            note_type_name=self.original_type_name,
            cloze_text_field=self.cloze_text_field,
        )
        # TODO: save original model & new created model
        self.original_field_list = [fld["name"] for fld in original_model["flds"]]


        # If model is of type Cloze, we do the conversion,
        # otherwise we just do the regex extraction
        if original_model["type"] == CLOZE_TYPE:
            # If the user doesn't map the Text field to a target field, we do it
            if not [el for el in self.new_fields if self.cloze_text_field in el[1]]:
                self.new_fields.append((FIELD_WITH_ORIGINAL_CLOZE,self. cloze_text_field))

            # Resume a conversion if the new type was already created before
            # TODO: make it the user action to create the new type ?
            new_note_type = col.models.by_name(self.new_type_name)
            if new_note_type is None:
                new_note_type = self.create_note_type(
                )

            missing_fields = set(field[0] for field in self.new_fields) - set(
                field["name"] for field in new_note_type["flds"]
            )
            for field in missing_fields:
                logger.warning(
                    f"Creation of the field '{field}' which is not present in new note type"
                )
                self.note_field_utils[field].add_field()
            col.models.save(new_note_type)

            self.change_note_type(original_model, new_note_type, notesID)
        else:
            new_note_type = original_model

        edited_notes = self.copy_from_cloze2save_field(
            notesID, new_note_type
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

    def create_note_type(
        self,
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
        models = self.col.models
        new_note_type = models.new(self.note_name)

        for i, field_info in enumerate(self.new_fields):
            self.note_field_utils[field_info[0]].add_field()

            if field_info[1] not in self.original_field_list:
                # Add template
                template = models.new_template(f"Answer: {field_info[0]}")

                models.add_template(new_note_type, template)

                new_note_type["tmpls"][i]["qfmt"] = "{{%s}}" % (
                    self.new_fields[(i + 1) % len(self.new_fields)][0]
                )
                new_note_type["tmpls"][i]["afmt"] = "{{%s}}" % (field_info[0])

        models.save(new_note_type)

        return new_note_type


    def change_note_type(
        self,
        old_note_type: dict,
        new_note_type: dict,
        notesID: list[int],
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

        if len(self.new_fields) < 2:
            raise ValueError("You must map at least two fields")

        fmap = dict()
        original_fields = old_note_type["flds"]

        for target_field_info in self.new_fields:
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
        self.col.models.change(old_note_type, notesID, new_note_type, fmap, cmap=None)
        # TODO: Is it possible not to do this?
        logger.warning(
            "The notes were converted even if the extraction is not validated. "
            "If you don't confirm and save the notes, you can resume the conversion "
            "but you must change the origin note type to the name of the new note type"
        )


    def copy_from_cloze2save_field(
        self,
        notesID: list[int],
        new_note_type: NotetypeDict,
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
        
        if FIELD_WITH_ORIGINAL_CLOZE == self.new_fields[-1][0]:
            field_to_extract_index = -1
        else:
            field_to_extract_index = self.note_field_utils[self.cloze_text_field].get_field_index()

        notes = []
        for noteID in notesID:
            note = self.col.get_note(noteID)
            for i, (target_field, field_origin) in enumerate(
            ):  # Could use last value to see if it's a regex / cloze extraction
                if field_origin not in self.original_field_list:
                    try:
                        note.fields[i] = self.note_field_utils[self.cloze_text_field].extract_cloze_deletion(
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


def find_notes(
    col: Collection,
    query: str = "",
    note_type_name: str = "Cloze",
    verbose: bool = True,
    cloze_text_field: str = "Text",
    override_confirmation: bool = False,
) -> tuple[list[int], NotetypeDict | None]:
    """Retrieves the notes according to a query.

    Args:
        col (Collection): The full Anki collection with all models and notes
        query (str): Query to use to find the notes
        note_type_name (str, optional): Name of the note type. Defaults to "Cloze".
        verbose: To show more information on the notes found. Defaults to True
        cloze_text_field: Field name containing the cloze note. Defaults to "Text"

    Raises:
        ValueError: If no note was found (because the query or note type name
        is wrong)

    Returns:
        list[int]: The list of the IDs of the notes
        NotetypeDict: The common type of the notes
    """

    # Get the notes to edit
    new_query = query + f' note:"{note_type_name}"'
    notefields = NoteFieldsUtils(col, note_type_name, [cloze_text_field])
    try:
        notesID = col.find_notes(new_query)
    except InvalidInput as e:
        col.reopen()
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
                    notefields.print_note_content(cloze_text_field, original_model, note_details)
                )

        if not override_confirmation:
            proceed()
    return list(notesID), original_model

def get_yaml_value(config_path,key):
    with open(config_path, 'rb') as file:
        config = yaml.safe_load(file)
    return config[key]

def get_col_path(config_path):
    COL_PATH = get_yaml_value(config_path, "collection_path")

    if COL_PATH[-6:] != ".anki2":
        COL_PATH += "collection.anki2"
    return COL_PATH