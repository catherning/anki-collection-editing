# from doctest import debug
import numpy as np
import os
from collections import defaultdict
from statistics import median, StatisticsError
from typing import Callable, Optional
import uuid
from json import dump, load
from anki.collection import Collection
from loguru import logger
from langdetect import detect
import re
import sys
from datetime import datetime
from scipy.sparse import lil_array, csr_matrix
from os import path
from annoy import AnnoyIndex 
from src.utils.note_utils import find_notes, get_col_path
from src.utils.field_utils import NoteFieldsUtils
from src.utils.utils import timeit, is_debug_mode
import subprocess
from pathlib import Path,PurePath
# TODO: make as arg

# TODO: method to return the list of groups with main signification summary or an example
# TODO: method to clean synonyms field ? when there's a blank line between each line
# TODO: apply group ID from json file
# TODO: decorréler d'Anki : possibilité de prendre en input fichier csv ou json de vocab ?
# TODO: find synonyms using (hierarchical) clustering of word embedding?

# TODO: fix this, can't find debug mode : because python3.12, works in 3.11 ?

debug_mode = is_debug_mode(logger)

def get_group_query(query_field,group_separator,group_idroup_id):
    # Query like "Synonyms group:re:(^|, )1(, |$)"
    return f'"{query_field}:re:(^|{group_separator}){group_idroup_id}({group_separator}|$)"'


# XXX: where to put the two methods ? new synonyms handling class or field utils or noteutils ? If field utils, then cyclic imports
def remove_group_range(col,field,note_type_name,range_min,range_max,separator=", "):
    c_err = 0
    for group_id in range (range_min, range_max):
        query = get_group_query(field, separator, group_id)
        try:
            notes_id,_ = find_notes(
                    col,
                    query=query, # Notes that are potential synonyms/cognats. We search for those that we already learned
                    note_type_name=note_type_name,
                    override_confirmation = True,
                    verbose=1
                )
        except ValueError:
            continue
        edited_notes = []
        for noteID in notes_id:
            note = col.get_note(noteID)
            groups = note[field].split(separator)
            groups.remove(str(group_id))
            note[field] = separator.join(groups)
            edited_notes.append(note)
        col.update_notes(edited_notes)
    logger.info("Groups removed.")
    col.close()

def get_last_id(col,original_type_name,query_field,group_separator,GROUPS,NOTE_GROUPS,main_signification_field):
    if len(GROUPS)!=0:
        max_id = max([int(id) for id in GROUPS.keys()])
        query = get_group_query(query_field, group_separator, max_id)
        try: 
            notesID, _ = find_notes(
                col,
                query=query,
                verbose=0,
                note_type_name=original_type_name,
                override_confirmation = True
            )
            return max_id
        except ValueError:
            raise ValueError("There's a mismatch between provided groups in JSON and in the database.")
    i=1
    while True:
        # XXX: Could just use max if using csv or pandas struct 
        query = get_group_query(query_field, group_separator, i)
        try: 
            notesID, _ = find_notes(
                col,
                query=query,
                verbose=0,
                note_type_name=original_type_name,
                override_confirmation = True
            )
            _ = add_group_to_dict(col, GROUPS, NOTE_GROUPS,main_signification_field, i, notesID)
            i+=1
        except ValueError:
            return i-1

def add_group_to_dict(col, GROUPS,NOTE_GROUPS, main_signification_field, group_id, notesID):
    # XXX: could do without col, but with pandas or dict struct
    notes_info = []
    unique_id = uuid.uuid4().int
    for noteID in notesID:
        note = col.get_note(noteID)
        notes_info.append({"id":noteID,
                           "text":note[main_signification_field]})
        NOTE_GROUPS[noteID]["text"] = note[main_signification_field]
        NOTE_GROUPS[noteID]["groups"].append((group_id,unique_id))

    GROUPS[str(group_id)] = {"unique_id":unique_id, "notes":notes_info}

    return GROUPS,NOTE_GROUPS


def get_notes_to_edit(col,original_type_name,query):
    logger.info("Finding notes to edit.")
    return find_notes(
                col,
                query=query,
                note_type_name=original_type_name,
                override_confirmation = True
            )

def reversed_assign_group_id(col,group_name,NOTE_GROUPS, group_separator = ", ",tag="auto_edited"):
    notes = []
    for noteID,group_ids in NOTE_GROUPS.items():
        note = col.get_note(noteID)
        note[group_name] = group_separator.join([str(group_id[0]) for group_id in group_ids["groups"]]) # XXX: Add unique_id to Anki note ?
        note.add_tag(tag)
        notes.append(note)
    col.update_notes(notes)

