from anki_utils import COL_PATH
from anki.collection import Collection
from anki.models import NotetypeDict, ModelManager

import re
from loguru import logger

def find_notes_to_change(col: Collection,
                         query: str,
                         cloze_type_name: str = "Cloze") -> list[int]:
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
        for note in notesID:
            logger.info(col.get_note(note).fields[0])
        print("Proceed ? (y/n)")
        if input()!="y":
            exit() 
    return list(notesID)


def create_note_type(col: Collection,
                     note_name:str,
                     new_fields:list[str],
                     original_field_list: list[str]) -> NotetypeDict:
    """Creates the new note type and the card templates

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
        fieldDict = models.new_field(field_info[0])
        models.add_field(new_note_type, fieldDict)
        
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
    
    col.models.change(old_note_type, notesID, new_note_type, fmap, cmap=None)
    

def extract_info_from_cloze(col,
                            notesID,
                            new_fields,
                            original_field_list):

    if "Original cloze text"==new_fields[-1][0]:
        field_to_extract = -1
    else:
        text_field = [(f_info,i) for i,f_info in enumerate(new_fields) if f_info[2]=="Text"][0]
        field_to_extract = text_field[1]
    
    
    notes = []
    for noteID in notesID:
        note = col.get_note(noteID)
        for i,(target_field,field_origin) in enumerate(new_fields): # Could use last value to see if it's a regex / cloze extraction
            if field_origin not in original_field_list:
                regex = "\{\{%s::([^}:]*):?:?.*\}\}" % (field_origin)
                # TODO: include case when there's several cloze for one card (ex: several {{c1::...}}) => to put in different fields
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
        notes.append(note)
        
    logger.info("Confirm the mappings and save notes ? (yes/no)")
    if input()=="yes":
        col.update_notes(notes)
        
            

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
        
        # Resume a conversion if the new type was already created before
        new_note_type = models.by_name(new_type_name) 
        if new_note_type is None:
            new_note_type = create_note_type(col, new_type_name, new_fields,original_field_list)
        
        change_note_type(col,original_model, new_note_type, notesID, new_fields)
    
    extract_info_from_cloze(col,notesID,new_fields,original_field_list)

    col.close()
    logger.success("New notes created and saved in the collection!")


new_type_name = "Tour de France Winners"
original_type_name = "Cloze Music & Sport"
new_fields = [("Winner" , "c1"),
              ("Year"   , "c2"),
              ("Extra"  , "Back Extra")] 
query = '"Tour de France" "won the {{c2"'

cloze2Basic(query, new_type_name, new_fields,original_type_name)


# FIXME: needs to have the latest (?) version of Anki GUI. Or min the same version as the Anki module used here => Either try with older version of Anki library, or issues is fixed when having the script as an addon ?