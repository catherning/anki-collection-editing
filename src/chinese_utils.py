import pinyin_jyutping
from anki.collection import Collection
import yaml

from anki_utils import COL_PATH
from utils import find_notes_to_change

config = yaml.load(open("config.yaml"))
COL_PATH = config["collection_path"]

note_type_name = "Chinois"
field_to_fill="Pinyin.1"
source_field = "Simplified"
query=f"{field_to_fill}:"

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