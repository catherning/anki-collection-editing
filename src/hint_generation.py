from anki.collection import Collection
from anki.models import NotetypeDict, ModelManager

from bs4 import BeautifulSoup, FeatureNotFound
import re
from loguru import logger
from anki_utils import COL_PATH
from cloze2basic import find_notes_to_change

def generate_global_hint(col, notesID, flds_in_hint, separator = ","):
    note_hints = []
    for nid in notesID:
        note = col.get_note(nid)

        #TODO: check if all notes have the same type? try if it's already checked. Otherwise, do I need to check note type each time, not above for loop?
        content=""
        for field in flds_in_hint:
            content += f"{note[field]} {separator} " 
        note_hints.append(content)
    return note_hints

def clean_hint(note_hints,break_lines=False):
    note_hints_sorted = note_hints[:]
    note_hints_sorted.sort() # TODO: add sort field ? Now it's just the first field in flds_in_hint

    # Specifics to have lines breaks between decades when the sorting field is Year
    if break_lines:
        note_hints_spaced = []
        previous_decimal = note_hints_sorted[0][2]
        for i, hint in enumerate(note_hints_sorted):
            if hint[2]!=previous_decimal:
                note_hints_spaced.append("")
            note_hints_spaced.append(hint)
            previous_decimal = hint[2]
        note_hints_sorted = note_hints_spaced
    return note_hints_sorted


def adapt_hint_to_note(col, note_hints_sorted, nid, cur_note_hint, hint_field,additional_hint=False,additional_hint_field_char=None):
    note = col.get_note(nid)
    idx = note_hints_sorted.index(cur_note_hint)
    if additional_hint == False:
        hidding_char = "?"
    else:
        try:
            hidding_char = BeautifulSoup(note[additional_hint_field_char], "lxml").text[0]
        except FeatureNotFound:
            hidding_char = BeautifulSoup(note[additional_hint_field_char], "html.parser").text[0]
        except KeyError:
            logger.error("The field from which you want a more precise hint is missing")
            
    hint = ( "<br>".join(note_hints_sorted[:idx]) + 
                ("<br>" if idx!=0 else "") + 
                hidding_char +
                ("<br>" if idx!=len(note_hints_sorted)-1 else "") +
                "<br>".join(note_hints_sorted[idx+1:])
                )
    logger.info("Hint adapted for the current note:")
    for el in hint.split("<br>"):
        print(el)
    note[hint_field] = hint
    return note


def generate_hint(note_type_name, query, flds_in_hint, separator, hint_field, break_lines, additional_hint, additional_hint_field_char):
    col = Collection(COL_PATH)
    notesID, original_model = find_notes_to_change(col,query, note_type_name,verbose=True, cloze_text_field="Original cloze text")
    
    note_hints = generate_global_hint(col, notesID,flds_in_hint, separator)
    
    note_hints_sorted = clean_hint(note_hints,break_lines)
    logger.info("The hint that will be repercuted to all notes is:")
    for hint in note_hints_sorted: logger.info(hint)

    notes = []
    for nid,cur_note_hint in zip(notesID,note_hints):
        note = adapt_hint_to_note(col, note_hints_sorted, nid, cur_note_hint, hint_field, additional_hint, additional_hint_field_char)
        notes.append(note)
    
    logger.info("Confirm the hint generation and save notes ? (Y/n)")
    if input()=="Y":
        col.update_notes(notes)
        logger.success("New note hints saved in the collection!")

    col.close()


# for nid in notesID:
#     note = col.get_note(nid)
#     for i,part in enumerate(parts):
#         if part.find(content_to_hide)==0: #TODO: change, when german, rule could change... Check if no lines had the content to hide, is it really a synonym ? To notify user

#             if note_type_name=="Chinois":
#                 try:
#                     soup = BeautifulSoup(note["Pinyin.1"],"html.parser")
#                     plain_pinyin=soup.get_text(" ",strip=True)
#                     parts[i] = plain_pinyin[0]
#                 except IndexError:
#                     r = requests.get(f'https://helloacm.com/api/pinyin/?cached&s={content_to_hide}')
#                     parts[i]=r.json()["result"][0][0]
                    
#             else:
#                 parts[i] = "?" #TODO: if option, get first letter of the content of field XXX. Else, just ?


if __name__ == "__main__":
    
    note_type_name = "Music"

    query = '"Kanye"'
    break_lines = False


    # TODO: If cloze: then give the cloze that would be the sorting field and the hint one
    # If basic: give the field

    # TODO: Afterwards, for converted cloze to Basic, don't have to filter by using the query, just the note type, AND the field where we have the constant value (ex: Author) to generate the hints
    flds_in_hint = ["Year","Album"]
    hint_field = "Extra"

    separator = "|"
    additional_hint = True
    additional_hint_field_char = "Album"

    generate_hint(note_type_name, query, flds_in_hint, separator, hint_field, break_lines, additional_hint, additional_hint_field_char)

