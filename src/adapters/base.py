from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.models import VocabNote, SynonymGroup


class VocabularyRepository(ABC):
    """Abstract Base Class (Interface) for Vocabulary Data Repositories.
    
    This abstracts away data storage details (Anki direct DB, CSV, JSON, etc.) 
    from the core business logic.
    """

    @abstractmethod
    def find_notes(self, query: str) -> List[VocabNote]:
        """Finds vocabulary notes matching the specified query or filter."""
        pass

    @abstractmethod
    def get_note(self, note_id: str) -> Optional[VocabNote]:
        """Retrieves a single vocabulary note by its unique identifier."""
        pass

    @abstractmethod
    def update_notes(self, notes: List[VocabNote]) -> None:
        """Saves or updates a list of vocabulary notes in the persistent storage."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Closes any underlying resources (such as database connections or file handles)."""
        pass
