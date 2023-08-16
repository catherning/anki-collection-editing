import pytest
from src.utils import truncate_field, add_field

def test_short_field():
    assert truncate_field('short field') == 'short field'

def test_long_field():
    assert truncate_field('this is a very long field that needs to be truncated') == 'this is a very long field that...'
    
def test_field_length_33():
    assert truncate_field('a field with 33 characters only!') == 'a field with 33 characters only!'
    
def test_empty_field():
    assert truncate_field('') == ''
    
    
# Tests that create_note_type function creates a new note type with valid input parameters
def test_add_field():
    pass
    # add_field()