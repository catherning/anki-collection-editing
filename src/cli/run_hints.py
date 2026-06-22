import sys
import argparse
from typing import Dict, List, Optional, Callable
from loguru import logger

from src.utils.config import load_config
from src.core.models import VocabNote
from src.core.hint_service import HintGeneratorService
from src.adapters.anki_adapter import AnkiVocabularyRepository
from src.utils.german_utils import romanic_sorting_key, romanic_additional_hint_func


SORTING_KEYS_MAP = {
    "romanic": romanic_sorting_key
}

ADDITIONAL_HINT_FUNCS_MAP = {
    "romanic": romanic_additional_hint_func
}


def get_hint_params(note_type_name: str, hint_type: str = "Synonyms", config: Optional[dict] = None) -> dict:
    """Returns the custom parameters for hint generation based on the note type."""
    if not config:
        config = load_config()

    profile = config.get("notetypes", {}).get(note_type_name)
    if not profile:
        logger.warning(f"Notetype '{note_type_name}' not found in configuration! Falling back to 'Chinois'.")
        profile = config.get("notetypes", {}).get("Chinois", {})

    # Resolve callables from string values
    sorting_key_name = profile.get("sorting_key")
    additional_hint_func_name = profile.get("additional_hint_func")

    sorting_key = SORTING_KEYS_MAP.get(sorting_key_name) if sorting_key_name else None
    additional_hint_func = ADDITIONAL_HINT_FUNCS_MAP.get(additional_hint_func_name) if additional_hint_func_name else None

    # Interpolate templates
    hint_field_template = profile.get("hint_field_template", "Generated {hint_type}")
    query_field_template = profile.get("query_field_template", "{hint_type} group")

    params = {
        "flds_in_hint": profile.get("flds_in_hint", ["Simplified", "Meaning"]),
        "separator": profile.get("separator", " "),
        "sorting_field": profile.get("sorting_field", "Pinyin.1"),
        "additional_hint_field": profile.get("additional_hint_field", "Pinyin.1"),
        "sorting_key": sorting_key,
        "additional_hint_func": additional_hint_func,
        "hint_field": hint_field_template.format(hint_type=hint_type),
        "query_field": query_field_template.format(hint_type=hint_type),
        "break_lines": profile.get("break_lines", False)
    }

    return params



def main():
    parser = argparse.ArgumentParser(description="Decoupled Anki Hint Generation Tool")
    parser.add_argument("--notetype", type=str, default="Chinois", help="Anki Notetype name (e.g. Chinois, Allemand)")
    parser.add_argument("--type", type=str, default="Synonyms", help="Hint type (e.g. Synonyms, Cognats)")
    parser.add_argument("--no-confirm", action="store_true", help="Skip user confirmation prompt before writing to DB")
    args = parser.parse_args()

    config = load_config()
    
    note_type_name = args.notetype
    hint_type = args.type
    
    logger.info(f"Setting up hint generation for note type: {note_type_name}, type: {hint_type}")
    params = get_hint_params(note_type_name, hint_type, config=config)
    
    # Initialize repository
    field_mapping = {
        "word": params["flds_in_hint"][0],
        "meaning": params["flds_in_hint"][1] if len(params["flds_in_hint"]) > 1 else "",
        "sorting_value": params["sorting_field"],
        "hint_field_value": params["hint_field"],
        "group_ids": params["query_field"]
    }
    
    logger.info(f"Connecting to repository at: {config['collection_path']}")
    repo = AnkiVocabularyRepository(
        col_or_path=config["collection_path"],
        note_type_name=note_type_name,
        field_mapping=field_mapping,
        group_separator=config["group_separator"]
    )
    
    # 1. Gather all notes that belong to any group to extract present group IDs
    logger.info("Scanning repository to find all grouped notes...")
    # Find notes where group_ids is not empty
    all_notes = repo.find_notes(f'"{params["query_field"]}:*"')
    
    # Collect all unique group IDs
    group_ids = set()
    for note in all_notes:
        for g_id in note.group_ids:
            if g_id.strip():
                group_ids.add(g_id.strip())
                
    sorted_group_ids = sorted(list(group_ids), key=lambda x: int(x) if x.isdigit() else 9999)
    logger.info(f"Found {len(sorted_group_ids)} unique group IDs: {sorted_group_ids}")
    
    if not sorted_group_ids:
        logger.warning("No groups found. Please run the synonym clustering tool first!")
        sys.exit(0)

    hint_service = HintGeneratorService()
    notes_to_update: List[VocabNote] = []

    # 2. Iterate over each group ID and generate/adapt hints
    for g_id in sorted_group_ids:
        logger.info(f"Generating hints for group ID: {g_id}")
        
        # Find all notes in this specific group
        # Query like: "Synonyms group:re:(^|, )1(, |$)"
        group_query = f'"{params["query_field"]}:re:(^|{config["group_separator"]}){g_id}({config["group_separator"]}|$)"'
        group_notes = repo.find_notes(group_query)
        
        if len(group_notes) < 2:
            logger.debug(f"Group {g_id} has fewer than 2 notes. Skipping hint generation.")
            continue
            
        # Generate hints for this group
        updated_hints = hint_service.generate_hints_for_group(
            notes=group_notes,
            flds_in_hint=params["flds_in_hint"],
            sorting_field=params["sorting_field"],
            sorting_key=params["sorting_key"],
            separator=params["separator"],
            additional_hint_field=params["additional_hint_field"],
            additional_hint_func=params["additional_hint_func"],
            break_lines=params["break_lines"],
            replace_existing=True,  # Overwrite existing hints with newly generated
            group_separator=config["group_separator"],
            current_group_id=g_id
        )
        
        # Add updated notes to save queue
        notes_to_update.extend(group_notes)

    if notes_to_update:
        logger.info(f"Prepared {len(notes_to_update)} updated hints across all groups.")
        
        # Filter duplicates in queue
        save_map = {n.id: n for n in notes_to_update}
        unique_save_list = list(save_map.values())
        
        confirm = True
        if not args.no_confirm:
            logger.info("Do you want to write these hints to the Anki collection? (y/N)")
            response = input().strip().lower()
            confirm = (response == "y")
            
        if confirm:
            logger.info(f"Writing {len(unique_save_list)} notes to collection...")
            repo.update_notes(unique_save_list)
            logger.success("Hints successfully written to the collection!")
        else:
            logger.warning("Aborted writing to collection.")
    else:
        logger.warning("No hints were generated.")

    repo.close()
    logger.info("Hint generation completed successfully!")


if __name__ == "__main__":
    main()
