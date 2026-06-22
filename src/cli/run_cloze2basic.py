import sys
import argparse
from loguru import logger
from src.utils.config import load_config
from src.utils.note_utils import NoteConverter

def main():
    parser = argparse.ArgumentParser(description="Decoupled Anki Cloze to Basic Conversion Tool")
    parser.add_argument("--new-type-name", "-n", type=str, default=None, help="Name of the new basic note type")
    parser.add_argument("--original-type-name", "-o", type=str, default=None, help="Name of the original cloze note type")
    parser.add_argument("--cloze-text-field", "-f", type=str, default=None, help="Field containing cloze text")
    parser.add_argument("--query", "-q", type=str, default=None, help="Anki search query")
    parser.add_argument("--mappings", "-m", type=str, nargs="+", default=None, 
                        help="Field mapping format as NewField:OldFieldOrCloze (e.g. Album:c1 Year:c2 Extra:Extra)")
    
    args = parser.parse_args()
    
    config = load_config()
    cloze2basic_conf = config.get("cloze2basic", {})
    
    new_type_name = args.new_type_name or cloze2basic_conf.get("new_type_name", "Music")
    original_type_name = args.original_type_name or cloze2basic_conf.get("original_type_name", "Cloze")
    cloze_text_field = args.cloze_text_field or cloze2basic_conf.get("cloze_text_field", "Text")
    query = args.query or cloze2basic_conf.get("query", "Krzysztof")
    
    # Resolve mappings list of tuples
    new_fields = []
    mappings_raw = args.mappings
    if mappings_raw is None:
        mappings_raw = cloze2basic_conf.get("mappings", ["Album:c1", "Year:c2", "Group:c3", "Extra:Extra"])
        
    for item in mappings_raw:
        if ":" in item:
            new_f, old_f = item.split(":", 1)
            new_fields.append((new_f.strip(), old_f.strip()))
        else:
            logger.warning(f"Invalid mapping format '{item}'. Expected 'NewField:OldField'. Skipping.")

    logger.info(f"Setting up Cloze to Basic conversion...")
    logger.info(f"Target Basic Notetype: {new_type_name}")
    logger.info(f"Source Cloze Notetype: {original_type_name}")
    logger.info(f"Cloze text field:      {cloze_text_field}")
    logger.info(f"Search Query:          {query}")
    logger.info(f"Field Mappings:        {new_fields}")

    note_converter = NoteConverter(
        config_path="src/config.yaml",
        new_note_name=new_type_name,
        new_fields=new_fields,
        original_type_name=original_type_name,
        cloze_text_field=cloze_text_field,
    )
    
    try:
        note_converter.run_cloze2Basic(query=query)
    except ValueError as e:
        logger.error(f"Conversion failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
