import re

from anki.collection import Collection
from anki.models import ModelsDictProxy, NotetypeDict
from anki.notes import Note
from bs4 import BeautifulSoup
from loguru import logger

from src.utils.utils import CLOZE_TYPE

def proceed():
    print("Proceed ? (Y/n)")
    a = input()
    if a == "y":
        logger.info("Please write 'Y' if you want to proceed.")
        a = input()
    if a != "Y":
        logger.info("Stopping prematurely at the user's request")
        exit()


def extract_text(node):
    """Recursively extract text from the BeautifulSoup node, handling blank lines."""
    lines = []
    for element in node.children:
        # If it's a string, strip extra whitespace
        if isinstance(element, str):
            text = element.strip()
            if text:
                lines.append(text)
        elif element.name == 'br':
            # Treat <br> as a blank line
            lines.append('\n')
        elif element.name == 'div':
            # If the div is empty or contains only &nbsp;, treat it as a blank line
            if element.get_text(strip=True) == '':
                lines.append('\n')
            else:
                # Recursively handle non-empty divs
                lines.extend(extract_text(element))
    return lines

# for a specific note, provide methods for a specific field. there can be different objects for different fields ?
# TODO: or one class for all fields ? as extention of note ?
class NoteFieldsUtils:
    def __init__(self, col: Collection, note_type_name: str,field_name: str):
        self.col = col
        self.note_type_name = note_type_name
        self.note_type = col.models.by_name(self.note_type_name)
        breakpoint()
        self.field_name = field_name # TODO: user really need to give it?

    def add_field(self) -> None:
        """
        Adds the new field to the note type.

        Returns:
        None
        """
        fieldDict = self.col.models.new_field(self.field_name)
        self.col.models.add_field(self.note_type, fieldDict)

    def get_field_index(self) -> int:
        return list(
            filter(lambda field: field["name"] == self.field_name, self.note_type["flds"])
        )[0]["ord"]

    def extract_cloze_deletion(self,field_to_extract_index, note, cloze_deletion) -> str:
        regex = r"\{\{%s::([^}:]*):?:?.*\}\}" % cloze_deletion
        # TODO: use field_name directly ?
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


    def extract_text_from_field(self,note):
        html_content = note[self.field_name].replace('\n', ' ')
        soup = BeautifulSoup(html_content, "html.parser")
        lines = extract_text(soup)
        return ' '.join(lines)

    def print_note_content(
        self, cloze_text_field: str, original_model: ModelsDictProxy, note_details: Note
    ):
        # TODO: check if given note is of correct type
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
        
    def get_cleaned_field_data(self, separator, note, flds_in_hint):
        # TODO: check if given note is of correct type
        content = ""
        for field in flds_in_hint:
            text = self.extract_text_from_field(note)
            clean_text = truncate_field([t for t in text.splitlines() if t][0], 60)
            content += clean_text + separator
        return content

    def get_cloze_data(self, flds_in_hint, cloze_field_index, separator, sorting_field, c_err, note):
        content = ""
        for cloze in flds_in_hint:
            try:
                content += (
                            self.extract_cloze_deletion(cloze_field_index, note, cloze)
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


def truncate_field(field: str, max_length: int = 30) -> str:
    return (
        f'{BeautifulSoup(field[:max_length], "html.parser").text}...'
        if len(BeautifulSoup(field, "html.parser").text) > max_length + 3
        else BeautifulSoup(field, "html.parser").text
    )


# ------------ Hint generation util methods ---------------



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