import pinyin_jyutping
import yaml
from anki.collection import Collection
from anki_utils import COL_PATH

from utils.note_utils import find_notes_to_change, get_col_path

COL_PATH = get_col_path("src/config.yaml")

## Get pinyin of characters to fill into a note field
def fill_pinyin(COL_PATH, note_type_name, field_to_fill, source_field, query):
    col = Collection(COL_PATH)
    notesID, original_model = find_notes_to_change(
    col, query, note_type_name, verbose=True, cloze_text_field=source_field
)
    p = pinyin_jyutping.PinyinJyutping()
    notes = []
    for nid in notesID:
        note = col.get_note(nid)
        note[field_to_fill] = p.pinyin(note[source_field])
    
        notes.append(note)

    if input("Confirm save ?") == "Y":
        col.update_notes(notes)

    col.close()

if __name__ == "__main__":
    note_type_name = "Chinois"
    field_to_fill="Pinyin.1"
    source_field = "Simplified"
    query=f"{field_to_fill}:"
    fill_pinyin(COL_PATH, note_type_name, field_to_fill, source_field, query)