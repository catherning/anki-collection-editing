from loguru import logger
from src.utils.note_utils import NoteConverter


if __name__ == "__main__":
    # TODO: when code is correct, use args instead (don't need to debug)
    new_type_name = "Music"

    clozes = ["c1", "c2", "c3"]
    cloze_text_field = "Text"  # FIELD_WITH_ORIGINAL_CLOZE
    query = f'Krzysztof'
    
    # TODO: make a method for that?
    for original_type_name, extra_field in zip(
        ["Cloze",], # "Cloze Music & Sport"], 
        ["Extra",] # "Back Extra"]
    ):
        for song_cloze in ["c1"]:#clozes:
            for year_cloze in ["c2"]:#clozes:
                    if (
                        song_cloze == year_cloze
                    ):
                        continue

                    logger.info(f"{song_cloze=} {year_cloze=}")
                    new_fields = [
                        ("Album", song_cloze),
                        ("Year", year_cloze),
                        ("Group","c3"),
                        ("Extra", extra_field),
                    ]

                      # re:c\d.*c\d.*c\d "re:\{\{c2::\d"' 
                    logger.info(f"Anki query: {query}")
                    
                    note_converter = NoteConverter("config.yaml",
                                                    new_type_name,
                                                    new_fields,
                                                    original_type_name,
                                                    cloze_text_field,
                                    )
                    try:
                        note_converter.run_cloze2Basic(
                            query=query)
                    except ValueError:
                        continue

# FIXME: needs to have the latest (?) version of Anki GUI.
# Or min the same version as the Anki module used here
# => Either try with older version of Anki library,
# or issues is fixed when having the script as an addon ?
