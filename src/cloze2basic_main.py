from typing import Optional

import yaml
from anki.collection import Collection
from loguru import logger

from src.utils.field_utils import add_field
from src.utils.note_utils import find_notes, create_note_type, change_note_type, extract_info_from_cloze_deletion, get_col_path
from src.utils.constants import CLOZE_TYPE, FIELD_WITH_ORIGINAL_CLOZE




if __name__ == "__main__":
    COL_PATH = get_col_path("src/config.yaml")
    
    # TODO: when code is correct, use args instead (don't need to debug)
    new_type_name = "Best Pictures"
    original_type_name = "Cloze"  # "Cloze Music & Sport" # "Olympic winners bis"

    clozes = ["c1", "c2"]
    
    # TODO: make a method for that
    for original_type_name, extra_field in zip(
        ["Cloze",], # "Cloze Music & Sport"], 
        ["Extra",] # "Back Extra"]
    ):
        for movie_cloze in clozes:
            for year_cloze in clozes:
                    if (
                        movie_cloze == year_cloze
                    ):
                        continue

                    logger.info(f"{movie_cloze=} {year_cloze=}")
                    new_fields = [
                        ("Movie winner", movie_cloze),
                        ("Year", year_cloze),
                        ("Extra", extra_field),
                    ]
                    query = f'"Best Picture" re:{year_cloze}::\d{{4}}'
                      # re:c\d.*c\d.*c\d "re:\{\{c2::\d"' 
                    logger.info(f"Anki query: {query}")
                    cloze_text_field = "Text"  # FIELD_WITH_ORIGINAL_CLOZE

                    try:
                        cloze2Basic(
                            COL_PATH, 
                            query=query,
                            new_type_name=new_type_name,
                            new_fields=new_fields,
                            original_type_name=original_type_name,
                            cloze_text_field=cloze_text_field,
                        )
                    except ValueError:
                        continue

# FIXME: needs to have the latest (?) version of Anki GUI.
# Or min the same version as the Anki module used here
# => Either try with older version of Anki library,
# or issues is fixed when having the script as an addon ?
