import json
from typing import Dict, List, Optional
from src.core.models import VocabNote
from src.adapters.base import VocabularyRepository


class JSONVocabularyRepository(VocabularyRepository):
    """JSON-specific adapter mapping JSON records to core VocabNote domain models."""

    def __init__(
        self,
        json_path: str,
        field_mapping: Dict[str, str],
        group_separator: str = ", "
    ):
        """
        Args:
            json_path: Path to the JSON file
            field_mapping: Map from domain attributes to JSON keys.
                Required keys: "word", "meaning", "sorting_value", "hint_field_value", "group_ids"
            group_separator: Separator used for multiple group IDs (default: ", ")
        """
        self.json_path = json_path
        self.field_mapping = field_mapping
        self.group_separator = group_separator
        self._notes: List[VocabNote] = []
        self._load()

    def _load(self) -> None:
        """Loads notes from the JSON file into memory."""
        try:
            with open(self.json_path, mode="r", encoding="utf-8") as f:
                records = json.load(f)
                if not isinstance(records, list):
                    records = []
                
                for idx, record in enumerate(records):
                    note_id = record.get("id", str(idx))
                    
                    # Map JSON fields to domain
                    word = record.get(self.field_mapping.get("word", ""), "").strip()
                    meaning = record.get(self.field_mapping.get("meaning", ""), "").strip()
                    sorting_value = record.get(self.field_mapping.get("sorting_value", ""), "").strip()
                    hint_field_value = record.get(self.field_mapping.get("hint_field_value", ""), "").strip()
                    
                    # Parse group IDs
                    group_ids_val = record.get(self.field_mapping.get("group_ids", ""), "")
                    group_ids = []
                    if isinstance(group_ids_val, list):
                        group_ids = [str(g).strip() for g in group_ids_val if str(g).strip()]
                    elif isinstance(group_ids_val, str) and group_ids_val.strip():
                        group_ids = [g.strip() for g in group_ids_val.split(self.group_separator) if g.strip()]

                    # Store full record in metadata
                    metadata = dict(record)

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
        except (FileNotFoundError, json.JSONDecodeError):
            self._notes = []

    def find_notes(self, query: str) -> List[VocabNote]:
        """Finds matching notes. If query is empty or '*', returns all notes."""
        if not query or query == "*":
            return self._notes

        query_lower = query.lower()
        results = []
        for note in self._notes:
            if query_lower in note.word.lower() or query_lower in note.meaning.lower():
                results.append(note)
        return results

    def get_note(self, note_id: str) -> Optional[VocabNote]:
        """Retrieves a single vocabulary note by its ID."""
        for note in self._notes:
            if note.id == note_id:
                return note
        return None

    def update_notes(self, notes: List[VocabNote]) -> None:
        """Updates modified notes in memory."""
        for updated_note in notes:
            for i, note in enumerate(self._notes):
                if note.id == updated_note.id:
                    self._notes[i] = updated_note
                    break

    def close(self) -> None:
        """Writes the in-memory notes back to the JSON file."""
        records = []
        for note in self._notes:
            record = dict(note.metadata)
            
            # Sync mapped values back
            word_key = self.field_mapping.get("word")
            meaning_key = self.field_mapping.get("meaning")
            sorting_key = self.field_mapping.get("sorting_value")
            hint_key = self.field_mapping.get("hint_field_value")
            group_key = self.field_mapping.get("group_ids")

            record["id"] = note.id
            if word_key:
                record[word_key] = note.word
            if meaning_key:
                record[meaning_key] = note.meaning
            if sorting_key:
                record[sorting_key] = note.sorting_value
            if hint_key:
                record[hint_key] = note.hint_field_value
            if group_key:
                # Keep original type if it was list
                if isinstance(note.metadata.get(group_key), list):
                    record[group_key] = note.group_ids
                else:
                    record[group_key] = self.group_separator.join(note.group_ids)

            records.append(record)

        with open(self.json_path, mode="w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
