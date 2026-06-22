from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class VocabNote:
    """Represents a standardized vocabulary note in our core domain.
    
    This dataclass is entirely independent of Anki, CSV, or any physical database.
    It encapsulates the word, meaning, sorting/hint metadata, and association with
    synonym groups.
    """
    id: str  # Standardized string identifier (e.g., Anki note ID, or CSV row index)
    word: str  # The key term/character (e.g., "aufmuntern", "Simplified" Chinese)
    meaning: str  # The definition or translation of the term
    sorting_value: str = ""  # Value used for sorting within a group (e.g., Year or Pinyin)
    hint_field_value: str = ""  # Current contents of the hint holding field
    group_ids: List[str] = field(default_factory=list)  # Associated group IDs (e.g. ["1", "5"])
    unique_group_ids: List[int] = field(default_factory=list)  # Robust UUID ints mapping to groups
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extensible map for any custom/raw fields

    def add_to_group(self, group_id: str, unique_group_id: int) -> None:
        """Associate this note with a synonym group."""
        g_id_str = str(group_id)
        if g_id_str not in self.group_ids:
            self.group_ids.append(g_id_str)
        if unique_group_id not in self.unique_group_ids:
            self.unique_group_ids.append(unique_group_id)

    def remove_from_group(self, group_id: str, unique_group_id: int) -> None:
        """Deassociate this note from a synonym group."""
        g_id_str = str(group_id)
        if g_id_str in self.group_ids:
            self.group_ids.remove(g_id_str)
        if unique_group_id in self.unique_group_ids:
            self.unique_group_ids.remove(unique_group_id)


@dataclass
class SynonymGroup:
    """Represents a group of synonymous or related vocabulary notes."""
    group_id: str  # Sequential group ID (e.g., "1", "2")
    unique_id: int  # Long-term stable UUID int
    notes: List[VocabNote] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize group to standard format for JSON output."""
        return {
            "unique_id": self.unique_id,
            "notes": [{"id": int(n.id) if n.id.isdigit() else n.id, "text": n.word} for n in self.notes]
        }
