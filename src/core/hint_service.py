import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from src.core.models import VocabNote
from src.utils.text_utils import breaklines_by_decade


class HintGeneratorService:
    """Service responsible for generating and formatting vocabulary hints.
    
    This service is entirely decoupled from Anki, operating solely on VocabNote
    domain models and standard Python types.
    """

    def __init__(self):
        pass

    def default_text_sorting_key(self, item: Tuple[VocabNote, str, str]) -> str:
        """Sorts alphabetically by sorting value (lowercased)."""
        return item[2].lower()

    def default_int_sorting_key(self, item: Tuple[VocabNote, str, str]) -> int:
        """Sorts numerically by sorting value."""
        try:
            return int(item[2])
        except ValueError:
            return 0

    def generate_hints_for_group(
        self,
        notes: List[VocabNote],
        flds_in_hint: List[str],
        sorting_field: str,
        sorting_key: Optional[Callable] = None,
        separator: str = ", ",
        additional_hint_field: Optional[str] = None,
        additional_hint_func: Optional[Callable] = None,
        break_lines: bool = False,
        replace_existing: bool = True,
        group_separator: str = ", ",
        current_group_id: Optional[str] = None
    ) -> Dict[str, str]:
        """Generates adapted hint strings for a list of notes in a group.
        
        Returns a dictionary mapping note IDs to their final hint string.
        """
        if len(notes) < 2:
            # Cannot generate hints based on fewer than 2 notes
            return {}

        # 1. Gather raw content and sorting info for each note
        raw_hints: List[Tuple[VocabNote, str, str]] = []
        for note in notes:
            # Extract content from fields in metadata or direct attributes
            field_values = []
            for field_name in flds_in_hint:
                val = note.metadata.get(field_name, "")
                if not val and hasattr(note, field_name):
                    val = getattr(note, field_name)
                if val:
                    field_values.append(str(val))
            
            content = separator.join(field_values)
            
            # Extract sorting info
            sorting_info = str(note.metadata.get(sorting_field, ""))
            if not sorting_info and hasattr(note, sorting_field):
                sorting_info = str(getattr(note, sorting_field))
            
            raw_hints.append((note, content, sorting_info))

        # 2. Determine sorting key
        if sorting_key is None:
            # If all sorting values look like integers, sort numerically
            try:
                all_ints = True
                for item in raw_hints:
                    int(item[2])
                sorting_key = self.default_int_sorting_key
            except ValueError:
                sorting_key = self.default_text_sorting_key

        # 3. Sort notes and their raw hints
        try:
            raw_hints_sorted = sorted(raw_hints, key=sorting_key)
        except Exception as e:
            # Fallback to simple text sort if custom key fails
            raw_hints_sorted = sorted(raw_hints, key=lambda x: x[2].lower())

        # 4. Generate the adapted hint for each note
        updated_hints: Dict[str, str] = {}
        for target_idx, (target_note, target_content, _) in enumerate(raw_hints_sorted):
            # Compute hiding character
            hidding_char = "?"
            if additional_hint_field is not None:
                field_raw_text = target_note.metadata.get(additional_hint_field, "")
                if not field_raw_text and hasattr(target_note, additional_hint_field):
                    field_raw_text = getattr(target_note, additional_hint_field)
                
                # Strip HTML tags
                clean_text = re.sub(r"<[^>]+>", "", str(field_raw_text))
                
                if additional_hint_func is not None:
                    try:
                        hidding_char = additional_hint_func(clean_text)
                    except Exception:
                        hidding_char = clean_text[0] if clean_text else "?"
                else:
                    hidding_char = clean_text[0] if clean_text else "?"

            # Build list of strings representing the final formatted lines
            hint_lines = []
            for idx, (note, content, _) in enumerate(raw_hints_sorted):
                if idx == target_idx:
                    hint_lines.append(hidding_char)
                else:
                    hint_lines.append(content)

            # Apply breaklines if requested (spacing by decade)
            if break_lines:
                hint_lines = breaklines_by_decade(hint_lines)

            # Combine lines
            hint_string = "<br>".join(hint_lines)

            # Figure out if we should append or replace
            should_replace = replace_existing
            if not should_replace and group_separator and current_group_id:
                # If note has multiple groups, we append
                existing_groups = str(target_note.metadata.get("group_name_val", ""))
                if group_separator in existing_groups:
                    # Let's inspect group IDs
                    try:
                        group_ids = [int(el.strip()) for el in existing_groups.split(group_separator) if el.strip().isdigit()]
                        if int(current_group_id) in group_ids:
                            should_replace = False
                    except ValueError:
                        pass

            if should_replace:
                target_note.hint_field_value = hint_string
            else:
                if target_note.hint_field_value:
                    target_note.hint_field_value += "<br><br>" + hint_string
                else:
                    target_note.hint_field_value = hint_string

            updated_hints[target_note.id] = target_note.hint_field_value

        return updated_hints
