from anki_utils import COL_PATH
from anki.collection import Collection



def find_notes_to_change(col,
                         query: str) -> list[int]:
    # Get the notes to edit
    query  = query + " note:Cloze"
    # for string in to_search:
    notesID = col.find_notes(query)
    # notesID = list( set(notesID_search).intersection(set(notesID)) )

    return list(notesID)


def create_note_type(models,
                     note_name:str,
                     new_fields:list[str]) -> dict:
    """_summary_

    Args:
        models (_type_): _description_
        note_name (str): _description_
        new_fields (list[str]): The first one is used in the question side of the created template. The second one for the back. Please go back to Anki GUI to edit the card template
    """
    # Create new note type
    new_note_type = models.new(note_name)

    for field in new_fields:
        fieldDict = models.new_field(field)
        models.add_field(new_note_type, fieldDict)
        
    # Add template
    template = models.new_template("Who is the winner")

    models.add_template(new_note_type,template)
    new_note_type["tmpls"][0]["qfmt"] = "{{%s}}" % (new_fields[0])
    new_note_type["tmpls"][0]["afmt"] = "{{%s}}" % (new_fields[1])

    models.save(new_note_type)
    
    return new_note_type
    

def change_note_type(col, 
                     old_note_type: dict,
                     new_note_type: dict,
                     notesID: list[int],
                     field_mapping_list: list[str] ):
    # Change the note type
    models = col.models
    
    if len(field_mapping_list)<2:
        raise ValueError("You must map at least two fields")
    
    fmap = {"Text": field_mapping_list[0],"Extra":field_mapping_list[1]}

    models.change( old_note_type, notesID, new_note_type, fmap,cmap=None)
    col.update_notes([col.get_note(noteID) for noteID in notesID])

    col.close()
    

def cloze2Basic(new_type_name, 
                new_fields,
                query):
    col = Collection(COL_PATH+"collectionUser1 - Copie.anki2")

    notesID = find_notes_to_change(col,query)

    models = col.models
    modelID = models.get_single_notetype_of_notes(notesID)

    new_note_type = create_note_type(models, new_type_name, new_fields)

    new_fields_mapping = [new_fields[0],new_fields[2]]
    change_note_type(col,models.get(modelID), new_note_type, notesID, new_fields_mapping)


new_type_name = "Olympic winners"
new_fields = ["Winner","Year","Extra"]
query = '"Olympics" "won"'

cloze2Basic(new_type_name, new_fields, query)

# TODO: get the new info using regex