def update_notes_in_group(col, current_max_id, overall_edited_notes, group,GROUPS,NOTE_GROUPS):
    # XXX: could do without col, but with pandas or dict struct
    current_max_id += 1
    GROUPS,NOTE_GROUPS = add_group_to_dict(col, GROUPS, NOTE_GROUPS, main_signification_field, current_max_id, group)
    overall_edited_notes.update(group)
    return current_max_id,overall_edited_notes,GROUPS,NOTE_GROUPS

def create_note_groups(GROUPS):# -> defaultdict[Any, dict[str, str | list[Any]]]:
    NOTE_GROUPS = defaultdict(lambda: {"text":"","groups":[]})
    for groupID,group_info in GROUPS.items():
        unique_id = group_info[0]
        for note in group_info[1]:
            NOTE_GROUPS[note["id"]]["text"] = note["text"]
            NOTE_GROUPS[note["id"]]["groups"].append((groupID,unique_id))
    return NOTE_GROUPS


def merge_groups(GROUPS,NOTE_GROUPS):
    NEW_GROUPS = {**GROUPS}
    c = 0
    remove_groups = []
    new_groups_id_mapping = {i+1:i+1 for i in range(len(NEW_GROUPS))}
    for groupID,notes in GROUPS.items():
        for groupID2,notes2 in GROUPS.items():
            if groupID2 > groupID and groupID2 not in remove_groups:
                g1 = set(note["id"] for note in notes)
                g2 = set(note["id"] for note in notes2)
                common_words = len(g1.intersection(g2))
                if common_words>=3:
                    merged = notes + notes2
                    new_group = list({v['id']:v for v in merged}.values())
                    if len(new_group)<=10 or (common_words>=4): # Prevent creating groups with more than 10 elements
                        NEW_GROUPS[groupID] = list({v['id']:v for v in merged}.values()) # TODO: add unique_id to NEW_GROUPS
                        del NEW_GROUPS[groupID2]
                        remove_groups.append(groupID2)
                        new_groups_id_mapping = {i:j for i,j in new_groups_id_mapping.items() if j }
                        c+=1
                    else:
                        logger.debug(f"Groups {groupID} and {groupID2} were not merged because it would have more than 10 elements. Common words: {common_words}")

    #reset id
    NEW_GROUPS = {str(i+1):groups for i,groups in enumerate(NEW_GROUPS.values())}
    logger.info(f"Merged groups {c} times. Now max id is {len(NEW_GROUPS)}")
    
    NOTE_GROUPS = create_note_groups(NEW_GROUPS)
    return NEW_GROUPS, NOTE_GROUPS

def assign_group_id_to_chinese_manual_group(col,GROUPS,NOTE_GROUPS,noteID, field_text, original_type_name, main_signification_field,current_max_id,overall_edited_notes):
    group_elements = re.findall("[\u4e00-\u9FFF]+|\n", field_text)
    groups = [[noteID]]
    for el in group_elements:
        if el =="\n": # save in constant var / make more flexible ?
            # It's part of another group too
            groups.append([noteID])
        else:
            query = f'"{main_signification_field}:re:^(<div>)?{el}(</div>)?$"'
            try:
                found_group_notes, _ = find_notes(
                    col,
                    query=query,
                    note_type_name=original_type_name,
                    override_confirmation = True,
                    verbose=0
                )
            except ValueError:
                continue
            if len(found_group_notes) == 1:
                groups[-1] += found_group_notes
            else:
                logger.warning("TODO: what to do if there's several notes with the same signification?") # TODO:
    for group in groups:
        if len(group) > 1:
            current_max_id,overall_edited_notes,GROUPS,NOTE_GROUPS = update_notes_in_group(col, current_max_id, overall_edited_notes, group,GROUPS,NOTE_GROUPS)
        else:
            continue
    return current_max_id,overall_edited_notes,GROUPS,NOTE_GROUPS  

def get_word_vector(nlp,word,model="spacy"):
    if model=="spacy":
        return nlp(word).vector
    else:
        return model.encode([word], max_length=256)
    
