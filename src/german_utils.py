import yaml
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize


config = yaml.load(open("src/config.yaml"))
COL_PATH = config["collection_path"]
# import icu
# collator = icu.Collator.createInstance()

try:
    stop_words = set(stopwords.words('german'))
except LookupError:
    nltk.download('stopwords')
    stop_words = set(stopwords.words('german'))

stop_words.update(("e","r","s"))

def get_main_words(text):
    word_tokens = word_tokenize(text)
    return iter(w for w in word_tokens if w.lower() not in stop_words)
        
def romanic_sorting_key(hint_info):
    return " ".join(get_main_words(hint_info[1]))

def romanic_additional_hint_func(text):
    """Get the first letter of the main info (ex: for das Mädchen -> M, not d)"""
    return next(get_main_words(text))[0]
