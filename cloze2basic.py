from anki_utils import COL_PATH
from anki.collection import Collection
from anki.models import NotetypeDict, ModelManager

import re
from loguru import logger

CLOZE_TYPE = 1

def proceed():
    print("Proceed ? (Y/n)")
    a = input()
    if a=="y":
        logger.info("Please write 'Y' if you want to proceed.")
        a=input()
    if a!="Y":
        logger.info("Stopping prematurely at the user's request")
        exit() 

def truncate_field(field):
    return field[:30]+'...' if len(field)>33 else field

def find_notes_to_change(col: Collection,
                         query: str,
                         cloze_type_name: str = "Cloze",
                         cloze_text_field="Text") -> tuple[list[int],int]: 
    """Retrieves the notes to change according to a query.

    Args:
        col (Collection): The full Anki collection with all models and notes
        query (str): The query to use to match the pattern of the cards to change
        cloze_type_name (str, optional): The name of the Cloze note type. Defaults to "Cloze".

    Raises:
        ValueError: If the query or cloze note type name is wrong and no note was found 

    Returns:
        list[int]: The list of the IDs of the notes to convert
    """
    
    # Get the notes to edit
    new_query  = query + f' note:"{cloze_type_name}"'
    notesID = col.find_notes(new_query)

    if len(notesID)==0:
        raise ValueError("No notes found. Please review your query and cloze note type")
    else:
        logger.info(f"Number of notes found: {len(notesID)}")
        original_modelID = col.models.get_single_notetype_of_notes(notesID)
        original_model = col.models.get(original_modelID)
        for note in notesID:
            note_details = col.get_note(note)
            cloze_text_index = note_details._fmap[cloze_text_field][1]["ord"]
            logger.info(note_details.fields[cloze_text_index])
            for k,field in enumerate(note_details.fields):
                if original_model["type"]!= CLOZE_TYPE and field !="" and k!=cloze_text_index:
                    logger.warning(f'Field of the basic note is not empty and the text "{truncate_field(field)}" might be replaced')
        proceed()
    return list(notesID), original_model

def add_field(col,new_note_type,field):
    fieldDict = col.models.new_field(field)
    col.models.add_field(new_note_type, fieldDict)

def create_note_type(col: Collection,
                     note_name:str,
                     new_fields:list[str],
                     original_field_list: list[str]) -> NotetypeDict:
    """Creates the new note type and the card templates.

    Args:
        col (Collection): The full Anki collection with all models and notes
        note_name (str): The name of the new note
        new_fields (list[str]): The list of new field names and the information on how to fill it
        original_field_list (list[str]): The list of 

    Returns:
        NotetypeDict: The new note type dictionary
    """
    # Create new note type
    models = col.models
    new_note_type = models.new(note_name)

    for i,field_info in enumerate(new_fields):
        add_field(col,new_note_type,field_info[0])

        if field_info[1] not in original_field_list:
            # Add template
            template = models.new_template(f"Answer: {field_info[0]}")

            models.add_template(new_note_type,template)

            new_note_type["tmpls"][i]["qfmt"] = "{{%s}}" % (new_fields[(i+1)%len(new_fields)][0])
            new_note_type["tmpls"][i]["afmt"] = "{{%s}}" % (field_info[0])

    models.save(new_note_type)
    
    return new_note_type
    

def change_note_type(col, 
                     old_note_type: dict,
                     new_note_type: dict,
                     notesID: list[int],
                     new_fields: list[str] ):
    # Change the note type

    if len(new_fields)<2:
        raise ValueError("You must map at least two fields")
    
    fmap = dict()
    original_fields = old_note_type["flds"]
    
    for target_field_info in new_fields:
        try:
            # Map the ordinal position of the original field to the ordinal position (f_info["ord"]) of the target field 
            target_ord = next(filter(lambda field: target_field_info[0] == field['name'], new_note_type["flds"]))["ord"]
            original_ord = [original_field_info["ord"] for original_field_info in original_fields if target_field_info[1] == original_field_info["name"]][0]
            fmap[original_ord] = target_ord
            logger.info(f"Target field {target_field_info[0]} will be mapped from the field '{target_field_info[1]}'")
        except IndexError: # When taking the index 0 of empty list
            if re.compile("c\d").search(target_field_info[1]):
                logger.info(f"Target field {target_field_info[0]} will extract the {target_field_info[1]} cloze field")
            else:
                logger.error(f"Field not found. Wrong field name: '{target_field_info[1]}'. Please restart the script with the correct field name or proceed. The field will be empty")
                logger.info(f"For your information, the fields of the original note are: {[f_info['name'] for f_info in original_fields]}")
        except StopIteration:
            # Should not happen as we create the missing fields before
            logger.errror(f"Field {target_field_info[0]} is not present in new note type. It will be created")

            
    proceed()
    col.models.change(old_note_type, notesID, new_note_type, fmap, cmap=None)
    logger.warning("The notes were converted even if the extraction is not validated.")
    