@timeit
def get_vector_of_notes(nlp,col,notesID,note_field_utils,model="spacy"):
    # XXX: could do without col, but with pandas or dict struct
    if model=="spacy":
        vectors = []
        for noteID in notesID:
            vectors.append(get_word_vector(nlp,note_field_utils.extract_text_from_field(col.get_note(noteID),main_signification_field),model))
        return np.array(vectors)
    else:
        embeddings = nlp.encode(
            [note_field_utils.extract_text_from_field(col.get_note(noteID),main_signification_field) for noteID in notesID],
        )
        return embeddings

def build_index(vector_len,all_vectors):
    t = AnnoyIndex(vector_len, 'angular')
    for i,v in enumerate(all_vectors):
        t.add_item(i, v)
    t.build(10) # 10 trees
    # t.save('chinese.ann')
    return t

@timeit
def calc_group_dist(annoy_index,index_list):
    n_items= annoy_index.get_n_items()
    dist_array = lil_array((n_items,n_items))
    for i, index in enumerate(index_list):
        for index2 in index_list[i+1:]:
                dist_array[index,index2] = annoy_index.get_distance(index,index2)
    return csr_matrix(dist_array)

def calc_sparse_row_mean(dist_array):
    a = dist_array.sum(axis=1).A1
    return np.divide(dist_array.sum(axis=1).A1,dist_array.getnnz(axis=1), out=a,where=dist_array.getnnz(axis=1)!=0)

def calc_sparse_mean(dist_array):
    return dist_array.sum()/dist_array.getnnz()

def remove_outliers_from(list):
    m = median([el for el in list if el!=0])
    try:
        q1 = median([el for el in list if el <= m and el!=0])
    except StatisticsError:
        # No values below median. Can be the case if there are many equal values and only a few above it
        q1 = m
    try:
        q3 = median([el for el in list if el >= m])
    except StatisticsError:
        # No values above median. Can be the case if there are many equal values and only a few below it
        q3 = m
    iqr = q3 - q1
    outliers_index = [i for i,el in enumerate(list) if el > q3 + (iqr * 1.02)]
    if not outliers_index:
        return [list.argmax()]
    return outliers_index
    

def remove_group_outliers(annoy_index, all_deck_notesID, GROUPS,NOTE_GROUPS):
    # TODO: adapt code with unique_id
    for groupID,notes in GROUPS.items():
        g = [all_deck_notesID.index(note["id"]) for note in notes if note["id"] in all_deck_notesID] # else sûrement groupe créé sans vector search
        if len(g)>=10:
            dist_array = calc_group_dist(annoy_index,g)
            # overall_mean = calc_sparse_mean(dist_array)
            mean_array = calc_sparse_row_mean(dist_array)
            outliers_index = remove_outliers_from(mean_array)
            outliers_nID = [all_deck_notesID[el] for el in outliers_index]
            GROUPS[groupID] =  [el for el in notes if el["id"] not in outliers_nID] 
            logger.debug(f"Removing notes {[el["text"] for el in notes if el["id"] in outliers_nID]} from group {groupID}")
    
    NOTE_GROUPS = create_note_groups(GROUPS)
    return GROUPS, NOTE_GROUPS
  

# @timeit
def find_new_groups_from_embedding(col,GROUPS,NOTE_GROUPS,noteID,group_name,main_signification_field,current_max_id,annoy_index,overall_edited_notes,all_deck_notesID,distance_threshold=0.9,tag="auto_edited"):    
    # XXX: not perfect : it necessarily gives a new group. Could have included to an existing group...
    # or use https://github.com/explosion/spaCy/discussions/10465 most_similar, but then must use same logic as in commit 39f1f962fead7de0c48edbb76d36bef941a68728 : check if sim words are in anki
    # but it would do all notesID at once
    # most_similar = nlp.vocab.vectors.most_similar(vectors, n=10)
    
    # XXX: could do without col, but with pandas or dict struct
    nn,distances = annoy_index.get_nns_by_item(all_deck_notesID.index(noteID), 15,include_distances=True)
    nn,distances = nn[1:],distances[1:] # remove the first element which is the note itself
    logger.debug(f"Average distance of 15 closest notes: {np.mean(distances):.2f}, all distances: {[round(el,2) for el in distances]}")
    group = {noteID}
    for nn_index,distance in zip(nn,distances):
        if distance>distance_threshold: # todo calc threshold dynamically, depending on model ?
            break
        
        # TODO: adapt code with unique_id
        g1 = set(NOTE_GROUPS[noteID]["groups"])
        g2 = set(NOTE_GROUPS[all_deck_notesID[nn_index]]["groups"])
        
        if all_deck_notesID[nn_index] not in overall_edited_notes and len(g1.intersection(g2))==0:
            group.add(all_deck_notesID[nn_index])
        elif all_deck_notesID[nn_index] in overall_edited_notes and len(g1.intersection(g2))==0: # Close note was already edited and not in the same group
                group.add(all_deck_notesID[nn_index])
    
    if len(group)>1:
        group = list(group)
        current_max_id,overall_edited_notes,GROUPS,NOTE_GROUPS = update_notes_in_group(col, current_max_id, overall_edited_notes, group,GROUPS,NOTE_GROUPS)
    else:
        closest_note2 = col.get_note(all_deck_notesID[nn[1]])[main_signification_field]     # XXX: could do without col, but with pandas or dict struct
        if distances[1]<1: # TODO: store the threshold in variable
            group.add(all_deck_notesID[1])
            group = list(group)
            current_max_id,overall_edited_notes,GROUPS,NOTE_GROUPS = update_notes_in_group(col, current_max_id, overall_edited_notes, group,GROUPS,NOTE_GROUPS)
        else:
            logger.warning(f"No synonyms found using vector search! Closest note was {closest_note2} with distance {distances[1]}")
    return current_max_id,overall_edited_notes,GROUPS,NOTE_GROUPS


