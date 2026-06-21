import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import re
from typing import Optional, List
from app.models.metadata import Metadata

class Parsers:
    def __init__(self):
        self.languages = ['english', 'tamil', 'malayalam', 'kannada', 'hindi', 'telugu']

    def is_match(self, item_title: str, target_title: str) -> bool:
        # 1. Clean the prefix from the item_title (e.g., "LIK: " -> "")
        # This regex removes anything followed by a colon at the start of the string
        cleaned_item = re.sub(r'^[^:]+:\s*', '', item_title)
        
        # 2. Normalize both
        norm_item = self.normalize_text(cleaned_item)
        norm_target = self.normalize_text(target_title)
        
        # 3. Use Regex with Word Boundaries (\b) to ensure complete word matching
        # \b ensures that "Lokahe" does not match "Lokah"
        pattern = rf"\b{re.escape(norm_target)}\b"
        
        return bool(re.search(pattern, norm_item))

    def normalize_text(self, text: str) -> str:
        """Removes special characters and maps numerical synonyms to digits."""
        # 1. Map number words to digits to standardize
        num_map = {
            "one": "1", "two": "2", "three": "3", "four": "4", "five": "5"
        }
        
        # 2. Lowercase and replace non-alphanumeric with spaces
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        
        # 3. Standardize words
        words = text.split()
        normalized_words = [num_map.get(w, w) for w in words]
        
        return " ".join(normalized_words)
    

    def find_all_matches(
        self, 
        input_title: str, 
        input_year: Optional[str], 
        metadata_list: List[Metadata]
    ) -> List[Metadata]:
        
        target_title_norm = self.normalize_text(input_title)
        target_year = str(input_year).strip() if input_year else None
        
        matches: list[Metadata] = []
        
        for item in metadata_list:
            # 1. Compare Year Logic:
            # Skip only if BOTH have a year AND they don't match
            if item.year and target_year and str(item.year) != target_year:
                continue
                
            # 2. Compare Title:
            if self.normalize_text(item.title) == target_title_norm:
            # if self.is_match(self.normalize_text(item.title), target_title_norm):
                matches.append(item)
                
        return matches
    
    def parse_metadata(
        self, 
        text: str, 
        url: str, 
        languages: Optional[List[str]] = None
    ) -> Metadata:
        if not languages: languages = self.languages
        # 1. Prepare allowed languages (case-insensitive mapping)
        lang_map = {lang.casefold(): lang for lang in languages}
        
        # 2. Extract Year
        year_match = re.search(r'\(?(\d{4})\)?', text)
        year = year_match.group(1) if year_match else None
        
        # 3. Clean the text
        clean_text = re.sub(r'\(?\d{4}\)?', '', text)
        clean_text = re.sub(r'[\[\]\(\)\+\,]', ' ', clean_text)
        
        tokens = clean_text.split()
        
        # 4. Identify languages and title
        found_languages: list[str] = []
        title_words: list[str] = []
        
        for token in tokens:
            if token.casefold() in lang_map:
                found_languages.append(lang_map[token.casefold()])
            else:
                title_words.append(token)
                
        return Metadata(
            title=" ".join(title_words).strip(),
            url=url,  # Now filled with the provided URL
            year=year,
            languages=found_languages
        )
    

if __name__ == "__main__":
    parsers = Parsers()
    # --- Testing ---
    database = [
        Metadata(title="Lokah: Chapter One", url="", year="2026", languages=["Tamil", "Hindi"]),
        Metadata(title="Kara", url="", year=None, languages=["Tamil"]),
        Metadata(title="Karaa", url="", year="2026", languages=["Hindi"]),
        Metadata(title="Bison Kaalamaadan", url="", year="2025")
    ]

    # Test Case 1: Match "Lokah chapter 1" (2026 matches)
    print(f"Match 1: {parsers.find_all_matches('lokah chapter 1', '2026', database)}")

    # Test Case 2: Match "Kara" (No year in DB, matches 2025 input)
    print(f"Match 2: {parsers.find_all_matches('kara', '2025', database)}")

    # Test Case 3: "Karaa" (2026) vs 2025 input (Mismatch, should be None)
    print(f"Match 3: {parsers.find_all_matches('karaa', '2025', database)}")

    print(f"Match 4: {parsers.find_all_matches('Bison: Kaalamaadan', '2025', database)}")