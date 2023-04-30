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
        for note in notesID:
            logger.info(col.get_note(note).fields[0])
        print("Proceed ? (y/n)")
        # if input()!="y":
        #     exit() 
    return list(notesID)


def create_note_type(models,
                     note_name:str,
                     new_fields:list[str],
                     original_field_list) -> dict:
    """_summary_

    Args:
        models (_type_): _description_
        note_name (str): _description_
        new_fields (list[str]): The first one is used in the question side of the created template. The second one for the back. Please go back to Anki GUI to edit the card template
    """
    # Create new note type
    new_note_type = models.new(note_name)

    for i,field_info in enumerate(new_fields):
        fieldDict = models.new_field(field_info[0])
        models.add_field(new_note_type, fieldDict)
        
        if field_info[1] in original_field_list:
            # Add template
            template = models.new_template(f"Answer: {field_info[0]}")

            models.add_template(new_note_type,template)

            new_note_type["tmpls"][i]["qfmt"] = "{{%s}}" % (new_fields[(i+1)%len(new_fields)][0])
            new_note_type["tmpls"][i]["afmt"] = "{{%s}}" % (new_fields[i][0])

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
    cloze_fields = old_note_type["flds"]

    
    for i, field_info in enumerate(field_mapping_list):
        try:
            # Map the ordinal position of the original field to the ordinal position (f_info["ord"]) of the target field (i)
            fmap[[f_info["ord"] for f_info in cloze_fields if field_info[1] == f_info["name"]][0]] = i
            logger.info(f"Target field {field_info[0]} will be mapped from the field '{field_info[1]}'")
        except IndexError:
            logger.info(f"Target field {field_info[0]} will be mapped from nothing for the note type conversion step. (Original field / regex: '{field_info[1]}')")
    
    # TODO: transpose cards info onto the new cards
    cards = col.get_note(notesID[3]).cards()
    
    col.models.change(old_note_type, notesID, new_note_type, fmap, cmap=None)
    

def extract_info_from_cloze(col,
                            notesID,
                            new_fields,
                            original_field_list):

    if "Original cloze text"==new_fields[-1][0]:
        field_to_extract = -1
    else:
        text_field = [(f_info,i) for i,f_info in enumerate(new_fields) if f_info[2]=="Text"][0]
        # logger.warning(f"The field {text_field[0][0]} that was mapped from the cloze text field might be replaced with the matched pattern {text_field[0][1]} in the given regex")
        field_to_extract = text_field[1]
    
    
            
    for noteID in notesID:
        note = col.get_note(noteID)
        for i,(target_field,regex) in enumerate(new_fields): # Could use last value to see if it's a regex / cloze extraction
            if regex in original_field_list:
                # the content was already copied with fmap during the note conversion
                continue
            else:
                regex = "\{\{c"+str(i+1)+"::([^}:]*):?:?.*\}\}$"
                # https://regex101.com/r/usAlIw/1
                p = re.compile(regex)
                m = p.search(note.fields[field_to_extract])
                if m:
                    note.fields[i] =  m.group(1)
                else:
                    logger.error(f"Cloze text: '{note.fields[field_to_extract]}'")
                    raise Exception(f"Regex {regex} incorrect. Information to put in {target_field=} not found.")
                    # TODO: give the list of the notes with incorrect transformation and continue the process

        logger.info(f"Final fields of the note: {note.fields}")
        col.update_note(note)
            

def cloze2Basic(query: str,
                new_type_name: str = None, 
                new_fields: list[any] = None,
                original_type_name = "Cloze",
                ):
    col = Collection(COL_PATH+"collection.anki2")

    notesID = find_notes_to_change(col,query, original_type_name)

    models = col.models
    original_modelID = models.get_single_notetype_of_notes(notesID)
    original_model = models.get(original_modelID)
    original_field_list = [fld["name"] for fld in original_model["flds"]]

    # If model is of type Cloze, we do the conversion, otherwise we just do the regex extraction
    if original_model["type"]==1 : 
        
        # If the user doesn't map the Text field to a target field, we do it
        # TODO: allow for another name than Text where there is the cloze ?
        if not [el for el in new_fields if "Text" in el[1]]:
            new_fields.append(("Original cloze text","Text"))
            # Or copy "Text" to all target fields ?
        
        # Resume a conversion if the new type was already created before
        new_note_type = models.by_name(new_type_name) 
        if new_note_type is None:
            new_note_type = create_note_type(models, new_type_name, new_fields,original_field_list)
        
        change_note_type(col,original_model, new_note_type, notesID, new_fields)
    
    extract_info_from_cloze(col,notesID,new_fields,original_field_list)

    col.close()


new_type_name = "Olympic winners 2"
original_type_name = "Cloze" #Music & Sport"
# (new_field_name, regex to fill it with data OR the original field for mapping transferring (can't copy original field to several target fields. Make it possible ?))
new_fields = [("Winner" , "\{\{c\d::(\D+)::who\?\}\}"), # By default : regex to capture what's inside a cloze
              ("Year"   , "\{\{c\d::(\d{4}).*\}\}"),
              ("Extra"  , "Extra")] 
query = '"Olympics" "won"'

cloze2Basic(query, new_type_name, new_fields,original_type_name)


# FIXME: needs to have the latest (?) version of Anki GUI. Or min the same version as the Anki module used here => Either try with older version of Anki library, or issues is fixed when having the script as an addon ?