import os
import re
import json
import uuid
import argparse
from typing import Dict
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from loguru import logger

from src.utils.config import load_config
from src.core.models import VocabNote, SynonymGroup
from src.core.synonym_service import SynonymFinderService
from src.adapters.anki_adapter import AnkiVocabularyRepository


def load_groups_from_json(groups_file_path: Path) -> Dict[str, SynonymGroup]:
    """Loads existing synonym groups from a JSON file."""
    groups = {}
    if not groups_file_path.exists():
        return groups

    try:
        with open(groups_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for g_id, g_info in data.items():
                unique_id = g_info.get("unique_id", uuid.uuid4().int)
                notes_data = g_info.get("notes", [])
                
                # Reconstruct SynonymGroup
                vocab_notes = []
                for n_data in notes_data:
                    n_id = str(n_data["id"])
                    n_word = n_data["text"]
                    vocab_notes.append(VocabNote(id=n_id, word=n_word, meaning=""))
                
                groups[g_id] = SynonymGroup(
                    group_id=g_id,
                    unique_id=unique_id,
                    notes=vocab_notes
                )
    except Exception as e:
        logger.error(f"Error loading groups file: {e}")
    
    return groups


def main():
    parser = argparse.ArgumentParser(description="Decoupled Anki Synonym Extraction & Clustering Tool")
    parser.add_argument("--notetype", type=str, default=None, help="Anki Notetype name (e.g. Chinois, Allemand)")
    parser.add_argument("--type", type=str, default="Synonyms", help="Hint type (e.g. Synonyms, Cognats)")
    args = parser.parse_args()

    config = load_config()
    
    note_type_name = args.notetype or config.get("original_type_name", "Chinois")
    hint_type = args.type

    logger.info(f"Setting up synonym clustering for note type: {note_type_name}, type: {hint_type}")

    # Load note-type profile
    profile = config.get("notetypes", {}).get(note_type_name)
    if not profile:
        logger.warning(f"Notetype '{note_type_name}' not found in configuration! Falling back to 'Chinois'.")
        profile = config.get("notetypes", {}).get("Chinois", {})

    groups_file_conf = Path(config["groups_file"])
    groups_dir = groups_file_conf.parent
    groups_dir.mkdir(exist_ok=True, parents=True)
    
    # Locate latest groups file
    json_files = [groups_dir / f for f in os.listdir(groups_dir) if f.endswith(".json") and "noteview" not in f]
    groups_file = max(json_files, key=os.path.getmtime) if json_files else groups_file_conf
    
    logger.info(f"Loading existing groups from: {groups_file}")
    existing_groups = load_groups_from_json(groups_file)
    
    # Initialize repository field mapping
    flds_in_hint = profile.get("flds_in_hint", ["Simplified", "Meaning"])
    word_field = flds_in_hint[0] if len(flds_in_hint) > 0 else "Simplified"
    meaning_field = flds_in_hint[1] if len(flds_in_hint) > 1 else "Meaning"
    
    sorting_field = profile.get("sorting_field", "Pinyin.1")
    
    hint_field_template = profile.get("hint_field_template", "Generated {hint_type}")
    query_field_template = profile.get("query_field_template", "{hint_type} group")
    
    hint_field_value = hint_field_template.format(hint_type=hint_type)
    group_ids_field = query_field_template.format(hint_type=hint_type)

    manual_synonym_field = profile.get("manual_synonym_field") or config.get("hint_field", "Synonyms")
    tag_value = profile.get("tag") or config.get("tag", "syn_created")
    
    field_mapping = {
        "word": word_field,
        "meaning": meaning_field,
        "sorting_value": sorting_field,
        "hint_field_value": hint_field_value,
        "group_ids": group_ids_field
    }
    
    logger.info(f"Connecting to Anki DB at: {config['collection_path']}")
    repo = AnkiVocabularyRepository(
        col_or_path=config["collection_path"],
        note_type_name=note_type_name,
        field_mapping=field_mapping,
        group_separator=config["group_separator"]
    )
    
    # Determine max group ID
    if existing_groups:
        current_max_id = max([int(g_id) for g_id in existing_groups.keys() if g_id.isdigit()], default=0)
    else:
        current_max_id = 0
    logger.info(f"Current max group ID from JSON: {current_max_id}")
    
    # Queries
    query_val = profile.get("query") or config.get("query", "-is:new -is:suspended tag:marked -tag:syn_created")
    search_space_query_val = profile.get("search_space_query") or config.get("search_space_query", "-is:new")

    # Find notes to edit
    logger.info(f"Finding notes to edit with query: {query_val}")
    notes_to_edit = repo.find_notes(query_val)
    logger.info(f"Found {len(notes_to_edit)} notes to edit.")
    
    # Find all search space notes
    logger.info(f"Finding search space notes with query: {search_space_query_val}")
    all_deck_notes = repo.find_notes(search_space_query_val)
    logger.info(f"Total search space size: {len(all_deck_notes)} notes.")
    
    # Setup lookup mappings
    word_to_notes = defaultdict(list)
    for note in all_deck_notes:
        word_to_notes[note.word].append(note)
        
    note_id_to_note = {note.id: note for note in all_deck_notes}
    
    # Fill loaded group's note references with the full rich VocabNotes from DB
    for g_id, group in list(existing_groups.items()):
        rich_notes = []
        for dummy_note in group.notes:
            if dummy_note.id in note_id_to_note:
                rich_note = note_id_to_note[dummy_note.id]
                rich_notes.append(rich_note)
                # Ensure note object knows its loaded group IDs
                rich_note.add_to_group(g_id, group.unique_id)
            else:
                rich_notes.append(dummy_note)
        group.notes = rich_notes

    # Create active SynonymFinderService
    service = SynonymFinderService(
        vector_search_lib=config["lib"],
        model_name=config["model"],
        lang=config["lang"]
    )
    
    annoy_index = None
    if config["vector_search"] and all_deck_notes:
        logger.info("Generating embeddings and building Annoy index...")
        vectors = service.get_vectors_of_notes(all_deck_notes)
        annoy_index = service.build_annoy_index(vectors)
        logger.info("Annoy index built.")

    overall_edited_notes = set()
    
    for note in notes_to_edit:
        # Avoid processing same note multiple times in a single run
        if note.id in overall_edited_notes:
            if config["vector_search"] and annoy_index:
                logger.warning(f"Note '{note.word}' was already grouped. Searching next nearest synonyms.")
                current_max_id, existing_groups = service.find_new_groups_from_embedding(
                    target_note=note,
                    all_notes=all_deck_notes,
                    annoy_index=annoy_index,
                    groups=existing_groups,
                    overall_edited_notes=overall_edited_notes,
                    current_max_id=current_max_id
                )
            continue

        manual_hints_raw = note.metadata.get(manual_synonym_field, "")
        
        # Scenario 1: Note has manually written synonyms but no group ID assigned yet
        if manual_hints_raw and not note.group_ids:
            logger.info(f"Assigning group ID for manually defined synonyms of: '{note.word}'")
            
            # Find all Chinese characters (words) in the field
            group_elements = re.findall("[\u4e00-\u9FFF]+|\n", manual_hints_raw)
            groups_found = [[note]]
            
            for el in group_elements:
                if el == "\n":
                    groups_found.append([note])
                else:
                    found_notes = word_to_notes.get(el, [])
                    if len(found_notes) == 1:
                        groups_found[-1].append(found_notes[0])
                    elif len(found_notes) > 1:
                        # Fallback: add first matched note
                        groups_found[-1].append(found_notes[0])
                        
            for g_notes in groups_found:
                if len(g_notes) > 1:
                    current_max_id += 1
                    new_id = str(current_max_id)
                    unique_uid = uuid.uuid4().int
                    
                    new_group = SynonymGroup(
                        group_id=new_id,
                        unique_id=unique_uid,
                        notes=g_notes
                    )
                    
                    for n in g_notes:
                        n.add_to_group(new_id, unique_uid)
                        overall_edited_notes.add(n.id)
                        
                    existing_groups[new_id] = new_group

        # Scenario 2: Note has no manual hints, no group ID, and vector search is enabled
        elif not manual_hints_raw and not note.group_ids and config["vector_search"] and annoy_index:
            logger.info(f"Finding vector-similarity synonyms for: '{note.word}'")
            current_max_id, existing_groups = service.find_new_groups_from_embedding(
                target_note=note,
                all_notes=all_deck_notes,
                annoy_index=annoy_index,
                groups=existing_groups,
                overall_edited_notes=overall_edited_notes,
                current_max_id=current_max_id
            )
            
        elif note.group_ids:
            logger.info(f"'{note.word}' is already in a group: {note.group_ids}")

    # Post-processing: remove outliers from large groups and merge overlaps
    if config["vector_search"] and annoy_index:
        logger.info("Filtering outliers using median/IQR distance metric...")
        existing_groups = service.remove_group_outliers(annoy_index, all_deck_notes, existing_groups)
        
    logger.info("Merging overlapping groups...")
    existing_groups = service.merge_groups(existing_groups)

    # Reconstruct inverse NOTE_GROUPS lookup mapping
    note_groups_map = defaultdict(lambda: {"text": "", "groups": []})
    for g_id, group in existing_groups.items():
        for n in group.notes:
            note_groups_map[n.id]["text"] = n.word
            note_groups_map[n.id]["groups"].append((g_id, group.unique_id))

    # Apply tag and update repository
    notes_to_save = []
    for note_id, mapping in note_groups_map.items():
        vocab_note = note_id_to_note.get(note_id)
        if vocab_note:
            # Reconstruct group string value
            vocab_note.group_ids = [str(g[0]) for g in mapping["groups"]]
            
            # Add tag in metadata
            tags = list(vocab_note.metadata.get("_anki_tags", []))
            if tag_value not in tags:
                tags.append(tag_value)
            vocab_note.metadata["_anki_tags"] = tags
            
            notes_to_save.append(vocab_note)

    logger.info(f"Saving {len(notes_to_save)} updated notes to repository...")
    repo.update_notes(notes_to_save)
    
    # Save group views to JSON
    now = datetime.now().strftime("%Y%m%d-%H-%M")
    base_fn = f"{now}_{Path(config['groups_file']).stem}"
    
    groups_out_path = groups_dir / f"{base_fn}.json"
    notes_out_path = groups_dir / f"{base_fn}_noteview.json"
    
    logger.info(f"Saving serialized groups to: {groups_out_path}")
    
    # Serialize GROUPS
    serialized_groups = {}
    for g_id, group in existing_groups.items():
        serialized_groups[g_id] = {
            "unique_id": group.unique_id,
            "notes": [{"id": int(n.id) if n.id.isdigit() else n.id, "text": n.word} for n in group.notes]
        }
        
    with open(groups_out_path, "w", encoding="utf-8") as f:
        json.dump(serialized_groups, f, ensure_ascii=False, indent=2)
        
    with open(notes_out_path, "w", encoding="utf-8") as f:
        json.dump(dict(note_groups_map), f, ensure_ascii=False, indent=2)

    repo.close()
    logger.info("Synonym clustering orchestration completed successfully!")


if __name__ == "__main__":
    main()
