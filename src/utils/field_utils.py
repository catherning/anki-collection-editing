import re

from anki.collection import Collection
from anki.models import ModelsDictProxy, NotetypeDict
from anki.notes import Note
from bs4 import BeautifulSoup
from loguru import logger

from src.utils.constants import CLOZE_TYPE

def proceed():
    print("Proceed ? (Y/n)")
    a = input()
    if a == "y":
        logger.info("Please write 'Y' if you want to proceed.")
        a = input()
    if a != "Y":
        logger.info("Stopping prematurely at the user's request")
        exit()



# for a specific note, provide methods for a specific field. there can be different objects for different fields
class NoteFieldUtils:
    def __init__(self, col: Collection, note_type_name: str):
        self.col = col
        self.note_type_name = note_type_name
        self.note_type = col.models.by_name(self.new_type_name)

    def add_field(self, field: str) -> None:
        """
        Adds a new field to a note type.

        Parameters:
        field (str): The name of the new field.

        Returns:
        None
        """
        fieldDict = self.col.models.new_field(field)
        self.col.models.add_field(self.note_type, fieldDict)

    def get_field_index(self, field_name: str) -> int:
        return list(
            filter(lambda field: field["name"] == field_name, self.note_type["flds"])
        )[0]["ord"]

    def extract_cloze_deletion(self,field_to_extract_index, note, cloze_deletion) -> str:
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

def truncate_field(field: str, max_length: int = 30) -> str:
    return (
        f'{BeautifulSoup(field[:max_length], "html.parser").text}...'
        if len(BeautifulSoup(field, "html.parser").text) > max_length + 3
        else BeautifulSoup(field, "html.parser").text
    )


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

# ------------ Hint generation util methods ---------------

def get_cloze_data(flds_in_hint, cloze_field_index, separator, sorting_field, c_err, note):
    content = ""
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
    return content

def extract_text_from_field(note, field):
    soup = BeautifulSoup(note[field], "html.parser")
    for item in soup.select('span'):
        item.extract()
    return soup.get_text(" ")

def get_cleaned_field_data(separator, note, flds_in_hint):
    content = ""
    for field in flds_in_hint:
        text = extract_text_from_field(note, field)
        clean_text = truncate_field([t for t in text.splitlines() if t][0], 60)
        content += clean_text + separator
    return content


def breaklines_by_number(note_hints_sorted):
    note_hints_spaced = []
    previous_decimal = note_hints_sorted[0][2]
    for i, hint in enumerate(note_hints_sorted):
        if hint[2] != previous_decimal:
            note_hints_spaced.append("")
        note_hints_spaced.append(hint)
        previous_decimal = hint[2]
    note_hints_sorted = note_hints_spaced
    return note_hints_sorted