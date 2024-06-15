import time

CLOZE_TYPE = 1
FIELD_WITH_ORIGINAL_CLOZE = "Original cloze text"

def timeit(f):

    def timed(*args, **kw):

        ts = time.time()
        result = f(*args, **kw)
        te = time.time()

        print ("func:%r took: %2.4f sec" % \
          (f.__name__, te-ts))
        return result

    return timed