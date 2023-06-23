CLOZE_TYPE = 1

from loguru import logger

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