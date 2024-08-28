import numpy as np
from typing import Callable, Optional
from anki.collection import Collection
from loguru import logger
from langdetect import detect
import re
import spacy
from annoy import AnnoyIndex
# from scipy.spatial.distance import cosine
# from sklearn.metrics.pairwise import cosine_similarity
from src.utils.note_utils import find_notes, get_col_path, get_yaml_value
from src.utils.field_utils import NoteFieldsUtils
from src.utils.utils import timeit
import subprocess
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
                verbose=False,
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

def get_word_vector(word):
    return nlp(word).vector

@timeit
def get_vector_of_notes(col,notesID):
    vectors = []
    for noteID in notesID:
        vectors.append(get_word_vector(col.get_note(noteID)[main_signification_field]))
    return np.array(vectors)

@timeit
def find_new_groups(col,main_signification_field,noteID,current_max_id,all_vectors,overall_edited_notes,all_deck_notesID,distance_threshold=0.9):
    vector_len = len(get_word_vector(col.get_note(noteID)[main_signification_field]))

    t = AnnoyIndex(vector_len, 'angular')
    for i,v in enumerate(all_vectors):
        t.add_item(i, v)
    t.build(10) # 10 trees
    t.save('chinese.ann')
    
    # TODO: or use https://github.com/explosion/spaCy/discussions/10465 most_similar, but then must use same logic as in commit 39f1f962fead7de0c48edbb76d36bef941a68728 : check if sim words are in anki
    # but it would do all notesID at once
    # most_similar = nlp.vocab.vectors.most_similar(vectors, n=10)
    nn,distances = t.get_nns_by_item(all_deck_notesID.index(noteID), 15,include_distances=True)
    group = {noteID}
    for nn_index,distance in zip(nn,distances):
        if distance<=distance_threshold:
            group.add(all_deck_notesID[nn_index])
        else:
            break # TODO: it's sorted, is there more pythonic way ?          
    current_max_id,overall_edited_notes = update_notes_in_group(col, group_name, group_separator, current_max_id, overall_edited_notes, group)

    return current_max_id



def download_spacy_model(model_name):
    try:
        # Run the command to download the spaCy model
        result = subprocess.run(['python', '-m', 'spacy', 'download', model_name], check=True, capture_output=True, text=True)
        print(f"Model {model_name} downloaded successfully.")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while downloading the model: {e.stderr}")

if __name__ == "__main__":

    yaml_file = "src/config.yaml"

    # TODO: change get_yaml_value to retrieve all values at once in a method
    lang = "zh" 
    try:
        nlp = spacy.load(f'{lang}_core_web_md', exclude=["ner","tagger","parser","senter","attribute_ruler"])
    except OSError:
        download_spacy_model(f'{lang}_core_web_md')
        nlp = spacy.load(f'{lang}_core_web_md', exclude=["ner","tagger","parser","senter","attribute_ruler"])

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

    all_deck_notesID,_ = find_notes(
                col,
                query="-is:new", # TODO: change to get all notes ? or remove some of them afterwards because it would be increasing with time and thus slow the get_vector_of_notes (and get nn ?) ?
                note_type_name=original_type_name,
                override_confirmation = True,
                verbose=False
            )
    all_vectors = get_vector_of_notes(col,all_deck_notesID)

    for noteID in notesID:
        note = col.get_note(noteID)
        print(note[main_signification_field])

        if noteID in overall_edited_notes:
            # TODO
            logger.info("The note was already found in a group.")
            breakpoint()
            # TODO: calculate the average or max or other stat of the distance of words in all the groups   
            current_max_id = find_new_groups(col,main_signification_field,noteID,current_max_id,all_vectors,overall_edited_notes,all_deck_notesID)
        
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
                    current_max_id = assign_group_id_to_chinese_manual_group(col,main_signification_field,noteID,current_max_id,all_vectors,overall_edited_notes,all_deck_notesID)

        # It's not in a group yet. I need to find the group using word embeddings
        elif not note[hint_field] :
            current_max_id = find_new_groups(col,note,main_signification_field,noteID,original_type_name,current_max_id,notesID,all_vectors,overall_edited_notes)
                

        # The group ID is already set: what do I need to edit? I must call this from the new note that is added to the group
        elif note[hint_field] and note[group_name]:
            breakpoint()
            pass
        
        # It's not in a group yet. I need to find the group using word embeddings
        elif not note[hint_field] :
            current_max_id = find_new_groups(col,main_signification_field,noteID,current_max_id,all_vectors,overall_edited_notes,all_deck_notesID)
                
        else:
            # What else ?
            breakpoint()
            pass
             
        #         case "Allemand":
        #             lines = field_text.splitlines()
        #             group_elements = [line for line in lines if detect(line) == 'de']
        
    col.close()