def download_spacy_model(model_name):
    try:
        # Run the command to download the spaCy model
        result = subprocess.run(['poetry','run','python', '-m', 'spacy', 'download', model_name], check=True, capture_output=True, text=True)
        print(f"Model {model_name} downloaded successfully.")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while downloading the model: {e.stderr}")

def main(groups_file, col, tag, hint_field, group_name, main_signification_field, original_type_name, group_separator, query,search_space_query="-is:new",lang="zh",vector_search=True,file_name="groups_ch_syn.json",lib="spacy",model="spacy"):
    # what if json file different from Anki col ? 
    GROUPS = dict(load(open(groups_file, 'rb'))) if path.exists(groups_file) else dict()
    # TODO: or load from file too ?
    NOTE_GROUPS = create_note_groups(GROUPS)

    current_max_id = get_last_id(col,
                                original_type_name,
                                group_name,
                                group_separator= group_separator,
                                GROUPS=GROUPS,
                                NOTE_GROUPS=NOTE_GROUPS,
                                main_signification_field=main_signification_field)

    logger.info(f"Max group ID: {current_max_id}")
    overall_edited_notes = set()
    note_field_utils = NoteFieldsUtils(col,original_type_name)

    notesID, _ = get_notes_to_edit(col,original_type_name,query)

    logger.info("Finding all notes of the same type.")
    
    # if model!="spacy", too long, should shorten the search space
    all_deck_notesID,_ = find_notes(
                col,
                query=search_space_query, # Notes that are potential synonyms/cognats. We search for those that we already learned
                note_type_name=original_type_name,
                override_confirmation = True,
                verbose=1
            )
    if debug_mode:
        all_deck_notesID = list(set(all_deck_notesID[:1000]).union(notesID))
        logger.debug("Debug mode: only 1000 notes will be used.")

    if vector_search:
        match lib:
            case "spacy":
                import spacy
                try:
                    nlp = spacy.load(f'{lang}_core_web_md', exclude=["ner","tagger","parser","senter","attribute_ruler"]) # only tok2vec
                except OSError:
                    download_spacy_model(f'{lang}_core_web_md')
                    nlp = spacy.load(f'{lang}_core_web_md', exclude=["ner","tagger","parser","senter","attribute_ruler"]) # only tok2vec
            case "transformers":
                from torch import bfloat16
                from transformers import AutoModel
                nlp = AutoModel.from_pretrained(model, trust_remote_code=True, torch_dtype=bfloat16)
            case "sentence_transformer":
                from sentence_transformers import SentenceTransformer
                nlp = SentenceTransformer(model)
        logger.info("Model loaded.")
    
        all_vectors = get_vector_of_notes(nlp,col,all_deck_notesID,note_field_utils,model=model)
        nb_vector, vector_len = all_vectors.shape
        annoy_index = build_index(vector_len=vector_len,all_vectors=all_vectors)

        
        all_dist = calc_group_dist(annoy_index,index_list=range(nb_vector))
        logger.debug(f"Average distance between all notes: {calc_sparse_mean(all_dist):.2f}")

    for noteID in notesID:
        note = col.get_note(noteID)

        if noteID in overall_edited_notes:
            # XXX: calculate the average or max or other stat of the distance of words in all the manually created groups to know the threshold   
            if vector_search:
                logger.warning(f"The note '{note[main_signification_field]}' was already found in a group. Searching new syn/cognats group.")
                current_max_id,overall_edited_notes,GROUPS,NOTE_GROUPS = find_new_groups_from_embedding(col,GROUPS,NOTE_GROUPS,noteID,group_name,main_signification_field,current_max_id,annoy_index,overall_edited_notes,all_deck_notesID)
            else:
                logger.info(f"The note '{note[main_signification_field]}' was already found in a group. Doing nothing.")
        
        # It's a group that I created manually : just need to find the other notes in the group and create the group ID
        elif note[hint_field] and (not note[group_name]):
            logger.info(f"Assign group ID {current_max_id+1} for '{note[main_signification_field]}'.")
            hints = note[hint_field].split()
            field_text = note_field_utils.extract_text_from_field(note,hint_field)
            match original_type_name:
                # TODO: make it more flexible
                case "Chinois":
                    # Find the notes with the same signification/cognats, id est, that are in the same group 
                    current_max_id,overall_edited_notes,GROUPS,NOTE_GROUPS = assign_group_id_to_chinese_manual_group(col,GROUPS,NOTE_GROUPS,noteID,field_text, original_type_name, main_signification_field,current_max_id,overall_edited_notes)

        # It's not in a group yet. I need to find the group using word embeddings
        elif (not note[hint_field]) and (not note[group_name]) and vector_search:
            logger.info(f"Finding synonyms/cognats for '{note[main_signification_field]}' using vector search for new group ID {current_max_id+1}")
            current_max_id,overall_edited_notes,GROUPS,NOTE_GROUPS = find_new_groups_from_embedding(col,GROUPS,NOTE_GROUPS,noteID,group_name,main_signification_field,current_max_id,annoy_index,overall_edited_notes,all_deck_notesID)
                

        elif note[group_name]:
            logger.info(f"'{note[main_signification_field]}' already in a group with a group ID.")
            # XXX: Because of this elif where I don't do anything, won't find other groups for the note
                
        else:
            # What else ? only this case : Not in a group yet but no vector_search ?
            logger.warning(f"What's happening for '{note[main_signification_field]}'?")
            breakpoint()
            pass
    
    GROUPS,NOTE_GROUPS = remove_group_outliers(annoy_index, all_deck_notesID, GROUPS,NOTE_GROUPS)
    GROUPS,NOTE_GROUPS = merge_groups(GROUPS,NOTE_GROUPS)
    
    reversed_assign_group_id(col,group_name,NOTE_GROUPS, group_separator = ", ",tag=tag)
    col.close()

    logger.success("Done!")
    now = datetime.now().strftime('%Y%m%d-%H-%M')
    main_file_name = f"{now}_{file_name}"
    save_folder = groups_file.parent if isinstance(groups_file, PurePath) else "data"
    logger.info(f"Saving in {main_file_name}.json and {main_file_name}_noteview.json")
    with open(Path(save_folder,f"{main_file_name}.json"), 'w',encoding="utf-8") as f:
        dump(GROUPS, f,ensure_ascii=False)
    with open(Path(save_folder,f"{main_file_name}_noteview.json"), 'w',encoding="utf-8") as f:
        dump(NOTE_GROUPS, f,ensure_ascii=False)

    return GROUPS


if __name__ == "__main__":

    yaml_file = "src/config.yaml"

    groups_file = max([Path("data",f) for f in os.listdir('data') if f.endswith('.json') and "noteview" not in f], key=os.path.getmtime,default="groups_ch_syn.json")
    print(groups_file)

    COL_PATH = get_col_path(yaml_file)
    col = Collection(COL_PATH)
    if "collection.media" in os.getcwd():
        os.chdir("..")


    tag = "syn_created"  # Flags might have been better, but needs to get to the note cards
    hint_field = "Synonyms"
    group_name = f"{hint_field} group"
    main_signification_field = "Simplified"
    # translation_field = "Meaning"
    original_type_name = "Chinois"
    group_separator = ", "
    model = 'BAAI/bge-small-zh-v1.5'
    lib="sentence_transformer"

    query = f'-is:new -is:suspended tag:marked -tag:{tag}'
    # query = 'Synonyms:_* "Synonyms group:" rated:15'

    main(groups_file, col, tag, hint_field, group_name, main_signification_field, original_type_name, group_separator, query,search_space_query="-is:new",vector_search=True,lib=lib,model = model)
    # remove_group_range(col,group_name,original_type_name,28,1000,group_separator)
    