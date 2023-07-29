from anki.collection import Collection
from anki.models import NotetypeDict, ModelManager

import re
from loguru import logger
from anki_utils import COL_PATH
from cloze2basic import find_notes_to_change


col = Collection(COL_PATH+"collection.anki2")


note_type_name = "Tour de France"

query = '"Coldplay"'

flds_in_hint = ["Year","Winner"]
hint_field = "Extra"


notesID, original_model = find_notes_to_change(col,query, note_type_name,verbose=False)

note_hints = []
for nid in notesID:
    note = col.get_note(nid)

    #TODO: check if all notes have the same type? try if it's already checked. Otherwise, do I need to check note type each time, not above for loop?
    content=""
    for field in flds_in_hint:
        content += f"{note[field]} |" 
    note_hints.append(content)

note_hints_sorted = note_hints[:]
note_hints_sorted.sort()
note_hints_spaced = []

previous_decimal = note_hints_sorted[0][2]
for i, hint in enumerate(note_hints_sorted):
    if hint[2]!=previous_decimal:
        note_hints_spaced.append("")
    note_hints_spaced.append(hint)
    previous_decimal = hint[2]


notes = []
for nid,cur_note_hint in zip(notesID,note_hints):
    note = col.get_note(nid)
    idx = note_hints_spaced.index(cur_note_hint)
    hint = "<br>".join(note_hints_spaced[:idx]) + "<br>?<br>" + "<br>".join(note_hints_spaced[idx+1:])
    note[hint_field] = hint
    notes.append(note)
    
col.update_notes(notes)
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
    pass


