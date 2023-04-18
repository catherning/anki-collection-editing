from anki_utils import COL_PATH
from anki.collection import Collection

import re
from loguru import logger

def find_notes_to_change(col,
                         query: str,
                         cloze_type_name: str = "Cloze") -> list[int]:
    # Get the notes to edit
    query  = query + f' note:"{cloze_type_name}"'
    notesID = col.find_notes(query)

    if len(notesID)==0:
        raise ValueError("No notes found. Please review your query and cloze note type")
    else:
        logger.info(f"Number of notes found: {len(notesID)}")
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
    
    # fmap = {"Text": field_mapping_list[1],"Extra":field_mapping_list[0]}
    fmap = {0:0,1:1}
    
    models.change(old_note_type, notesID, new_note_type, fmap, cmap=None)
    
    
# TODO: get the new info using regex
def extract_info_from_cloze(col,
                            notesID,
                            regex):
    # TODO: test the cloze on the field before change the note type ?
    p = re.compile("\{\{c\d::the (\d{4}).*\}\}")
    field = "Winner"
    for noteID in notesID:
        note = col.get_note(noteID)
        m = p.search(note.fields[0])
        if m:
            note.fields[1] =  m.group(1)
        else:
            raise Exception(f"Regex incorrect. Information to put in {field=} not found") 
        
    # selection["nfld_Winner"] = selection["nfld_Winner"].str.extract(r'{{c\d::(\D+)::who\?}}')

    
    

def cloze2Basic(new_type_name, 
                new_fields,
                query,
                cloze_type_name = "Cloze"):
    col = Collection(COL_PATH+"collection.anki2")

    notesID = find_notes_to_change(col,query, cloze_type_name)

    models = col.models
    modelID = models.get_single_notetype_of_notes(notesID)

    new_note_type = create_note_type(models, new_type_name, new_fields)

    new_fields_mapping = [new_fields[0],new_fields[2]]
    change_note_type(col,models.get(modelID), new_note_type, notesID, new_fields_mapping)
    
    extract_info_from_cloze(col,notesID,None)
    
    # notesID =  col.find_notes('note:"Olympic winners"')


    
    col.update_notes([col.get_note(noteID) for noteID in notesID])

    col.close()


new_type_name = "Olympic winners"
new_fields = ["Winner","Year","Extra"] # TODO: if there's a field Extra, put the cloze info there ?
query = '"Olympics" "won"'

# Get possibility to start from middle, having already changed cloze type, but not yet the regex part ?
cloze2Basic(new_type_name, new_fields, query,"Cloze Music & Sport")



# FIXME: needs to have the latest (?) version of Anki GUI. Or min the same version as the Anki module used here => Either try with older version of Anki library, or issues is fixed when having the script as an addon ?