def extract_info_from_cloze(col,
                            notesID,
                            new_note_type,
                            new_fields,
                            original_field_list,
                            cloze_text_field="Text"):

    if "Original cloze text"==new_fields[-1][0]:
        field_to_extract_index = -1
    else:
        field_to_extract_index = list(filter(lambda field: field["name"] == cloze_text_field, new_note_type["flds"]))[0]["ord"]

    
    
    notes = []
    for noteID in notesID:
        note = col.get_note(noteID)
        for i,(target_field,field_origin) in enumerate(new_fields): # Could use last value to see if it's a regex / cloze extraction
            if field_origin not in original_field_list:
                regex = "\{\{%s::([^}:]*):?:?.*\}\}" % (field_origin)
                # TODO: include case when there's several cloze for one card (ex: several {{c1::...}}) => to put in different fields
                # https://regex101.com/r/usAlIw/1
                p = re.compile(regex)
                m = p.search(note.fields[field_to_extract_index])
                if m:
                    note.fields[i] =  m.group(1)
                else:
                    logger.error(f"Cloze text: '{note.fields[field_to_extract_index]}'")
                    raise Exception(f"Regex {regex} incorrect. Information to put in {target_field=} not found. Maybe the original field name was wrong?")
                    # TODO: give the list of the notes with incorrect transformation and continue the process

        logger.info(f"Final fields of the note: {[truncate_field(fld) for fld in note.fields]}")
        notes.append(note)
        
    logger.info("Confirm the mappings and save notes ? (Y/n)")
    if input()=="Y":
        col.update_notes(notes)
        logger.success("New notes created and saved in the collection!")
    else:
        logger.warning("The note field extraction was not saved. But the notes were already converted.")
    col.close()
        
            

def cloze2Basic(query: str,
                new_type_name: str = None, 
                new_fields: list[any] = None,
                original_type_name = "Cloze",
                cloze_text_field = "Text"
                ):
    col = Collection(COL_PATH+"collection.anki2")

    notesID, original_model = find_notes_to_change(col,query, original_type_name,cloze_text_field)
    
    original_field_list = [fld["name"] for fld in original_model["flds"]]

    # If model is of type Cloze, we do the conversion, otherwise we just do the regex extraction
    if original_model["type"] == CLOZE_TYPE : 
        
        # If the user doesn't map the Text field to a target field, we do it
        if not [el for el in new_fields if cloze_text_field in el[1]]:
            new_fields.append(("Original cloze text",cloze_text_field))
        
        # Resume a conversion if the new type was already created before
        new_note_type = col.models.by_name(new_type_name) 
        if new_note_type is None:
            new_note_type = create_note_type(col, new_type_name, new_fields,original_field_list)
        
        missing_fields = set(field[0] for field in new_fields) - set(field["name"] for field in new_note_type["flds"])
        for field in missing_fields:
            logger.warning(f"Creation of the field '{field}' which is not present in new note type")
            add_field(col, new_note_type, field)
        col.models.save(new_note_type)
        
        change_note_type(col,original_model, new_note_type, notesID, new_fields)
    else:
        new_note_type = original_model
    
    extract_info_from_cloze(col,notesID,new_note_type,new_fields,original_field_list,cloze_text_field)


# TODO: when code is correct, use args instead (don't need to debug) 
new_type_name = "Litterature"
original_type_name = "Cloze" #"Cloze Music & Sport" # "Olympic winners bis"
new_fields = [("Book" , "c3"),
              ("Year"   , "c2"),
              ("Author"   , "c1"),
              ("Extra"  , "Extra")
              ] 
query = 'Ernest Hemingway wrote'
cloze_text_field= "Text" #"Original cloze text" # 

cloze2Basic(query, new_type_name, new_fields, original_type_name,cloze_text_field)


# FIXME: needs to have the latest (?) version of Anki GUI. Or min the same version as the Anki module used here => Either try with older version of Anki library, or issues is fixed when having the script as an addon ?s