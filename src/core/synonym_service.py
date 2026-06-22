import os
import re
import uuid
import numpy as np
from typing import Any, Dict, List, Set, Tuple, Optional
from statistics import median, StatisticsError
from annoy import AnnoyIndex
from scipy.sparse import lil_array, csr_matrix
from loguru import logger
from src.core.models import VocabNote, SynonymGroup


class SynonymFinderService:
    """Core domain service for identifying synonyms and grouping vocabulary notes.
    
    This service handles the vector embeddings, indexing, mathematical clustering,
    and median/IQR outlier filtering, completely decoupled from Anki APIs.
    """

    def __init__(self, vector_search_lib: str = "spacy", model_name: str = "spacy", lang: str = "zh"):
        self.vector_search_lib = vector_search_lib
        self.model_name = model_name
        self.lang = lang
        self.nlp = None

    def load_model(self) -> None:
        """Loads the spaCy model or SentenceTransformers model as configured."""
        if self.nlp is not None:
            return

        logger.info(f"Loading NLP library: {self.vector_search_lib} with model: {self.model_name}")
        match self.vector_search_lib:
            case "spacy":
                import spacy
                try:
                    # Load spaCy model (excluding unneeded components for speed)
                    self.nlp = spacy.load(
                        f"{self.lang}_core_web_md", 
                        exclude=["ner", "tagger", "parser", "senter", "attribute_ruler"]
                    )
                except OSError:
                    logger.info(f"Downloading spaCy model: {self.lang}_core_web_md")
                    import subprocess
                    subprocess.run(
                        ["poetry", "run", "python", "-m", "spacy", "download", f"{self.lang}_core_web_md"], 
                        check=True
                    )
                    self.nlp = spacy.load(
                        f"{self.lang}_core_web_md", 
                        exclude=["ner", "tagger", "parser", "senter", "attribute_ruler"]
                    )
            case "transformers":
                from torch import bfloat16
                from transformers import AutoModel
                self.nlp = AutoModel.from_pretrained(self.model_name, trust_remote_code=True, torch_dtype=bfloat16)
            case "sentence_transformer":
                from sentence_transformers import SentenceTransformer
                self.nlp = SentenceTransformer(self.model_name)
            case _:
                raise ValueError(f"Unknown vector search library: {self.vector_search_lib}")
        
        logger.info("Model loaded successfully.")

    def get_word_vector(self, word: str) -> np.ndarray:
        """Computes the vector embedding of a single word."""
        self.load_model()
        if self.vector_search_lib == "spacy":
            return self.nlp(word).vector
        elif self.vector_search_lib in ("transformers", "sentence_transformer"):
            # Enforce 1D array
            return self.nlp.encode([word], max_length=256)[0]
        else:
            raise ValueError(f"Unsupported NLP model type: {self.vector_search_lib}")

    def get_vectors_of_notes(self, notes: List[VocabNote]) -> np.ndarray:
        """Computes vectors for a list of VocabNotes."""
        self.load_model()
        words = [note.word for note in notes]
        if self.vector_search_lib == "spacy":
            vectors = [self.get_word_vector(w) for w in words]
            return np.array(vectors)
        else:
            embeddings = self.nlp.encode(words)
            return embeddings

    def build_annoy_index(self, vectors: np.ndarray) -> AnnoyIndex:
        """Builds an Annoy Index for fast nearest-neighbor lookups."""
        nb_vector, vector_len = vectors.shape
        annoy_index = AnnoyIndex(vector_len, "angular")
        for i, v in enumerate(vectors):
            annoy_index.add_item(i, v)
        annoy_index.build(10)  # 10 trees
        return annoy_index

    def calc_group_dist(self, annoy_index: AnnoyIndex, index_list: List[int]) -> csr_matrix:
        """Calculates pairwise distance sparse matrix of items in index_list."""
        n_items = annoy_index.get_n_items()
        dist_array = lil_array((n_items, n_items))
        for i, idx in enumerate(index_list):
            for idx2 in index_list[i+1:]:
                dist_array[idx, idx2] = annoy_index.get_distance(idx, idx2)
        return csr_matrix(dist_array)

    def calc_sparse_row_mean(self, dist_array: csr_matrix) -> np.ndarray:
        """Calculates mean of each row in the distance sparse matrix."""
        a = dist_array.sum(axis=1).A1
        return np.divide(dist_array.sum(axis=1).A1, dist_array.getnnz(axis=1), out=a, where=dist_array.getnnz(axis=1) != 0)

    def calc_sparse_mean(self, dist_array: csr_matrix) -> float:
        """Calculates global mean distance."""
        nnz = dist_array.getnnz()
        if nnz == 0:
            return 0.0
        return float(dist_array.sum() / nnz)

    def find_outliers(self, dist_list: List[float]) -> List[int]:
        """Identifies outliers using the median and IQR (Interquartile Range) algorithm."""
        filtered_list = [el for el in dist_list if el != 0]
        if not filtered_list:
            return []
        
        m = median(filtered_list)
        try:
            q1 = median([el for el in filtered_list if el <= m])
        except StatisticsError:
            q1 = m
        try:
            q3 = median([el for el in filtered_list if el >= m])
        except StatisticsError:
            q3 = m
            
        iqr = q3 - q1
        outliers_index = [i for i, el in enumerate(dist_list) if el > q3 + (iqr * 1.02)]
        if not outliers_index:
            # If no outliers found, default to removing the single worst element
            return [int(np.argmax(dist_list))]
        return outliers_index

    def remove_group_outliers(
        self,
        annoy_index: AnnoyIndex,
        all_notes: List[VocabNote],
        groups: Dict[str, SynonymGroup]
    ) -> Dict[str, SynonymGroup]:
        """Filters out outlier notes from synonym groups of size >= 10."""
        note_id_to_index = {note.id: i for i, note in enumerate(all_notes)}
        
        for group_id, group in groups.items():
            if len(group.notes) >= 10:
                # Map notes to annoy index positions
                indices_in_annoy = [note_id_to_index[note.id] for note in group.notes if note.id in note_id_to_index]
                if len(indices_in_annoy) < 2:
                    continue
                
                dist_array = self.calc_group_dist(annoy_index, indices_in_annoy)
                mean_array = self.calc_sparse_row_mean(dist_array)
                
                outliers_idx_in_group = self.find_outliers(list(mean_array))
                outliers_ids = {group.notes[idx].id for idx in outliers_idx_in_group if idx < len(group.notes)}
                
                removed_notes = [n for n in group.notes if n.id in outliers_ids]
                logger.debug(f"Removing outlier notes from group {group_id}: {[n.word for n in removed_notes]}")
                
                # Keep non-outliers
                group.notes = [n for n in group.notes if n.id not in outliers_ids]
                
                # Remove association from note domain objects
                for removed in removed_notes:
                    removed.remove_from_group(group_id, group.unique_id)
                    
        return groups

    def merge_groups(self, groups: Dict[str, SynonymGroup]) -> Dict[str, SynonymGroup]:
        """Merges overlapping groups when they share 3 or more common notes."""
        merged_groups = {**groups}
        removed_group_ids: Set[str] = set()
        
        for g_id, g in groups.items():
            for g_id2, g2 in groups.items():
                if g_id2 > g_id and g_id2 not in removed_group_ids and g_id not in removed_group_ids:
                    g1_set = {n.id for n in g.notes}
                    g2_set = {n.id for n in g2.notes}
                    common_notes = len(g1_set.intersection(g2_set))
                    
                    if common_notes >= 3:
                        combined_notes_map = {n.id: n for n in g.notes + g2.notes}
                        combined_notes = list(combined_notes_map.values())
                        
                        if len(combined_notes) <= 10 or common_notes >= 4:
                            g.notes = combined_notes
                            removed_group_ids.add(g_id2)
                            del merged_groups[g_id2]
                            
                            # Update note associations
                            g2_group = groups[g_id2]
                            for note in combined_notes:
                                note.remove_from_group(g_id2, g2_group.unique_id)
                                note.add_to_group(g_id, g.unique_id)
                        else:
                            logger.debug(f"Groups {g_id} and {g_id2} were not merged because size > 10. Common: {common_notes}")

        # Reset group IDs to consecutive string integers
        resorted_groups: Dict[str, SynonymGroup] = {}
        for idx, group in enumerate(merged_groups.values()):
            new_id = str(idx + 1)
            old_id = group.group_id
            group.group_id = new_id
            
            # Update all notes within the group
            for note in group.notes:
                note.remove_from_group(old_id, group.unique_id)
                note.add_to_group(new_id, group.unique_id)
                
            resorted_groups[new_id] = group

        logger.info(f"Merged groups. Now max group ID is {len(resorted_groups)}")
        return resorted_groups

    def find_new_groups_from_embedding(
        self,
        target_note: VocabNote,
        all_notes: List[VocabNote],
        annoy_index: AnnoyIndex,
        groups: Dict[str, SynonymGroup],
        overall_edited_notes: Set[str],
        current_max_id: int,
        distance_threshold: float = 0.9
    ) -> Tuple[int, Dict[str, SynonymGroup]]:
        """Uses vector search to find synonyms for a target note and updates the group mapping."""
        note_id_to_index = {note.id: i for i, note in enumerate(all_notes)}
        if target_note.id not in note_id_to_index:
            return current_max_id, groups

        target_idx = note_id_to_index[target_note.id]
        nn_indices, distances = annoy_index.get_nns_by_item(target_idx, 15, include_distances=True)
        
        # Skip the self-reference (first element)
        nn_indices, distances = nn_indices[1:], distances[1:]
        logger.debug(f"Average distance of 15 closest notes: {np.mean(distances):.2f}, all: {[round(d, 2) for d in distances]}")

        group_member_ids = {target_note.id}
        for nn_idx, dist in zip(nn_indices, distances):
            if dist > distance_threshold:
                break
            
            neighbor_note = all_notes[nn_idx]
            
            # If they don't share any existing group, add them
            shared_groups = set(target_note.group_ids).intersection(set(neighbor_note.group_ids))
            if len(shared_groups) == 0:
                group_member_ids.add(neighbor_note.id)

        if len(group_member_ids) > 1:
            current_max_id += 1
            new_id = str(current_max_id)
            unique_uid = uuid.uuid4().int
            
            # Construct SynonymGroup object
            group_notes = [note_id_to_index[nid] for nid in group_member_ids if nid in note_id_to_index]
            new_group = SynonymGroup(
                group_id=new_id,
                unique_id=unique_uid,
                notes=[all_notes[idx] for idx in group_notes]
            )
            
            # Associate group with each note
            for note in new_group.notes:
                note.add_to_group(new_id, unique_uid)
                overall_edited_notes.add(note.id)
                
            groups[new_id] = new_group
        else:
            # Fallback to nearest neighbor if first few distances are reasonably close
            if len(distances) > 0 and distances[0] < 1.0:
                current_max_id += 1
                new_id = str(current_max_id)
                unique_uid = uuid.uuid4().int
                
                closest_note = all_notes[nn_indices[0]]
                new_group = SynonymGroup(
                    group_id=new_id,
                    unique_id=unique_uid,
                    notes=[target_note, closest_note]
                )
                
                for note in new_group.notes:
                    note.add_to_group(new_id, unique_uid)
                    overall_edited_notes.add(note.id)
                    
                groups[new_id] = new_group
            else:
                logger.warning(f"No synonyms found using vector search for '{target_note.word}'")

        return current_max_id, groups
