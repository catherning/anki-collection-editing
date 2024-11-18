import numpy as np
from collections import defaultdict
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
from src.utils.note_utils import find_notes, get_col_path
from src.utils.field_utils import NoteFieldsUtils
from src.utils.utils import timeit
import subprocess
# TODO: make as arg

# TODO: method to return the list of groups with main signification summary or an example
# TODO: methods to delete groups, especially starting from a number ?
# TODO: method to clean synonyms field ? when there's a blank line between each line?
# TODO: apply group ID from json file

def get_last_id(col,original_type_name,query_field,group_separator,GROUPS,main_signification_field):
    if len(GROUPS)!=0:
        # TODO: check that last group ID exists indeed in the database
        return max([int(id) for id in GROUPS.keys()]) 
    i=0
    while True:
        i+=1
        query = f'"{query_field}:re:(^|{group_separator}){i}({group_separator}|$)"'
        # query is something like "Synonyms group:re:(^|, )1(, |$)"

        try: 
            notesID, _ = find_notes(
                col,
                query=query,
                verbose=0,
                note_type_name=original_type_name,
                override_confirmation = True
            )
            add_group_to_dict(col, GROUPS, main_signification_field, i, notesID)
        except ValueError:
            return i-1

def add_group_to_dict(col, GROUPS, main_signification_field, group_id, notesID):
    notes_info = []
    for noteID in notesID:
        note = col.get_note(noteID)
        notes_info.append({"id":noteID,
                           "text":note[main_signification_field]})
    GROUPS[str(group_id)] = notes_info
    return GROUPS


def get_notes_to_edit(col,original_type_name,query):
    return find_notes(
                col,
                query=query,
                note_type_name=original_type_name,
                override_confirmation = True
            )

def assign_group_id(col,noteIDs,group_name,group_id, group_separator = ", ",tag="auto_edited"):
    notes = []
    for noteID in noteIDs:
        note = col.get_note(noteID)
        if note[group_name]:
            note[group_name] += group_separator
        note[group_name] += str(group_id)
        note.add_tag(tag)
        notes.append(note)
    col.update_notes(notes)

def reversed_assign_group_id(col,group_name,NOTE_GROUPS, group_separator = ", ",tag="auto_edited"):
    notes = []
    for noteID,group_ids in NOTE_GROUPS.items():
        note = col.get_note(noteID)
        note[group_name] = group_separator.join([str(group_id) for group_id in group_ids])
        note.add_tag(tag)
        notes.append(note)
    col.update_notes(notes)

def update_notes_in_group(col, group_name, group_separator, current_max_id, overall_edited_notes, group,GROUPS,tag="auto_edited"):
    current_max_id += 1
    GROUPS = add_group_to_dict(col, GROUPS, main_signification_field, current_max_id, group)
    # assign_group_id(col,group,group_name,current_max_id, group_separator,tag)
    overall_edited_notes.update(group)
    return current_max_id,overall_edited_notes,GROUPS

def assign_group_id_to_chinese_manual_group(col,GROUPS,noteID, field_text, original_type_name, main_signification_field,current_max_id,overall_edited_notes,tag):
    group_elements = re.findall("[\u4e00-\u9FFF]+|\n", field_text)
    groups = [[noteID]]
    for el in group_elements:
        if el =="\n": # save in constant var / make more flexible ?
            # It's part of another group too
            groups.append([noteID])
        else:
            query = f"{main_signification_field}:{el}"
            try:
                found_group_notes, _ = find_notes(
                    col,
                    query=query,
                    note_type_name=original_type_name,
                    override_confirmation = True
                )
            except ValueError:
                continue
            if len(found_group_notes) == 1:
                groups[-1] += found_group_notes
            else:
                logger.warning("TODO: what to do if there's several notes with the same signification?") # TODO:
    for group in groups:
        if len(group) > 1:
            current_max_id,overall_edited_notes,GROUPS = update_notes_in_group(col, group_name, group_separator, current_max_id, overall_edited_notes, group,GROUPS,tag)
        else:
            continue
    return current_max_id,overall_edited_notes,GROUPS  

