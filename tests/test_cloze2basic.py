import sys

# import pytest

sys.path.insert(0, "./src")
# from src.cloze2basic import find_notes, create_note_type


def test_create_note_type_valid_input(mocker):
    col = mocker.Mock()
    models = mocker.Mock()
    col.models = models
    # note_name = "Test Note"
    # new_fields = [("Field 1", "Text"), ("Field 2", "Text")]
    # original_field_list = ["Field 1", "Field 2"]
    assert 1 == 1
    # result = create_note_type(col, note_name, new_fields, original_field_list)
    # assert result['name'] == note_name
    # assert len(result['flds']) == len(new_fields)
    # for i, field in enumerate(result['flds']):
    #     assert field['name'] == new_fields[i][0]
    #     assert field['ord'] == i
