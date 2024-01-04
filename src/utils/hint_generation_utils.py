# from datetime import datetime
from typing import Callable, Optional
import re
from anki.collection import Collection
from anki.models import ModelManager, NotetypeDict
from bs4 import BeautifulSoup
from loguru import logger

from src.utils.field_utils import (extract_cloze_deletion,
                   get_field_index, print_note_content, proceed, get_cloze_data, get_cleaned_field_data,
                   breaklines_by_number)
from src.utils.note_utils import find_notes
from src.utils.constants import CLOZE_TYPE

class HintGenerator:
    def __init__(self, 
                 flds_in_hint:list[str], 
                 col_path:str, 
                 notesID:list[int],
                 col:Optional[Collection]=None,
                 hint_holding_field: Optional[str]= "Extra", # make obligatory as if it's the default 
                    # and it doesn't exists, might throw error?
                 sorting_field:Optional[str]=None,
                 sorting_key: Optional[Callable]=None,
                 separator:Optional[str]=", ", 
                 cloze_field:Optional[int]=None, 
                 group_separator:Optional[str]=None
                 ):
        
        self.col = Collection(col_path) if col is None else col
        self.notesID = notesID
        self.hint_holding_field = hint_holding_field
        self.flds_in_hint = flds_in_hint
        self.sorting_field = sorting_field
        self.sorting_key = sorting_key
        self.separator = separator
        self.cloze_field = cloze_field # TODO: get cloze_field_index here once and for all?
        self.group_separator = group_separator
        self.note_hints_sorted = []
        
        
    def default_text_sorting_key(row):
        return row[1].lower()
    
    def default_int_sorting_key(row):
        return int(row[1])
                
    def run(
        self,
        note_type_name: str,
        query: str,
        cloze_field: Optional[str]=None,
        break_lines: bool = False,
        replace: bool = False,
    ) -> None:
        """Main method to generate hints for several notes using their information.

        Args:
            note_type_name (str): The name of the common note type
            query (str): The query to find the notes to update
            flds_in_hint (list[str]): The fields from where to extract the hint info.
            Ex: ["c2","c1"] if the notes are Cloze notes
            hint_field (str): The field where the hint will be stored in
            additional_hint_field (Optional[str]): The field from where to extract
            the eventual additional hint in the form of the first character of the field
            sorting_key (Optional[Callable]): The key to sort the hints
            sorting_field (Optional[str]): The field used for sorting
            cloze_field (Optional[str]): The name of the cloze field if notes are Cloze.
            separator (str, optional): The string to separate the info from flds_in_hint.
            Defaults to ", ".
            break_lines (bool, optional): If you want breaklines. For now it only works
            if the sorting field is numerical (years) and it add breaklines between decades.
            Defaults to False.
            replace (bool, optional): If you want to replace, not append the hing field.
            Defaults to False.

        Raises:
            ValueError: If there is only 0 or 1 note found with the query
        """
        
        notesID, _, _, hint = self.generate_clean_hint(note_type_name, query, cloze_field, break_lines)

        notes = []
        for nid in notesID:
            # TODO: check if ok
            note = self.col.get_note(nid)
            note[self.hint_holding_field] = hint
            notes.append(note)

        logger.info("Confirm the hint generation and save notes ? (Y/n)")
        if input() == "Y":
            self.col.update_notes(notes)
            logger.success("New note hints saved in the collection!")

        self.col.close()

    def generate_clean_hint(self, note_type_name, query, cloze_field, break_lines):
        # TODO: see what to return bw note_hints_sorted and hint? if HintGen, only need hint because identical
        # If HintAdaptor, need note_hints_sorted bc need to adapt to each note afterwards
        
        notesID, original_model = find_notes(
            self.col, query, note_type_name, verbose=True, cloze_text_field=cloze_field
        )

        if len(notesID) < 2:
            raise ValueError(
                "There is only one note. You can't generate hints based on several notes."
            )

        self.cloze_field_index = (
            get_field_index(original_model, cloze_field)
            if original_model["type"] == CLOZE_TYPE
            else None
        )

        note_hints = self.get_raw_global_hint()

        # If the first hint info is numeric, then sort as int
        # (not int as strings, otherwise "10"<"6")
        if self.sorting_key is None:
            try:
                [int(el[1]) for el in note_hints]
                self.sorting_key = self.default_int_sorting_key
            except ValueError:
                self.sorting_key = self.default_text_sorting_key

        try:
            note_hints_sorted = self.clean_hint(
                note_hints, break_lines=break_lines
            )
            hint = self.get_string_hint_from_list()
        except Exception as e:
            logger.error(e)
            logger.error("There might have been an error with the sorting key.")
            exit()

        logger.info("The hint that will be repercuted to all notes is:")
        logger.info(hint)
        return notesID, original_model, note_hints_sorted,hint, 
    

    def get_raw_global_hint(self
    ) -> list[tuple[str, str]]:
        """Generate the global hint that uses information from several notes.

        Args:
            col (Collection): The Anki Collection
            notesID (list[int]): The IDs of the notes for which to add the generated hint
            flds_in_hint (list[str]): The fields of the notes to use to generate the hint
            cloze_field_index (Optional[int]): The index of the cloze field if the notes
            are Cloze
            separator (str, optional): The string to add between each info from the fields in
                flds_in_hint. Defaults to ", ".
            sorting_field (_type_, optional): The field to use to sort the hint.
            Defaults to None.

        Returns:
            list[tuple[str, str]]: The list of global hint and the field info used for sorting
        """
        note_hints = []
        c_err = 0
        for nid in self.notesID:
            note = self.col.get_note(nid)

            # TODO: check if all notes have the same type? try if it's already checked.
            # Otherwise, do I need to check note type each time, not above for loop?
            
            if note._note_type["type"] == CLOZE_TYPE:
                content = get_cloze_data(self.flds_in_hint, 
                                         self.cloze_field_index, self.separator, 
                                         self.sorting_field, c_err, note)
                sorting_info = extract_cloze_deletion(
                    self.cloze_field_index, note, self.sorting_field
                )
            else:
                content = get_cleaned_field_data(self.separator, note, self.flds_in_hint)  
                sorting_info = BeautifulSoup(note[self.sorting_field], "html.parser").text
                
            content = content[:len(content)-len(self.separator)] # remove last separator that is useless
            note_hints.append((content, sorting_info))

        if c_err > 0:
            logger.warning("There were errors generating the hint from cloze fields.")
            proceed()

        return note_hints

    def get_string_hint_from_list(self)->str:
        hint = "<br>".join(self.note_hints_sorted)
        return hint

    def clean_hint(
        self,
        notesID: list[int],
        note_hints: list[tuple[str, str]],
        break_lines: bool = False,
    ) -> list[str]:
        """Clean the global hint by sorting and eventually adding break lines.

        Args:
            note_hints (list[tuple[str, str]]): The generated global hint to clean
            sorting_key (Optional[Callable]): The method to use to sort the hint
            (alphabetically, numerically). Ex: lambda row: int(row[1])
            break_lines (bool, optional): If you want breaklines. For now it only works
            if the sorting field is numerical (years) and it add breaklines between decades.
            Defaults to False.

        Returns:
            list[str]: The cleaned hints
        """
        note_hints_sorted = note_hints[:]
        # note_hints_sorted.sort(key=sorting_key)
        temp = sorted(zip(note_hints_sorted, notesID), key=lambda zipped_list: self.sorting_key(zipped_list[0]))
        note_hints_sorted, notesID = zip(*temp)
        
        # Issue with sorting pinyin for now:
        # ex yunmi < yunan whereas it should be the opposite (yu<yun)
        note_hints_sorted = [el[0] for el in note_hints_sorted]

        # TODO: Specifics to have lines breaks between decades when the sorting field is Year
        if break_lines:
            note_hints_sorted = breaklines_by_number(note_hints_sorted)
        return note_hints_sorted
    
    
