# Extract Hardcoded Parameters into Configuration Files — Walkthrough

We have successfully extracted the hardcoded parameters from the CLI layers of the application into clean, dynamic config profiles inside `src/config.yaml`. 

This enables the application to seamlessly support new languages and customized notetypes without altering any Python code!

---

## What Was Done

1. **Parameter & Type Extraction**:
   - Refactored `get_hint_params` inside `src/cli/run_hints.py` to fetch from `config["notetypes"]` dynamically.
   - Built mappings `SORTING_KEYS_MAP` and `ADDITIONAL_HINT_FUNCS_MAP` to cleanly map configuration strings like `"romanic"` to corresponding Python function callables.
   - Dynamic template fields are fully supported (e.g., `hint_field_template.format(hint_type=hint_type)`).

2. **Generic Synonym Extraction CLI**:
   - Added command line flags `--notetype` and `--type` to `src/cli/run_synonyms.py`.
   - Refactored the synonym clustering pipeline to dynamically resolve field mapping parameters, queries, and tag identifiers from the active config profile.

3. **Revamped Cloze to Basic Utility**:
   - Moved the obsolete, hardcoded script `src/cloze2basic_main.py` into a modern dynamic CLI script: `src/cli/run_cloze2basic.py`.
   - Equipped the new CLI tool with robust argparse arguments to override target types, source types, cloze fields, queries, and field extraction mappings.
   - Placed default `cloze2basic` configuration sections inside both `src/config.yaml` and `src/utils/config.py` fallbacks to allow seamless out-of-the-box usage.

4. **Robust Unit Tests**:
   - Added `test_get_hint_params()` inside `tests/test_decoupled_core.py` to ensure proper config resolution and translation of function callables.

---

## Verification Results

### 1. Automated Unit Tests
All 11 unit tests pass flawlessly in WSL:
```bash
wsl /home/kaprime/.local/bin/uv run pytest tests/
======================== 11 passed, 1 warning in 1.32s =========================
```

### 2. Live Chinese Synonym Extraction Run
The updated synonym clustering executed successfully against the unpacked test database:
- Found 280 notes to edit.
- Search space: 4,710 notes.
- Correctly parsed the dynamic `Chinois` profile from YAML.
- Extracted and processed **1,728 updated notes** and saved results to `data/20260622-22-37_groups_ch_syn.json`.

### 3. Live Hint Generation Run
The dynamic hint generator executed successfully:
- Scanned group memberships and parsed profile configuration.
- Prepared 2,223 hints across all active groups.
- Updated **1,816 cards** in the Anki database.
