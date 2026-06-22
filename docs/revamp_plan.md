# Architectural Revamp Plan: Decoupled Design

This document archives the approved architectural revamp plan for the **Anki Synonym Linking & Hint Generation** tool.

## Target Architecture

The goal of this revamp is to separate the **core backend logic** (finding synonyms via embeddings, clustering notes, dynamic hint generation formatting) from the **frontend / storage engines** (direct Anki collection manipulation, CSV loading, or JSON processing).

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

## Directory Structure Design

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

## Implementation Phases

1. **Phase 1: Project Initialization & Directory Structure**: Setup the new folders and python package files (`__init__.py`).
2. **Phase 2: Core Domain Models & Services**: Implement `models.py`, `synonym_service.py`, `hint_service.py`, and `text_utils.py`.
3. **Phase 3: Repository Pattern & Adapters**: Implement abstract `VocabularyRepository`, concrete `AnkiVocabularyRepository`, `CSVVocabularyRepository`, and `JSONVocabularyRepository`.
4. **Phase 4: CLI Application layer**: Create main executable drivers `run_synonyms.py` and `run_hints.py`.
5. **Phase 5: Automated Testing**: Write unit tests for core services to ensure accuracy and prevent regression.
