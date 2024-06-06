import numpy as np
from typing import Callable, Optional
from anki.collection import Collection
from loguru import logger
from langdetect import detect
import re
import fasttext.util
from sklearn.metrics.pairwise import cosine_similarity
from src.utils.note_utils import find_notes, get_col_path, get_yaml_value
from src.utils.field_utils import NoteFieldsUtils
from src.utils.utils import timeit
# TODO: make as arg

def get_last_id(col,original_type_name,query_field,group_separator):
    
    i=0
    while True:
        i+=1
        query = f'"{query_field}:re:(^|{group_separator}){i}({group_separator}|$)"'

        try: 
            notesID, _ = find_notes(
                col,
                query=query,
                note_type_name=original_type_name,
                override_confirmation = True
            )
        except ValueError:
            return i-1


def get_notes_to_edit(col,original_type_name):
    query = f'-is:new -is:suspended tag:marked'
    return find_notes(
                col,
                query=query,
                note_type_name=original_type_name,
                override_confirmation = True
            )

def assign_group_id(col,noteIDs,group_name,group_id, group_separator = ", "):
    notes = []
    for noteID in noteIDs:
        note = col.get_note(noteID)
        if note[group_name]:
            note[group_name] += group_separator
        note[group_name] += str(group_id)
        notes.append(note)
    col.update_notes(notes)

def update_notes_in_group(col, group_name, group_separator, current_max_id, overall_edited_notes, group):
    current_max_id += 1 # FIXME: bof
    assign_group_id(col,group,group_name,current_max_id, group_separator)
    overall_edited_notes.update(group)
    # TODO: change flag of notes so that we can still check manually just in case
    return current_max_id, overall_edited_notes

def assign_group_id_to_chinese_manual_group(col,noteID, field_text, original_type_name, main_signification_field,current_max_id,overall_edited_notes):
    group_elements = re.findall("[\u4e00-\u9FFF]+|\n", field_text)
    groups = [[noteID]]
    for el in group_elements:
        query = f"{main_signification_field}:{el}"
        if el =="\n": # save in constant var / make more flexible ?
            # It's part of another group too
            groups.append([noteID])
        else:
            found_group_notes, _ = find_notes(
                col,
                query=query,
                note_type_name=original_type_name,
                override_confirmation = True
            )
            if len(found_group_notes) == 1:
                groups[-1] += found_group_notes
            else:
                logger.warning("TODO: what to do if there's several notes with the same signification?")
    for group in groups:
        current_max_id,overall_edited_notes = update_notes_in_group(col, group_name, group_separator, current_max_id, overall_edited_notes, group)
    return current_max_id


def get_vector_of_notes(col,notesID,ft):
    vectors = []
    for noteID in notesID:
        vectors.append(ft.get_word_vector(col.get_note(noteID)[main_signification_field]))
    return np.array(vectors)



def find_new_groups(col,note,main_signification_field,noteID,original_type_name,current_max_id,notesID,vectors,overall_edited_notes):
    # 1.TODO: only for synonyms, not cognats
    nn = ft.get_nearest_neighbors(note[main_signification_field])
    group = [noteID]
    for neighbour in nn:
        # check if neighbour in cards
        query = f"{main_signification_field}:{neighbour[1]}"
        try:
            found_group_notes, _ = find_notes(
                            col,
                            query=query,
                            note_type_name=original_type_name,
                            override_confirmation = True
                        )
        except ValueError:
            continue
        # TODO: What if it's part of several groups and I don't know ? at first change manually afterwards? 
        # use the english translation and if there's different meaning, vectorize, find similar words in english then translate ?
        if len(found_group_notes)==1:
            group.append(found_group_notes[0])                
        else:
            pass
            # TODO: what?
    current_max_id,overall_edited_notes = update_notes_in_group( col, group_name, group_separator, current_max_id, overall_edited_notes, group)

    # Find closest vectors from the notes to edit
    cos_sim = cosine_similarity(np.expand_dims(vectors[notesID.index(noteID),:],0),vectors)[0]
    sorted_indices = np.argsort(-cos_sim)
    filtered_indices = sorted_indices[cos_sim[sorted_indices] >= 0.5]
    top_indices = filtered_indices[:5]
    sim_group = [notesID[i] for i in top_indices]
    current_max_id,overall_edited_notes = update_notes_in_group( col, group_name, group_separator, current_max_id, overall_edited_notes, sim_group)
    return current_max_id



if __name__ == "__main__":

    yaml_file = "src/config.yaml"

    # TODO: change get_yaml_value to retrieve all values at once in a method
    # ch_embedding_path = get_yaml_value(yaml_file,"ch_embedding_path")
    # wv_from_text = KeyedVectors.load_word2vec_format(ch_embedding_path, binary=False, unicode_errors='replace')
    lang = "zh" 
    fasttext.util.download_model(lang, if_exists='ignore')
    ft = fasttext.load_model(f'cc.{lang}.300.bin')
    ft.get_nearest_neighbors = timeit(ft.get_nearest_neighbors)

    logger.info("Model loaded")
    
    COL_PATH = get_col_path(yaml_file)
    col = Collection(COL_PATH)

    hint_field = "Synonyms"
    group_name = f"{hint_field} group"
    main_signification_field = "Simplified"
    translation_field = "Meaning"
    original_type_name = "Chinois"
    group_separator = ", "
    current_max_id = get_last_id(col,
                                original_type_name,
                                group_name,group_separator= group_separator)

    print(current_max_id)
    overall_edited_notes = set()
    note_field = NoteFieldsUtils(col,original_type_name, [hint_field])

    notesID, _ = get_notes_to_edit(col,original_type_name)
    # notesID_rev = {noteID:i for i,noteID in enumerate(notesID)}
    vectors = get_vector_of_notes(col,notesID,ft)

    for noteID in notesID:
        note = col.get_note(noteID)
        print(note[main_signification_field])

        if noteID in overall_edited_notes:
            # TODO
            logger.warning("The note was already found in a group! What to do ?")
            breakpoint()
            current_max_id = find_new_groups(col,note,main_signification_field,noteID,original_type_name,current_max_id,notesID,vectors,overall_edited_notes)
        
        # It's a group that I created manually : 
        # just need to find the other notes in the group and create the group ID
        elif note[hint_field] and not note[group_name]:
            print(note[hint_field])
            hints = note[hint_field].split()
            field_text = note_field.extract_text_from_field(note,hint_field)
            match original_type_name:
                # TODO: make it more flexible
                case "Chinois":
                    # Find the notes with the same signification/cognats, id est, that are in the same group 
                    current_max_id = assign_group_id_to_chinese_manual_group(col,noteID, field_text, original_type_name, main_signification_field,current_max_id,overall_edited_notes)

        # It's not in a group yet. I need to find the group using word embeddings
        elif not note[hint_field] :
            current_max_id = find_new_groups(col,note,main_signification_field,noteID,original_type_name,current_max_id,notesID,vectors,overall_edited_notes)
                

        # The group ID is already set: what do I need to edit? I must call this from the new note that is added to the group
        elif note[hint_field] and note[group_name]:
            breakpoint()
            pass
        
        else:
            # What else ?
            breakpoint()
            pass

                        
        #         case "Allemand":
        #             lines = field_text.splitlines()
        #             group_elements = [line for line in lines if detect(line) == 'de']
        
        
        
    print(len(notesID))
    col.close()