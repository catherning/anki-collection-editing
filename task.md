# Task List: Extract hardcoded parameters into YAML configuration

- [x] **Phase 1: Refactor CLI run_hints.py**
  - [x] Implement string-to-callable maps for custom sorting/helpers
  - [x] Replace hardcoded `get_hint_params` with dynamic config lookups
  - [x] Support custom templates for fields with format interpolation

- [x] **Phase 2: Refactor CLI run_synonyms.py**
  - [x] Add command-line arguments `--notetype` and `--type` to synonym CLI
  - [x] Replace hardcoded field mapping with dynamic config lookups based on note type profile
  - [x] Use configurable tags and query fields from profile templates

- [x] **Phase 3: Revamp Cloze to Basic Utility**
  - [x] Create dynamic `src/cli/run_cloze2basic.py` CLI script supporting arguments and dynamic mappings
  - [x] Add dynamic `cloze2basic` configurations block to `src/config.yaml`
  - [x] Add fallback default values in `src/utils/config.py`
  - [x] Remove obsolete `src/cloze2basic_main.py` file

- [x] **Phase 4: Testing & Verification**
  - [x] Run full pytest suite under WSL
  - [x] Run synonyms and hints generation CLIs on German/Allemand or Chinois to verify compatibility and correct execution
  - [x] Generate final walkthrough documentation
