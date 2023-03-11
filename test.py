from anki_utils import COL_PATH

# from ankipandas import Collection, set_debug_log_level
# set_debug_log_level()

from anki.collection import Collection
from anki.models import ChangeNotetypeRequest

col = Collection(COL_PATH+"collectionUser1 - Copie.anki2")

print(col)


# Get the notes to edit
notesID = col.find_notes("year}} Tour de France")
notesID2 = col.find_notes("won the")
notesID3 = col.find_notes("note:Cloze")
notesID = list(set(notesID2).intersection(set(notesID)).intersection(set(notesID3)))

models = col.models

modelID = models.get_single_notetype_of_notes(notesID)
    
# Create new note type
newNote = models.new("Tour de France")

new_fields = ["Tour de France Winner","Year","Extra"]

for field in new_fields:
    fieldDict = models.new_field(field)
    models.add_field(newNote, fieldDict)
    
# Add template
template = models.new_template("Who is the winner")
models.add_template(newNote,template)

models.save(newNote)

# Change the note type
fmap = {"Text":"Winner","Extra":"Extra"}

# models.change( modelID, notesID, newNote, fmap,cmap=None)

change_nt_info = models.change_notetype_info(modelID, newNote.mid)

input = ChangeNotetypeRequest()
input.ParseFromString(change_nt_info)
input.note_ids.extend([...])

models.change_notetype_of_notes(input)