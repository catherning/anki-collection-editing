from anki_utils import COL_PATH
from anki.collection import Collection

import re
from loguru import logger

def find_notes_to_change(col,
                         query: str,
                         cloze_type_name: str = "Cloze") -> list[int]:
    # Get the notes to edit
    new_query  = query + f' note:"{cloze_type_name}"'
    notesID = col.find_notes(new_query)

    if len(notesID)==0:
        raise ValueError("No notes found. Please review your query and cloze note type")
    else:
        logger.info(f"Number of notes found: {len(notesID)}")
        print("Proceed ? (y/n)")
        # if input()!="y":
        #     exit() 
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

    for field_info in new_fields:
        fieldDict = models.new_field(field_info[0])
        models.add_field(new_note_type, fieldDict)
        
    # Add template
    template = models.new_template("Who is the winner")

    models.add_template(new_note_type,template)

    # TODO: make it customizable ?
    new_note_type["tmpls"][0]["qfmt"] = "{{%s}}" % (new_fields[0][0])
    new_note_type["tmpls"][0]["afmt"] = "{{%s}}" % (new_fields[1][0])

    models.save(new_note_type)
    
    return new_note_type
    

def change_note_type(col, 
                     old_note_type: dict,
                     new_note_type: dict,
                     notesID: list[int],
                     field_mapping_list: list[str] ):
    # Change the note type

    if len(field_mapping_list)<2:
        raise ValueError("You must map at least two fields")
    
    fmap = dict()
    # fmap = {"Text": field_mapping_list[1],"Extra":field_mapping_list[0]}
    cloze_fields = old_note_type["flds"]
    for i, field_info in enumerate(field_mapping_list):
        # if len(field_info)==2:
        try:
            # Map the ordinal position of the original field to the ordinal position (f_info["ord"]) of the target field (i)
            fmap[[f_info["ord"] for f_info in cloze_fields if field_info[1] == f_info["name"]][0]] = i
        except IndexError:
            logger.info(f"Target field {field_info[0]} will be mapped from nothing for the note type conversion step. (Original field / regex: {field_info[1]})")
    
    col.models.change(old_note_type, notesID, new_note_type, fmap, cmap=None)
    

def extract_info_from_cloze(col,
                            notesID,
                            new_fields):
    # TODO: test the cloze on the field before change the note type ?
    """_summary_

    Args:
        col (_type_): _description_
        notesID (_type_): _description_
        regex (_type_): _description_
        Carefull not to replace the last 
        
    Raises:
        Exception: _description_
    """
    # TODO: compare efficiency if exchange loops.
    if "Original cloze text"==new_fields[-1][0]:
        field_to_extract = -1
    else:
        text_field = [(f_info,i) for i,f_info in enumerate(new_fields) if f_info[2]=="Text"][0]
        logger.warning(f"The field {text_field[0][0]} that was mapped from the cloze text field will be replaced with the matched pattern {text_field[0][1]} in the given regex")
        field_to_extract = text_field[1]
        
    for noteID in notesID:
        note = col.get_note(noteID)
        for i,(target_field,regex,_) in enumerate(new_fields):
            p = re.compile(regex)
            m = p.search(note.fields[field_to_extract])
            if m:
                note.fields[i] =  m.group(1)
                
            else:
                raise Exception(f"Regex incorrect. Information to put in {target_field=} not found") 
        col.update_note(note)
            
    # selection["nfld_Winner"] = selection["nfld_Winner"].str.extract(r'{{c\d::(\D+)::who\?}}')

    
    

def cloze2Basic(query: str,
                new_type_name: str = None, 
                new_fields: list[any] = None,
                original_type_name = "Cloze",
                ):
    col = Collection(COL_PATH+"collection.anki2")

    notesID = find_notes_to_change(col,query, original_type_name)

    models = col.models
    modelID = models.get_single_notetype_of_notes(notesID)

    if "Cloze" in original_type_name : # or check if models.get(model id) == type of cloze ?
        new_fields.append(("Original cloze text","Text"))
        # TODO: check that there's only once "Text" or other field name in last place of set.
        # Or if there's already one with field "text", then do not append "Origianal cloze text" to new_field.
        # Or allow it and copy to all target fields.
        new_note_type = create_note_type(models, new_type_name, new_fields)

        # new_fields_mapping = [field_info for field_info in new_fields if len(field_info)==3] 
        # useless ? or necessary check ? but then following line is wrong ?
        # fmap[[f_info["ord"] for f_info in cloze_fields if field_info[2] == f_info["name"]][0]] = i
        
        change_note_type(col,models.get(modelID), new_note_type, notesID, new_fields)
    
    extract_info_from_cloze(col,notesID,new_fields)
    
    
    col.update_notes([col.get_note(noteID) for noteID in notesID])

    col.close()


new_type_name = "Olympic winners"
original_type_name = "Cloze Music & Sport"
# (new_field_name, regex to fill it with data, the original field for mapping transferring (can't copy original field to several target fields. Make it possible ?))
new_fields = [("Winner" , "\{\{c\d::(\D+)::who\?\}\}"),
              ("Year"   , "\{\{c\d::the (\d{4}).*\}\}"),
              ("Extra"  , "Back Extra")] 

# TODO: if there's a field Extra, put the cloze info there ?

query = '"Olympics" "won"'

# Get possibility to start from middle, having already changed cloze type, but not yet the regex part ?
cloze2Basic(query, new_type_name, new_fields,original_type_name)



# FIXME: needs to have the latest (?) version of Anki GUI. Or min the same version as the Anki module used here => Either try with older version of Anki library, or issues is fixed when having the script as an addon ?