import pytest
from src.core.models import VocabNote, SynonymGroup
from src.core.hint_service import HintGeneratorService
from src.core.synonym_service import SynonymFinderService


def test_vocab_note_and_synonym_group():
    # Create notes
    note1 = VocabNote(id="1", word="test1", meaning="meaning1", sorting_value="pinyin1")
    note2 = VocabNote(id="2", word="test2", meaning="meaning2", sorting_value="pinyin2")

    # Verify initial state
    assert len(note1.group_ids) == 0
    assert len(note1.unique_group_ids) == 0

    # Test group assignment
    note1.add_to_group("g101", 123456)
    assert note1.group_ids == ["g101"]
    assert note1.unique_group_ids == [123456]

    # Test duplicate assignment prevention
    note1.add_to_group("g101", 123456)
    assert note1.group_ids == ["g101"]

    # Test group removal
    note1.remove_from_group("g101", 123456)
    assert len(note1.group_ids) == 0
    assert len(note1.unique_group_ids) == 0


def test_hint_generator_service():
    hint_service = HintGeneratorService()

    # Create a list of notes for hint generation
    notes = [
        VocabNote(
            id="1", 
            word="炎热", 
            meaning="burning hot", 
            sorting_value="yánrè",
            metadata={"Simplified": "炎热", "Meaning": "burning hot", "Pinyin.1": "yánrè"}
        ),
        VocabNote(
            id="2", 
            word="酷热", 
            meaning="intense heat", 
            sorting_value="kùrè",
            metadata={"Simplified": "酷热", "Meaning": "intense heat", "Pinyin.1": "kùrè"}
        )
    ]

    # Generate hints for this group
    updated_hints = hint_service.generate_hints_for_group(
        notes=notes,
        flds_in_hint=["Simplified", "Meaning"],
        sorting_field="Pinyin.1",
        separator=" - "
    )

    # Note 1 (炎热, yánrè) is sorted after Note 2 (酷热, kùrè) alphabetically since "k" < "y".
    # So the sorted list of hints is:
    # Index 0: 酷热 - intense heat
    # Index 1: 炎热 - burning hot
    #
    # When adapted for Note 1 (idx 1), the first element remains intact, and the second is hidden:
    # "酷热 - intense heat<br>?"
    #
    # When adapted for Note 2 (idx 0), the first element is hidden, and the second remains:
    # "?<br>炎热 - burning hot"

    assert "1" in updated_hints
    assert "2" in updated_hints
    
    assert updated_hints["1"] == "酷热 - intense heat<br>?"
    assert updated_hints["2"] == "?<br>炎热 - burning hot"


def test_synonym_service_outliers():
    service = SynonymFinderService()

    # If list has no outliers, it should return index of max distance
    distances = [0.1, 0.2, 0.15, 0.9, 0.1]
    outliers = service.find_outliers(distances)
    assert outliers == [3]  # Index of 0.9 is 3


def test_synonym_service_merges():
    service = SynonymFinderService()

    # Create dummy notes
    notes = [VocabNote(id=str(i), word=f"word{i}", meaning="") for i in range(15)]

    # Group 1 has notes 0, 1, 2, 3, 4
    g1 = SynonymGroup(group_id="1", unique_id=111, notes=notes[0:5])
    for n in g1.notes:
        n.add_to_group("1", 111)

    # Group 2 has notes 2, 3, 4, 5, 6 (shares 2, 3, 4 - 3 common notes)
    g2 = SynonymGroup(group_id="2", unique_id=222, notes=notes[2:7])
    for n in g2.notes:
        n.add_to_group("2", 222)

    groups = {"1": g1, "2": g2}
    merged = service.merge_groups(groups)

    # After merge, Group 1 and Group 2 should merge into a single group because they share 3 elements,
    # and the total combined size is 7 (<= 10).
    assert len(merged) == 1
    assert "1" in merged
    
    merged_g1 = merged["1"]
    assert len(merged_g1.notes) == 7
    # Verify that all notes in merged group are updated correctly with the group ID
    for n in merged_g1.notes:
        assert "1" in n.group_ids
        assert "2" not in n.group_ids


def test_get_hint_params():
    from src.cli.run_hints import get_hint_params, romanic_sorting_key, romanic_additional_hint_func
    from src.utils.config import load_config
    
    # Test with loaded config
    config = load_config()
    
    # German profile
    german_params = get_hint_params("Allemand", "Synonyms", config=config)
    assert german_params["flds_in_hint"] == ["German", "French/English"]
    assert german_params["separator"] == " | "
    assert german_params["sorting_field"] == "German"
    assert german_params["sorting_key"] == romanic_sorting_key
    assert german_params["additional_hint_func"] == romanic_additional_hint_func
    assert german_params["hint_field"] == "Generated Synonyms"
    assert german_params["query_field"] == "Synonyms group"
    assert german_params["break_lines"] is False

    # Best Pictures profile with custom type
    bp_params = get_hint_params("Best Pictures", "Cognats", config=config)
    assert bp_params["flds_in_hint"] == ["Year", "Movie winner"]
    assert bp_params["separator"] == " "
    assert bp_params["sorting_field"] == "Year"
    assert bp_params["sorting_key"] is None
    assert bp_params["additional_hint_func"] is None
    assert bp_params["hint_field"] == "Extra"
    assert bp_params["query_field"] == "Year"
    assert bp_params["break_lines"] is True

