from anki.collection import Collection
from anki.models import NotetypeDict, ModelManager
from anki.notes import Note
from datetime import datetime
from bs4 import BeautifulSoup, FeatureNotFound
from typing import Optional

from loguru import logger
from anki_utils import COL_PATH
from cloze2basic import find_notes_to_change
from utils import CLOZE_TYPE, get_field_index, extract_cloze_field, proceed, print_note_content, truncate_field

def generate_global_hint(col: Collection, notesID: list[str], flds_in_hint: list[str], cloze_field_index=None, separator = ", ", sorting_field = None) -> list[tuple[str,str]]:
    note_hints = []
    c_err = 0
    for nid in notesID:
        note = col.get_note(nid)

        #TODO: check if all notes have the same type? try if it's already checked. Otherwise, do I need to check note type each time, not above for loop?
        content=""
        if note._note_type["type"] == CLOZE_TYPE:
            for cloze in flds_in_hint:
                try:
                    content += extract_cloze_field(cloze_field_index, note, cloze) + separator
                except Exception:
                    logger.error("Hint could not be extracted from cloze field. Is the note type Cloze or the given cloze number correct?")
                    c_err +=1
                # TODO: warnings / error if cloze type but fields given or the opposite
            sorting_info = extract_cloze_field(cloze_field_index, note, sorting_field)
        else:    
            for field in flds_in_hint:
                text = BeautifulSoup(note[field], 'html.parser').text
                clean_text = truncate_field(text.replace("\n", separator), 60)
                content += clean_text + separator
            sorting_info = BeautifulSoup(note[sorting_field], 'html.parser').text
        note_hints.append((content,sorting_info))
    
    if c_err > 0:
        logger.warning("There were errors generating the hint from cloze fields.")
        proceed()
        
    return note_hints

def clean_hint(note_hints,break_lines=False,sorting_key = None) -> list[str]:
    note_hints_sorted = note_hints[:]
    note_hints_sorted.sort(key=sorting_key) # TODO: add sort field. Ex: pinyin
    # Issue with sorting pinyin for now: ex yunmi < yunan whereas it should be the opposite (yu<yun) 
    note_hints_sorted = [el[0] for el in note_hints_sorted]

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


def adapt_hint_to_note(col, note_hints_sorted, original_model, nid, cur_note_hint, hint_field, cloze_text_field, additional_hint_field=None,func = None):
    note = col.get_note(nid)
    idx = note_hints_sorted.index(cur_note_hint[0])
    if additional_hint_field is None:
        hidding_char = "?"
    else:
        
        if original_model["type"] == CLOZE_TYPE:
            cloze_field_index = get_field_index(original_model,cloze_field) if original_model["type"] == CLOZE_TYPE else None
            hidding_char = BeautifulSoup( extract_cloze_field(cloze_field_index, note, additional_hint_field), "html.parser").text[0]
        else:
            try:
                hidding_char = BeautifulSoup(note[additional_hint_field], "html.parser").text[0]
            except KeyError as e:
                logger.error("The field from which you want a more precise hint is missing")
                raise e
            
    hint = ( "<br>".join(note_hints_sorted[:idx]) + 
                ("<br>" if idx!=0 else "") + 
                hidding_char +
                ("<br>" if idx!=len(note_hints_sorted)-1 else "") +
                "<br>".join(note_hints_sorted[idx+1:])
                )
    
    logger.info(f"Hint adapted for the current note {print_note_content(cloze_text_field, original_model, note)}:")
    for el in hint.split("<br>"):
        print(el)
    note[hint_field] = hint
    return note


def generate_hint(note_type_name : str, query : str, 
                  flds_in_hint: list[str], 
                  hint_field: str, 
                  additional_hint_field: Optional[str], 
                  break_lines: bool = False, 
                  separator : str = ", ", 
                  cloze_field: Optional[str], 
                  sorting_key = None, 
                  sorting_field: Optional[str]):
    col = Collection(COL_PATH)
    notesID, original_model = find_notes_to_change(col,query, note_type_name,verbose=True, cloze_text_field=cloze_field)
    
    if len(notesID)<2:
        raise ValueError("There is only one note. You can't generate hints based on several notes.")

    cloze_field_index = get_field_index(original_model,cloze_field) if original_model["type"] == CLOZE_TYPE else None
    
    
    note_hints = generate_global_hint(col, notesID, flds_in_hint, cloze_field_index, separator, sorting_field)
    
    # If the first hint info is numeric, then sort as int (not int as strings, otherwise "10"<"6")
    try:
        if sorting_key is None:
            [int(el[1]) for el in note_hints]
            sorting_key = lambda row: int(row[1])
    except ValueError:
        pass
    
    try:
        note_hints_sorted = clean_hint(note_hints,break_lines, sorting_key=sorting_key)
    except Exception as e:
        logger.error(e)
        logger.error("There might have been an error with the sorting key.")
        exit()
        # new_sorting_key = lambda row: sorting_key(get_first_el(row))
        # note_hints_sorted = clean_hint(note_hints,break_lines, sorting_key=new_sorting_key)
        
    logger.info("The hint that will be repercuted to all notes is:")
    for hint in note_hints_sorted: logger.info(hint)

    notes = []
    for nid,cur_note_hint in zip(notesID,note_hints):
        note = adapt_hint_to_note(col, note_hints_sorted, original_model, nid, cur_note_hint, hint_field, cloze_field, additional_hint_field)
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

    query = "" #'"Academy Award for Best Picture"'
    break_lines = False

    # TODO: Afterwards, for converted cloze to Basic, don't have to filter by using the query, just the note type, AND the field where we have the constant value (ex: Author) to generate the hints
    flds_in_hint = ["Year","Album"]
    cloze_field = "" #"Text"
    hint_field = "Extra"
    sorting_field = "Year"
    sorting_key = None #lambda row: row[1]

    separator = " " # should add spaces
    additional_hint_field = None # "Movie winner"

    # for i in range(3,10):
    #     query = f"Year:19{i}*"
    
    col = Collection(COL_PATH)
    notesID, original_model = find_notes_to_change(col,query, note_type_name,verbose=True, cloze_text_field=cloze_field)
    
    groups = []
    for noteID in notesID:
        note = col.get_note(noteID)
        if note["Group"] not in groups:
            groups.append(note["Group"])
    col.close()
    
    for group in groups:
        query = f'Group:"{group}"'
        try:
            generate_hint(note_type_name, query, flds_in_hint, separator, hint_field, break_lines, additional_hint_field, cloze_field, sorting_key, sorting_field)
        except ValueError as e:
            print(group, e)
            continue
