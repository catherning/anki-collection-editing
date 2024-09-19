import numpy as np
from typing import Callable, Optional
from json import dump, load
from anki.collection import Collection
from loguru import logger
from langdetect import detect
import re
from datetime import datetime
from os import path
import spacy
from annoy import AnnoyIndex
# from scipy.spatial.distance import cosine
# from sklearn.metrics.pairwise import cosine_similarity
from src.utils.note_utils import find_notes, get_col_path, get_yaml_value
from src.utils.field_utils import NoteFieldsUtils
from src.utils.utils import timeit
import subprocess
# TODO: make as arg

# TODO: method to return the list of groups with main signification summary or an example
# TODO methods to delete groups, especially starting from a number ?

def get_last_id(col,original_type_name,query_field,group_separator,GROUPS):
    if len(GROUPS)!=0:
        return max(GROUPS.keys()) 
    i=0
    while True:
        i+=1
        query = f'"{query_field}:re:(^|{group_separator}){i}({group_separator}|$)"'

        try: 
            notesID, _ = find_notes(
                col,
                query=query,
                verbose=0,
                note_type_name=original_type_name,
                override_confirmation = True
            )
            GROUPS[str(i)]=notesID
        except ValueError:
            return i-1
    # TODO: save GROUPS. If given and not null, then it's easier to get last id



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

def update_notes_in_group(col, group_name, group_separator, current_max_id, overall_edited_notes, group,GROUPS):
    current_max_id += 1 # FIXME: bof
    GROUPS[str(current_max_id)] = group
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
                logger.warning("TODO: what to do if there's several notes with the same signification?") # TODO:
    for group in groups:
        current_max_id,overall_edited_notes = update_notes_in_group(col, group_name, group_separator, current_max_id, overall_edited_notes, group,GROUPS)
    return current_max_id  

def get_word_vector(word):
    return nlp(word).vector

@timeit
def get_vector_of_notes(col,notesID):
    vectors = []
    for noteID in notesID:
        vectors.append(get_word_vector(col.get_note(noteID)[main_signification_field]))
    return np.array(vectors)

def build_index(vector_len,all_vectors):
    t = AnnoyIndex(vector_len, 'angular')
    for i,v in enumerate(all_vectors):
        t.add_item(i, v)
    t.build(10) # 10 trees
    # t.save('chinese.ann')
    return t

# @timeit
def find_new_groups(col,noteID,current_max_id,t,overall_edited_notes,all_deck_notesID,distance_threshold=0.9):    
    # XXX: not perfect : it necessarily gives a new group. Could have included to an existing group...
    # TODO: or use https://github.com/explosion/spaCy/discussions/10465 most_similar, but then must use same logic as in commit 39f1f962fead7de0c48edbb76d36bef941a68728 : check if sim words are in anki
    # but it would do all notesID at once
    # most_similar = nlp.vocab.vectors.most_similar(vectors, n=10)
    nn,distances = t.get_nns_by_item(all_deck_notesID.index(noteID), 15,include_distances=True)
    group = {noteID}
    for nn_index,distance in zip(nn,distances):
        if distance>distance_threshold:
            break

        note_dup = col.get_note(all_deck_notesID[nn_index])
        g1 = set(note["Synonyms group"].split(","))
        g2 = set(note_dup["Synonyms group"].split(","))
        if all_deck_notesID[nn_index] not in overall_edited_notes and len(g1.intersection(g2))==0:
            group.add(all_deck_notesID[nn_index])
        elif all_deck_notesID[nn_index] in overall_edited_notes and all_deck_notesID[nn_index]!=noteID: # check que des dup ?
            if len(g1.intersection(g2))!=0: # and g1!={""} and g2!={""}:
                print(note["Synonyms group"],note_dup["Synonyms group"])
                pass
                # TODO: 2 notes ne peuvent pas être dans 2 mêmes groupes ! Il faut les fusionner ensemble ou en amont, 
    
    if len(group)>1:
        # XXX: what to do when group is of len(1) ? lower the threshold / use english vectors, makes it even more complicated
        group = list(group)
        current_max_id,overall_edited_notes = update_notes_in_group(col, group_name, group_separator, current_max_id, overall_edited_notes, group,GROUPS)

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

    # TODO: Load file name given by user as args
    groups_file = "groups_ch_syn.json"
    GROUPS = dict(load(open(groups_file, 'rb'))) if path.exists(groups_file) else dict()

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
                                group_name,
                                group_separator= group_separator,
                                GROUPS=GROUPS)

    logger.info(f"Max group ID: {current_max_id}")
    overall_edited_notes = set()
    note_field = NoteFieldsUtils(col,original_type_name, [hint_field])

    notesID, _ = get_notes_to_edit(col,original_type_name)

    all_deck_notesID,_ = find_notes(
                col,
                query="-is:new", # TODO: change to get all notes ? or remove some of them afterwards because it would be increasing with time and thus slow the get_vector_of_notes (and get nn ?) ?
                note_type_name=original_type_name,
                override_confirmation = True,
                verbose=1
            )
    all_vectors = get_vector_of_notes(col,all_deck_notesID)
    vector_len = len(get_word_vector(col.get_note(all_deck_notesID[0])[main_signification_field]))
    t = build_index(vector_len=vector_len,all_vectors=all_vectors)

    for noteID in notesID:
        note = col.get_note(noteID)
        print(note[main_signification_field])

        if noteID in overall_edited_notes:
            logger.info("The note was already found in a group.")
            # breakpoint()
            # TODO: calculate the average or max or other stat of the distance of words in all the groups   
            current_max_id = find_new_groups(col,noteID,current_max_id,t,overall_edited_notes,all_deck_notesID)
        
        # It's a group that I created manually : 
        # just need to find the other notes in the group and create the group ID
        elif note[hint_field] and not note[group_name]:
            # print(note[hint_field])
            hints = note[hint_field].split()
            field_text = note_field.extract_text_from_field(note,hint_field)
            match original_type_name:
                # TODO: make it more flexible
                case "Chinois":
                    # Find the notes with the same signification/cognats, id est, that are in the same group 
                    current_max_id = assign_group_id_to_chinese_manual_group(col,noteID,"", original_type_name, main_signification_field,current_max_id,overall_edited_notes,) # all_vectors,all_deck_notesID

        # It's not in a group yet. I need to find the group using word embeddings
        elif not note[hint_field] :
            current_max_id = find_new_groups(col,noteID,current_max_id,t,overall_edited_notes,all_deck_notesID)
                

        elif note[hint_field] and note[group_name]:
            # The group ID is already set, all is well
            pass
                
        else:
            # What else ?
            breakpoint()
            pass
    
    now = datetime.now().strftime('%Y%m%d%H%M%S')
    dump(GROUPS, open(f"{groups_file.split('.json')[0]}_{now}.json", 'w'))
        #         case "Allemand":
        #             lines = field_text.splitlines()
        #             group_elements = [line for line in lines if detect(line) == 'de']
        
    col.close()