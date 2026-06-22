# Architectural Revamp Plan: Decoupled Design

This document describes the approved architectural revamp plan for the **Anki Synonym Linking & Hint Generation** tool.

## 1. Problem Statement & Goals

Currently, the core logic for synonym search, vector embedding clustering, and dynamic hint formatting is tightly coupled with Anki's direct SQLite database library (`anki.collection.Collection`). 

This creates several issues:
1. **WSL / Windows SQLite Locking**: Direct database file access gets locked or fails across operating system boundaries.
2. **Hard to Test**: Testing synonym groupings requires opening and writing to a real, unlocked `.anki2` file.
3. **Anki Add-on Portability**: Opening/closing collections inside an active desktop process will crash Anki or lock the database, since Anki already manages the active collection globally.

### Goals of the Revamp:
* **Decouple the Backend Core**: Make core synonym grouping, vector indexing, outlier filtering, and hint formatting completely independent of Anki.
* **Repository Pattern (Adapters)**: Support loading/saving data from any source—live Anki process (Add-on mode), offline Anki DB (CLI mode), plain text CSV spreadsheets, or JSON files.
* **Add-on Portability**: Ensure the code runs flawlessly inside Anki Desktop.

---

## 2. Target Architecture Diagram

```mermaid
graph TD
    subgraph Data Sources / I/O Adapters
        AnkiStandalone["Anki Standalone CLI<br>(Direct SQLite / Collection)"]
        AnkiAddon["Anki Desktop Add-on<br>(Using mw.col inside Anki)"]
        CSVSource["CSV / TSV Files"]
        JSONSource["JSON Vocab Files"]
    end

    subgraph Repository Interface / Adapter Layer
        Repo["VocabularyRepository (Abstract)"]
        AnkiRepo["AnkiVocabularyRepository"]
        CSVRepo["CSVVocabularyRepository"]
        JSONRepo["JSONVocabularyRepository"]
    end

    subgraph Core "Backend" Domain Layer
        NoteModel["VocabNote (Dataclass)"]
        GroupModel["SynonymGroup (Dataclass)"]
        
        SynService["SynonymFinderService<br>(Vector Embeddings, Clustering, Outlier Detection)"]
        HintService["HintGeneratorService<br>(Chronological / Synonym Hint Formatting)"]
    end

    %% Flow of data
    AnkiStandalone --> AnkiRepo
    AnkiAddon --> AnkiRepo
    CSVSource --> CSVRepo
    JSONSource --> JSONRepo

    AnkiRepo --> Repo
    CSVRepo --> Repo
    JSONRepo --> Repo

    Repo -- "Loads/Saves" --> NoteModel
    Repo -- "Loads/Saves" --> GroupModel

    NoteModel & GroupModel --> SynService
    NoteModel & GroupModel --> HintService

    SynService -- "Updates" --> GroupModel
    HintService -- "Generates Hint Strings" --> NoteModel
```

---

## 3. Directory Structure Design

We are restructuring the project's source code inside `src/` to follow a clean, modular layout:

```
src/
├── core/                        # <-- Core Backend Logic (Pure Python, No Anki Dependency)
│   ├── __init__.py
│   ├── models.py                # VocabNote & SynonymGroup Dataclasses
│   ├── synonym_service.py       # ML Clustering, Embedding generation, Outlier removal logic
│   └── hint_service.py          # Dynamic hint text generation/formatting logic
│
├── adapters/                    # <-- Adapters / Repositories (Data Access Layer)
│   ├── __init__.py
│   ├── base.py                  # Abstract base class: VocabularyRepository
│   ├── anki_adapter.py          # Maps Anki Notes <-> VocabNote domain models
│   ├── csv_adapter.py           # Maps CSV rows <-> VocabNote domain models
│   └── json_adapter.py          # Maps JSON dicts <-> VocabNote domain models
│
├── cli/                         # <-- Frontend CLI orchestrating the process
│   ├── __init__.py
│   ├── run_synonyms.py          # Orchestrates synonym finding
│   └── run_hints.py             # Orchestrates hint generation
│
└── utils/                       # <-- General shared utilities
    ├── text_utils.py            # Clean text/HTML extraction (BeautifulSoup parser)
    └── logger.py                # Configuration for Loguru loggers
```

---

## 4. Work Checklist / Implementation Phases

- [x] **Phase 1: Project Initialization & Directory Structure**
  - [x] Create `src/core/` package
  - [x] Create `src/adapters/` package
  - [x] Create `src/cli/` package
  - [/] Move shared utility modules under `src/utils/`

- [/] **Phase 2: Core Domain Model Implementation**
  - [x] Implement `src/core/models.py` (Dataclasses for `VocabNote` and `SynonymGroup`)
  - [x] Refactor HTML/text extraction to `src/utils/text_utils.py` (BeautifulSoup, cloze parsers)
  - [ ] Implement `src/core/hint_service.py` (Decoupled Hint generation)
  - [ ] Implement `src/core/synonym_service.py` (Decoupled Embeddings, Clustering, Outlier removal)

- [ ] **Phase 3: Repository / Adapter Layer**
  - [ ] Implement abstract `VocabularyRepository` in `src/adapters/base.py`
  - [ ] Implement `AnkiVocabularyRepository` in `src/adapters/anki_adapter.py`
  - [ ] Implement `CSVVocabularyRepository` in `src/adapters/csv_adapter.py`
  - [ ] Implement `JSONVocabularyRepository` in `src/adapters/json_adapter.py`

- [ ] **Phase 4: CLI Application / Orchestration**
  - [ ] Create `src/cli/run_synonyms.py` as main synonym tool
  - [ ] Create `src/cli/run_hints.py` as main hint generation tool
  - [ ] Create unified config management `src/utils/config.py`

- [ ] **Phase 5: Testing & Verification**
  - [ ] Create basic mock unit tests under `tests/` for core services
  - [ ] Verify execution using Python CLI commands