def get_word_vector(nlp,word):
    return nlp(word).vector

@timeit
def get_vector_of_notes(nlp,col,notesID,note_field_utils):
    vectors = []
    for noteID in notesID:
        vectors.append(get_word_vector(nlp,note_field_utils.extract_text_from_field(col.get_note(noteID),main_signification_field)))
    return np.array(vectors)

def build_index(vector_len,all_vectors):
    t = AnnoyIndex(vector_len, 'angular')
    for i,v in enumerate(all_vectors):
        t.add_item(i, v)
    t.build(10) # 10 trees
    # t.save('chinese.ann')
    return t

# @timeit
def find_new_groups(col,GROUPS,noteID,current_max_id,annoy_index,overall_edited_notes,all_deck_notesID,distance_threshold=0.8,tag="auto_edited"):    
    # XXX: not perfect : it necessarily gives a new group. Could have included to an existing group...
    # or use https://github.com/explosion/spaCy/discussions/10465 most_similar, but then must use same logic as in commit 39f1f962fead7de0c48edbb76d36bef941a68728 : check if sim words are in anki
    # but it would do all notesID at once
    # most_similar = nlp.vocab.vectors.most_similar(vectors, n=10)
    note = col.get_note(noteID)
    nn,distances = annoy_index.get_nns_by_item(all_deck_notesID.index(noteID), 15,include_distances=True)
    group = {noteID}
    for nn_index,distance in zip(nn,distances):
        if distance>distance_threshold:
            break

        close_note = col.get_note(all_deck_notesID[nn_index])
        g1 = set(note["Synonyms group"].split(","))
        g2 = set(close_note["Synonyms group"].split(","))
        if all_deck_notesID[nn_index] not in overall_edited_notes and len(g1.intersection(g2))==0:
            group.add(all_deck_notesID[nn_index])
        elif all_deck_notesID[nn_index] in overall_edited_notes and all_deck_notesID[nn_index]!=noteID: # check que des dup ?
            if len(g1.intersection(g2))!=0 and g1!={""} and g2!={""}:
                print(note["Synonyms group"],close_note["Synonyms group"])
                continue
                # TODO: 2 notes ne peuvent pas être dans 2 mêmes groupes ! Il faut les fusionner ensemble ou en amont, 
    
    if len(group)>1:
        # XXX: what to do when group is of len(1) ? lower the threshold / use english vectors, makes it even more complicated
        group = list(group)
        current_max_id,overall_edited_notes,GROUPS = update_notes_in_group(col, group_name, group_separator, current_max_id, overall_edited_notes, group,GROUPS,tag)
    return current_max_id,overall_edited_notes,GROUPS


def download_spacy_model(model_name):
    try:
        # Run the command to download the spaCy model
        result = subprocess.run(['python', '-m', 'spacy', 'download', model_name], check=True, capture_output=True, text=True)
        print(f"Model {model_name} downloaded successfully.")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while downloading the model: {e.stderr}")

