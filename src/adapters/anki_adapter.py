import re
from typing import Dict, List, Optional, Any
from anki.collection import Collection
from src.core.models import VocabNote
from src.adapters.base import VocabularyRepository
from src.utils.text_utils import extract_plain_text


class AnkiVocabularyRepository(VocabularyRepository):
    """Anki-specific adapter mapping Anki Notes to core VocabNote domain models.
    
    This can be used offline via CLI (passing collection path) or inside a live 
    Anki desktop process (injecting an existing collection instance).
    """

    def __init__(
        self,
        col_or_path: Any,
        note_type_name: str,
        field_mapping: Dict[str, str],
        group_separator: str = ", "
    ):
        """
        Args:
            col_or_path: Either a file path to .anki2, or an active anki.collection.Collection
            note_type_name: The target Anki Notetype/Model name (e.g., "Chinois")
            field_mapping: Map from domain attributes to Anki field names.
                Required keys: "word", "meaning", "sorting_value", "hint_field_value", "group_ids"
            group_separator: Separator used for storing multiple group IDs in Anki (default: ", ")
        """
        if isinstance(col_or_path, str):
            self.col = Collection(col_or_path)
            self._owns_col = True
        else:
            self.col = col_or_path
            self._owns_col = False

        self.note_type_name = note_type_name
        self.field_mapping = field_mapping
        self.group_separator = group_separator

    def _to_domain_model(self, anki_note: Any) -> VocabNote:
        """Converts an Anki Note into a core VocabNote domain model."""
        note_id = str(anki_note.id)
        
        # Helper to get field value safely
        def get_field(name: str) -> str:
            mapped_name = self.field_mapping.get(name)
            if mapped_name and mapped_name in anki_note:
                return anki_note[mapped_name]
            return ""

        word_html = get_field("word")
        word = extract_plain_text(word_html).strip()
        meaning = get_field("meaning").strip()
        sorting_value = get_field("sorting_value").strip()
        hint_field_value = get_field("hint_field_value").strip()
        
        # Parse group IDs
        group_ids_raw = get_field("group_ids")
        group_ids = []
        if group_ids_raw.strip():
            group_ids = [g.strip() for g in group_ids_raw.split(self.group_separator) if g.strip()]

        # Collect all raw note fields into metadata
        metadata = {}
        for fld in anki_note.keys():
            metadata[fld] = anki_note[fld]

        # Also store original fields in metadata for later use in hint generation
        metadata["_anki_tags"] = anki_note.tags

        return VocabNote(
            id=note_id,
            word=word,
            meaning=meaning,
            sorting_value=sorting_value,
            hint_field_value=hint_field_value,
            group_ids=group_ids,
            metadata=metadata
        )

    def find_notes(self, query: str) -> List[VocabNote]:
        """Searches Anki for notes matching the query and maps them to VocabNotes."""
        # Append note type to the query to restrict searches
        full_query = query
        if f'note:"{self.note_type_name}"' not in query:
            full_query = f'{query} note:"{self.note_type_name}"'

        try:
            note_ids = self.col.find_notes(full_query)
        except Exception:
            self.col.reopen()
            note_ids = self.col.find_notes(full_query)

        vocab_notes = []
        for nid in note_ids:
            try:
                anki_note = self.col.get_note(nid)
                vocab_notes.append(self._to_domain_model(anki_note))
            except Exception as e:
                # Log and skip invalid notes
                continue
        return vocab_notes

    def get_note(self, note_id: str) -> Optional[VocabNote]:
        """Retrieves a single note by its Anki note ID."""
        try:
            anki_note = self.col.get_note(int(note_id))
            return self._to_domain_model(anki_note)
        except Exception:
            return None

    def update_notes(self, notes: List[VocabNote]) -> None:
        """Maps modified VocabNotes back to Anki notes and saves them to the DB."""
        anki_notes_to_update = []
        for note in notes:
            try:
                anki_note = self.col.get_note(int(note.id))
                
                # Helper to update mapped field
                def set_field(name: str, value: str):
                    mapped_name = self.field_mapping.get(name)
                    if mapped_name and mapped_name in anki_note:
                        anki_note[mapped_name] = value

                # Update group IDs
                group_ids_val = self.group_separator.join(note.group_ids)
                set_field("group_ids", group_ids_val)
                
                # Update hint field
                set_field("hint_field_value", note.hint_field_value)

                # Ensure any metadata modifications are synced back
                for k, v in note.metadata.items():
                    if k in anki_note and k not in (self.field_mapping.get("group_ids"), self.field_mapping.get("hint_field_value")):
                        anki_note[k] = str(v)

                anki_notes_to_update.append(anki_note)
            except Exception as e:
                continue

        if anki_notes_to_update:
            self.col.update_notes(anki_notes_to_update)

    def close(self) -> None:
        """Closes the underlying collection if this repository instance opened it."""
        if self._owns_col and self.col:
            self.col.close()
