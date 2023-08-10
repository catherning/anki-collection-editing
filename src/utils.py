
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

def truncate_field(field,max_length=30):
    return f'{field[:max_length]}...' if len(field)>max_length+3 else field


def add_field(col,new_note_type,field):
    fieldDict = col.models.new_field(field)
    col.models.add_field(new_note_type, fieldDict)
    
def get_field_index(note_type,field_name):
    return list(filter(lambda field: field["name"] == field_name, note_type["flds"]))[0]["ord"]

def extract_cloze_field(field_to_extract_index, note, cloze_origin):
    regex = "\{\{%s::([^}:]*):?:?.*\}\}" % cloze_origin
                # TODO: include case when there's several cloze for one card (ex: several {{c1::...}}) => to put in different fields
                # https://regex101.com/r/usAlIw/1
    p = re.compile(regex)
    m = p.search(note.fields[field_to_extract_index])
    if m:
        return m.group(1)
    else:
        logger.error(f"Cloze text: '{note.fields[field_to_extract_index]}'")
        raise Exception(f"Regex {regex} incorrect.")
    

def print_note_content(cloze_text_field, original_model, note_details):
    if original_model["type"] == CLOZE_TYPE:
        cloze_text_index = note_details._fmap[cloze_text_field][1]["ord"]
        return note_details.fields[cloze_text_index]
    else:
        return {field["name"]: truncate_field(note_details[field["name"]]) 
                                    for field in original_model["flds"]
                                    if note_details[field["name"]]!="" and field["name"]!=cloze_text_field}
    