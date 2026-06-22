import csv
from typing import Dict, List, Optional
from src.core.models import VocabNote
from src.adapters.base import VocabularyRepository


class CSVVocabularyRepository(VocabularyRepository):
    """CSV-specific adapter mapping CSV rows to core VocabNote domain models.
    
    This enables offline processing of vocab sheets completely independent of Anki.
    """

    def __init__(
        self,
        csv_path: str,
        field_mapping: Dict[str, str],
        delimiter: str = ",",
        group_separator: str = ", "
    ):
        """
        Args:
            csv_path: Path to the CSV file
            field_mapping: Map from domain attributes to CSV column header names.
                Required keys: "word", "meaning", "sorting_value", "hint_field_value", "group_ids"
            delimiter: Column separator (e.g., "," or "\t")
            group_separator: Separator used for multiple group IDs (default: ", ")
        """
        self.csv_path = csv_path
        self.field_mapping = field_mapping
        self.delimiter = delimiter
        self.group_separator = group_separator
        self.headers: List[str] = []
        self._notes: List[VocabNote] = []
        self._load()

    def _load(self) -> None:
        """Loads notes from the CSV file into memory."""
        try:
            with open(self.csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=self.delimiter)
                self.headers = reader.fieldnames or []
                
                for idx, row in enumerate(reader):
                    note_id = str(idx)
                    
                    # Map row cells to domain
                    word = row.get(self.field_mapping.get("word", ""), "").strip()
                    meaning = row.get(self.field_mapping.get("meaning", ""), "").strip()
                    sorting_value = row.get(self.field_mapping.get("sorting_value", ""), "").strip()
                    hint_field_value = row.get(self.field_mapping.get("hint_field_value", ""), "").strip()
                    
                    # Parse group IDs
                    group_ids_raw = row.get(self.field_mapping.get("group_ids", ""), "")
                    group_ids = []
                    if group_ids_raw.strip():
                        group_ids = [g.strip() for g in group_ids_raw.split(self.group_separator) if g.strip()]

                    # Store entire row in metadata for custom attributes
                    metadata = dict(row)

                    vocab_note = VocabNote(
                        id=note_id,
                        word=word,
                        meaning=meaning,
                        sorting_value=sorting_value,
                        hint_field_value=hint_field_value,
                        group_ids=group_ids,
                        metadata=metadata
                    )
                    self._notes.append(vocab_note)
        except FileNotFoundError:
            # If file doesn't exist, we start with an empty sheet
            self._notes = []

    def find_notes(self, query: str) -> List[VocabNote]:
        """Finds matching notes. If query is empty or '*', returns all notes.
        
        Supports basic word search matching.
        """
        if not query or query == "*":
            return self._notes

        query_lower = query.lower()
        results = []
        for note in self._notes:
            if query_lower in note.word.lower() or query_lower in note.meaning.lower():
                results.append(note)
        return results

    def get_note(self, note_id: str) -> Optional[VocabNote]:
        """Retrieves a single vocabulary note by its row index."""
        try:
            idx = int(note_id)
            if 0 <= idx < len(self._notes):
                return self._notes[idx]
        except ValueError:
            pass
        return None

    def update_notes(self, notes: List[VocabNote]) -> None:
        """Updates modified notes in memory."""
        for updated_note in notes:
            for i, note in enumerate(self._notes):
                if note.id == updated_note.id:
                    self._notes[i] = updated_note
                    break

    def close(self) -> None:
        """Writes the in-memory notes back to the CSV file."""
        if not self.headers:
            # Default headers based on field mappings if file was initially empty
            self.headers = list(self.field_mapping.values())

        with open(self.csv_path, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.headers, delimiter=self.delimiter)
            writer.writeheader()
            
            for note in self._notes:
                row = dict(note.metadata)
                
                # Sync mapped values back into CSV row dict
                word_col = self.field_mapping.get("word")
                meaning_col = self.field_mapping.get("meaning")
                sorting_col = self.field_mapping.get("sorting_value")
                hint_col = self.field_mapping.get("hint_field_value")
                group_col = self.field_mapping.get("group_ids")

                if word_col:
                    row[word_col] = note.word
                if meaning_col:
                    row[meaning_col] = note.meaning
                if sorting_col:
                    row[sorting_col] = note.sorting_value
                if hint_col:
                    row[hint_col] = note.hint_field_value
                if group_col:
                    row[group_col] = self.group_separator.join(note.group_ids)
                
                writer.writerow(row)
