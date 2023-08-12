# Fonctionalities

## Use cases
- I use the Extra field as a hint, showing a list of similar answers to other cards. But it's a hint only for some fields, it contains the answer for other fields. But in a cloze note, we can't chose if we want to show the Extra field for specific cloze fields, not all of them. Furthermore, I have sevaral cloze notes who follow the same patterns. So I transform the Cloze cards into basic cards where I can adapt the card templates : for some cards, I show the Extra field in the question, for others, in the Answer.

# Installation

- Careful: if in WSL, must copy the collection to WSL file system. Refering to the collection in Windows filesystem (`/mnt/c` etc) seems to create an empty collection. TODO: check why. anki library in linux is different?

# TODOs
- Handle the repetition of cloze field number (several {{c1:...}})
- Allow for mistakes => undo or else ?

`cp "/mnt/c/Users/User/AppData/Roaming/Anki2/User 1/collection.anki2" ~/anki-editing/anki-collection-editing/data/collection.anki2`

# Examples of scripts to automate editing notes

## Convert cloze notes on the same theme. 

But sometimes c1 refers to one field, sometimes to another
    
    clozes = ["c1","c2","c3"]
    
    for album_cloze in clozes:
        for year_cloze in clozes:
            for group_cloze in clozes:
                if album_cloze == year_cloze or album_cloze == group_cloze or year_cloze == group_cloze:
                    continue
                
                print(f"{album_cloze=} {year_cloze=} {group_cloze=}")
                new_fields = [("Album" , album_cloze),
                            ("Year"   , year_cloze),
                            ("Group", group_cloze),
                            ("Extra"  , "Back Extra")
                            ] 
                query = 'album re:' + album_cloze + '.*c\d.*c\d re:\{\{' + year_cloze + '::\d{4}' # re:c\d.*c\d.*c\d "re:\{\{c2::\d"' # 
                cloze_text_field= "Text" #"Original cloze text"

                try:
                    cloze2Basic(query = query, new_type_name = new_type_name , new_fields=new_fields ,original_type_name=original_type_name,cloze_text_field=cloze_text_field)
                except ValueError:
                    continue

## Generate hints

This script will generate the hints as the list of the albums done by a group.
*
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
            generate_hint(note_type_name, query, flds_in_hint, separator, hint_field, break_lines, additional_hint_field_char, cloze_field, sorting_key, sorting_field)
        except ValueError as e:
            print(group, e)
            continue
