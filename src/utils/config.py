import os
import yaml
from pathlib import Path


def load_config(config_path: str = "src/config.yaml") -> dict:
    """Loads configuration settings from a YAML file with sensible defaults."""
    project_root = Path(__file__).resolve().parent.parent.parent
    
    # Resolve config path relative to project root
    abs_config_path = project_root / config_path

    default_config = {
        "collection_path": "data/collection.anki2",
        "groups_file": "data/groups_ch_syn.json",
        "tag": "syn_created",
        "hint_field": "Synonyms",
        "group_name": "Synonyms group",
        "main_signification_field": "Simplified",
        "original_type_name": "Chinois",
        "group_separator": ", ",
        "query": "-is:new -is:suspended tag:marked -tag:syn_created",
        "search_space_query": "-is:new",
        "vector_search": True,
        "lib": "sentence_transformer",
        "model": "BAAI/bge-small-zh-v1.5",
        "lang": "zh",
        "notetypes": {
            "Chinois": {
                "flds_in_hint": ["Simplified", "Meaning"],
                "separator": " ",
                "sorting_field": "Pinyin.1",
                "additional_hint_field": "Pinyin.1",
                "hint_field_template": "Generated {hint_type}",
                "query_field_template": "{hint_type} group",
                "break_lines": False,
                "sorting_key": None,
                "additional_hint_func": None
            },
            "Allemand": {
                "flds_in_hint": ["German", "French/English"],
                "separator": " | ",
                "sorting_field": "German",
                "additional_hint_field": "German",
                "hint_field_template": "Generated {hint_type}",
                "query_field_template": "{hint_type} group",
                "break_lines": False,
                "sorting_key": "romanic",
                "additional_hint_func": "romanic"
            },
            "Best Pictures": {
                "flds_in_hint": ["Year", "Movie winner"],
                "separator": " ",
                "sorting_field": "Year",
                "additional_hint_field": None,
                "hint_field_template": "Extra",
                "query_field_template": "Year",
                "break_lines": True,
                "sorting_key": None,
                "additional_hint_func": None
            },
            "Music": {
                "flds_in_hint": ["Year", "Album"],
                "separator": " ",
                "sorting_field": "Year",
                "additional_hint_field": None,
                "hint_field_template": "Extra",
                "query_field_template": "Year",
                "break_lines": True,
                "sorting_key": None,
                "additional_hint_func": None
            }
        },
        "cloze2basic": {
            "new_type_name": "Music",
            "original_type_name": "Cloze",
            "cloze_text_field": "Text",
            "query": "Krzysztof",
            "mappings": [
                "Album:c1",
                "Year:c2",
                "Group:c3",
                "Extra:Extra"
            ]
        }
    }

    if abs_config_path.exists():
        try:
            with open(abs_config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if loaded and isinstance(loaded, dict):
                    default_config.update(loaded)
        except Exception:
            pass

    # Resolve any relative paths in config to be absolute paths relative to project root
    for key in ["collection_path", "groups_file"]:
        path_val = default_config[key]
        if path_val and not os.path.isabs(path_val):
            default_config[key] = str((project_root / path_val).resolve())

    # Clean collection path suffix
    col_path = default_config["collection_path"]
    if col_path and not col_path.endswith(".anki2"):
        default_config["collection_path"] = str(Path(col_path) / "collection.anki2")

    return default_config
