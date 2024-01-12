# from datetime import datetime
from anki.collection import Collection
from src.utils.german_utils import romanic_additional_hint_func, romanic_sorting_key

from src.utils.hint_generation_utils import HintAdaptor
from src.utils.note_utils import get_col_path

# TODO: make as arg


if __name__ == "__main__":
    COL_PATH = get_col_path("src/config.yaml")
    if 'col' not in globals():
        col = Collection(COL_PATH)
    
    for note_type_name in ["Best Pictures"]: #"Chinois","Allemand"]:
        break_lines = False

        cloze_field = ""  # "Text"
        group_separator = ", "
        query_field = "Year"

        match note_type_name:
            case "Chinois":
                flds_in_hint = ["Simplified", "Meaning"]
                separator = " "
                sorting_field = additional_hint_field = "Pinyin.1"
                sorting_key = None
                additional_hint_func = None

            case "Allemand":
                sorting_key = romanic_sorting_key
                additional_hint_func = romanic_additional_hint_func
                         
                flds_in_hint = ["German", "French/English"]
                separator = " | "  # should add spaces
                sorting_field = additional_hint_field = "German"
        
            case "Best Pictures":
                sorting_key = None
                additional_hint_func = None
                flds_in_hint = ["Year", "Movie winner"]
                separator = " "
                sorting_field = "Year"
                additional_hint_field = "Movie winner"
                hint_field = "Extra"
                
        # TODO: check if HintGenerator is ok
        hint_adaptor = HintAdaptor(
            flds_in_hint,
            col = col,
            hint_holding_field = hint_field,
            sorting_field = sorting_field,
            sorting_key = sorting_key,
            separator = separator,
            group_separator = group_separator,
            additional_hint_field = additional_hint_field,
            additional_hint_func = additional_hint_func,
            replace = True,
            query_field = query_field,
            break_lines = break_lines,
        )

        for cent in ["19","20"]:
            for i in range(10):
                query = f'{query_field}:{cent}{i}*'
                try:

                    hint_adaptor.run(note_type_name,
                                     query,)
                except ValueError as e:
                    print(query, e)
                    continue

                

        # for hint_field in ["Synonyms","Cognats"]:
        #     query_field = f"{hint_field} group"
                
        #     # Itère sur query : chiffre par chiffre. Si retrouve une carte, doit append le hint, pas remplacer
        #     i=0
        #     while True:
        #         i+=1
        #         query = f'"{query_field}:re:(^|{group_separator}){i}({group_separator}|$)"'
                
        #         try:
        #             generate_hint_main(
        #                 COL_PATH,
        #                 note_type_name,
        #                 query,
        #                 flds_in_hint,
        #                 hint_field,
        #                 additional_hint_field,
        #                 additional_hint_func,
        #                 sorting_key,
        #                 sorting_field,
        #                 separator=separator,
        #                 break_lines=break_lines,
        #                 # cloze_field=cloze_field,
        #                 replace = True,
        #                 query_field = query_field,
        #                 group_separator = group_separator
        #             )
        #         except ValueError as e:
        #             print(query, e)
        #             break
