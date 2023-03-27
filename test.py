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
new_note_type = models.new("Tour de France")

new_fields = ["Tour de France Winner","Year","Extra"]

for field in new_fields:
    fieldDict = models.new_field(field)
    models.add_field(new_note_type, fieldDict)
    
# Add template
template = models.new_template("Who is the winner")
models.add_template(new_note_type,template)

new_note_type["tmpls"][0]["qfmt"] = "{{Tour de France Winner}} is the winner of which year's Tour de France ?"
new_note_type["tmpls"][0]["afmt"] = "{{Year}}"


models.save(new_note_type)

# Change the note type
fmap = {"Text":"Tour de France Winner","Extra":"Extra"}

print(col.get_note(notesID[0]).mid==modelID)

models.change( models.get(modelID), notesID, new_note_type, fmap,cmap=None)

col.update_notes([col.get_note(noteID) for noteID in notesID])

print(col.get_note(notesID[0]).mid==modelID)

col.close()

print("ok")