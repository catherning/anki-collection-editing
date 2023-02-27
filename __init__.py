from anki_utils import COL_PATH

# from ankipandas import Collection, set_debug_log_level
# set_debug_log_level()

from anki.collection import Collection

col = Collection(COL_PATH)

print(col)