def main(groups_file, col, tag, hint_field, group_name, main_signification_field, original_type_name, group_separator, query,lang="zh"):
    GROUPS = dict(load(open(groups_file, 'rb'))) if path.exists(groups_file) else dict()
    current_max_id = get_last_id(col,
                                original_type_name,
                                group_name,
                                group_separator= group_separator,
                                GROUPS=GROUPS,
                                main_signification_field=main_signification_field)
    logger.info(f"Max group ID: {current_max_id}")
    overall_edited_notes = set()
    note_field_utils = NoteFieldsUtils(col,original_type_name)

    notesID, _ = get_notes_to_edit(col,original_type_name,query)

    all_deck_notesID,_ = find_notes(
                col,
                query="-is:new", # Notes that are potential synonyms/cognats. We search for those that we already learned
                note_type_name=original_type_name,
                override_confirmation = True,
                verbose=1
            )
    
    # TODO: change get_yaml_value to retrieve all values at once in a method
    try:
        nlp = spacy.load(f'{lang}_core_web_md', exclude=["ner","tagger","parser","senter","attribute_ruler"])
    except OSError:
        download_spacy_model(f'{lang}_core_web_md')
        nlp = spacy.load(f'{lang}_core_web_md', exclude=["ner","tagger","parser","senter","attribute_ruler"])
    logger.info("Model loaded.")

    all_vectors = get_vector_of_notes(nlp,col,all_deck_notesID,note_field_utils)
    vector_len = len(get_word_vector(nlp,col.get_note(all_deck_notesID[0])[main_signification_field]))
    annoy_index = build_index(vector_len=vector_len,all_vectors=all_vectors)

    for noteID in notesID:
        note = col.get_note(noteID)
        logger.info("Finding synonyms/cognats for " + note[main_signification_field])

        if noteID in overall_edited_notes:
            logger.info("The note was already found in a group.")
            # TODO: calculate the average or max or other stat of the distance of words in all the groups   
            current_max_id,overall_edited_notes,GROUPS = find_new_groups(col,GROUPS,noteID,current_max_id,annoy_index,overall_edited_notes,all_deck_notesID,tag=tag)
        
        # It's a group that I created manually : just need to find the other notes in the group and create the group ID
        elif note[hint_field] and not note[group_name]:
            hints = note[hint_field].split()
            field_text = note_field_utils.extract_text_from_field(note,hint_field)
            match original_type_name:
                # TODO: make it more flexible
                case "Chinois":
                    # Find the notes with the same signification/cognats, id est, that are in the same group 
                    current_max_id = assign_group_id_to_chinese_manual_group(col,GROUPS,noteID,field_text, original_type_name, main_signification_field,current_max_id,overall_edited_notes,tag)

        # It's not in a group yet. I need to find the group using word embeddings
        elif not note[hint_field] :
            current_max_id,overall_edited_notes,GROUPS = find_new_groups(col,GROUPS,noteID,current_max_id,annoy_index,overall_edited_notes,all_deck_notesID,tag=tag)
                

        elif note[hint_field] and note[group_name]:
            # The group ID is already set, all is well
            # TODO: should I remove the is:suspended ect that are in the query ? bc if rerun, they 
            pass
                
        else:
            # What else ?
            breakpoint()
            pass
    
    
    NOTE_GROUPS = defaultdict(lambda: {"text":"","groups":[]})
    for k,v in GROUPS.items():
        for noteID in v:
            NOTE_GROUPS[noteID["id"]]["text"] = noteID["text"]
            NOTE_GROUPS[noteID["id"]]["groups"].append(k)
    reversed_assign_group_id(col,group_name,NOTE_GROUPS, group_separator = ", ",tag="auto_edited")

    logger.success("Done!")

    
    now = datetime.now().strftime('%Y%m%d-%H-%M')
    with open(f"{now}_{groups_file.split('.json')[0]}.json", 'w',encoding="utf-8") as f:
        dump(GROUPS, f,ensure_ascii=False)
    with open(f"{now}_{groups_file.split('.json')[0]}_noteview.json", 'w',encoding="utf-8") as f:
        dump(NOTE_GROUPS, f,ensure_ascii=False)

        #         case "Allemand":
        #             lines = field_text.splitlines()
        #             group_elements = [line for line in lines if detect(line) == 'de']
        
    col.close()

if __name__ == "__main__":

    yaml_file = "src/config.yaml"

    # TODO: Load file name given by user as args
    groups_file = "groups_ch_syn.json"

    COL_PATH = get_col_path(yaml_file)
    col = Collection(COL_PATH)

    tag = "syn_created"  # Flags might have been better, but needs to get to the note cards
    hint_field = "Synonyms"
    group_name = f"{hint_field} group"
    main_signification_field = "Simplified"
    # translation_field = "Meaning"
    original_type_name = "Chinois"
    group_separator = ", "
    query = f'-is:new -is:suspended tag:marked -tag:{tag}'
    main(groups_file, col, tag, hint_field, group_name, main_signification_field, original_type_name, group_separator, query)