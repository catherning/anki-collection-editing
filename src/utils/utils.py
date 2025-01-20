import time
import sys

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
  
def is_debug_mode(logger):
    try:
        # Check if a trace function is set
        gettrace = getattr(sys, "gettrace", None)
        if gettrace and gettrace():
            logger.info("Debug mode detected via sys.gettrace")
            return True

        # Check for the presence of debugpy (VS Code debugger)
        import debugpy
        if debugpy.is_client_connected():
            logger.info("Debug mode detected via debugpy")
            return True

    except ImportError:
        logger.info("debugpy not found. Continuing other checks.")

    # No debug mode detected
    logger.info("Running in normal mode")
    return False