class HintAdaptor(HintGenerator):
    def __init__(self, 
                 additional_hint_field: Optional[str] = None,
                 additional_hint_func: Optional[Callable] = None,):
        super().__init__(self)
        self.additional_hint_field = additional_hint_field
        self.additional_hint_func = additional_hint_func
        
    def append_if_not_first_group(self, query, replace, note):
        if not self.group_separator:
            return replace

        query_field = query.split(":")[0].replace('"','')
        p = re.compile(r"(\d+)")
        m = p.search(query)
        if m:
            current_group_ID = int(m.group(1))
        
        # If user wants to replace the hints from scratch, then we must check if current note was already 
        # edited with the script
        # If they systematically want to append, not replace, then we skip the if below 
        if self.group_separator in note[query_field] and replace:
            note_groups = [int(el) for el in note[query_field].split(self.group_separator)]
            if current_group_ID == min(note_groups):
                replace = True
            elif current_group_ID in note_groups:
                replace = False
        return replace

    def get_string_hint_from_list(self, idx, hidding_char)->str:
        hint = (
            "<br>".join(self.note_hints_sorted[:idx])
            + ("<br>" if idx != 0 else "")
            + hidding_char
            + ("<br>" if idx != len(self.note_hints_sorted) - 1 else "")
            + "<br>".join(self.note_hints_sorted[idx + 1 :])
        )
        
        return hint
        
    def adapt_hint_to_note (
        self,
        query: str, 
        original_model: ModelManager,
        nid: int,
        cur_note_hint: str,
        cloze_field: str,
        additional_hint_func: Optional[Callable],
        query_field: Optional[str], #TODO: remove query or (query_field, group_separator) ?
        replace: bool = False,
        # func=None,
    ) -> NotetypeDict:
        """Adapt the hint to a note by hiding the hint info of that note and update the note.

        Args:
            col (Collection): The Anki collection
            note_hints_sorted (list[str]): The cleaned global hint
            original_model (ModelManager): The type of the note
            nid (int): The ID of the note
            cur_note_hint (str): The hint corresponding to the current note
            hint_holding_field (str): The field that will be populated with the hint
            cloze_field (str): The field with the cloze text (only for
            logging purposes)
            additional_hint_field (Optional[str]): The field with the eventual
            additional hint.
            If not given, then we hide the hint info with '?'. Otherwise, for now,
            we show the first character of the info in the additional_hint_field

        Raises:
            KeyError: additional_hint_field is wrong

        Returns:
            NotetypeDict: The updated note
        """
        note = self.col.get_note(nid)
        idx = self.note_hints_sorted.index(cur_note_hint)
        if self.additional_hint_field is None:
            hidding_char = "?"
        else:
            if additional_hint_func is None:
                def additional_hint_func(text):
                    return text[0]
            
            if original_model["type"] == CLOZE_TYPE:
                self.cloze_field_index = get_field_index(original_model, cloze_field)
                field_raw_text = extract_cloze_deletion(self.cloze_field_index, note, self.additional_hint_field)
            else:
                try:
                    field_raw_text = note[self.additional_hint_field]
                except KeyError as e:
                    logger.error(
                        "The field from which you want a more precise hint is missing"
                    )
                    raise e
                    
            field_text = BeautifulSoup(field_raw_text, "html.parser").text
            hidding_char = additional_hint_func(field_text)


        hint = self.get_string_hint_from_list(self.note_hints_sorted, idx, hidding_char)

        logger.info(
            "Hint adapted for the current note"
            f" {print_note_content(cloze_field, original_model, note)}:"
        )
        for el in hint.split("<br>"):
            print(el)

        replace = self.append_if_not_first_group(query, self.group_separator, replace, note)

        if replace:
            note[self.hint_holding_field] = hint
        else:
            hint = "<br><br>" + hint
            note[self.hint_holding_field] += hint
        return note

    def run(
        self,
        note_type_name: str,
        query: str,
        query_field: Optional[str]=None,
        break_lines: bool = False,
        replace: bool = False,
    ) -> None:
        """Main method to generate hints for several notes using their information.

        Args:
            note_type_name (str): The name of the common note type
            query (str): The query to find the notes to update
            flds_in_hint (list[str]): The fields from where to extract the hint info.
            Ex: ["c2","c1"] if the notes are Cloze notes
            hint_field (str): The field where the hint will be stored in
            additional_hint_field (Optional[str]): The field from where to extract
            the eventual additional hint in the form of the first character of the field
            sorting_key (Optional[Callable]): The key to sort the hints
            sorting_field (Optional[str]): The field used for sorting
            cloze_field (Optional[str]): The name of the cloze field if notes are Cloze.
            separator (str, optional): The string to separate the info from flds_in_hint.
            Defaults to ", ".
            break_lines (bool, optional): If you want breaklines. For now it only works
            if the sorting field is numerical (years) and it add breaklines between decades.
            Defaults to False.
            replace (bool, optional): If you want to replace, not append the hing field.
            Defaults to False.

        Raises:
            ValueError: If there is only 0 or 1 note found with the query
        """
        notesID, original_model, note_hints_sorted, hint = self.generate_clean_hint(note_type_name, query, sorting_key, cloze_field, col, break_lines)

        notes = []
        for i,nid in enumerate(notesID):
            note = self.adapt_hint_to_note(
                query,
                note_hints_sorted,
                original_model,
                nid,
                note_hints_sorted[i],
                replace = replace,
                query_field = query_field,
            )
            notes.append(note)

        logger.info("Confirm the hint generation and save notes ? (Y/n)")
        if input() == "Y":
            self.col.update_notes(notes)
            logger.success("New note hints saved in the collection!")

        self.col.close()