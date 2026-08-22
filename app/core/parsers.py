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
        """Maps numerical synonyms/symbols to digits, then removes special characters."""
        # 1. Map symbols and number words before removing punctuation
        mapping = {
            "&": "and",
            "one": "1", "two": "2", "three": "3", "four": "4", "five": "5"
        }
        
        text = text.lower()
        
        # Replace keys while maintaining boundaries for word-based keys
        pattern = re.compile(
            r'|'.join(r'\b{}\b'.format(re.escape(k)) if k.isalnum() else re.escape(k) for k in mapping.keys())
        )
        text = pattern.sub(lambda m: mapping[m.group(0)], text)
        
        # 2. Replace remaining non-alphanumeric characters with spaces
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
        
        # 3. Clean up extra spaces
        return " ".join(text.split())
    

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
        if not languages: 
            languages = self.languages

        lang_map = {lang.casefold(): lang for lang in languages}
        
        # 1. Extract Year
        year_match = re.search(r'\(?(\d{4})\)?', text)
        year = year_match.group(1) if year_match else None

        # 2. Extract Quality (e.g., WEB-DL, HD, 1080p, 720p, HDRip, CAM, DVDRip)
        quality_pattern = r'\b(WEB-DL|WEBRip|HDRip|DVDRip|BRRip|BluRay|HDTV|CAMRip|CAM|1080p|720p|480p|4k)\b'
        quality_match = re.search(quality_pattern, text, flags=re.IGNORECASE)
        quality = quality_match.group(1) if quality_match else None

        # 3. Clean string for title processing
        clean_text = re.sub(r'\(?\d{4}\)?', '', text)  # remove year
        clean_text = re.sub(quality_pattern, '', clean_text, flags=re.IGNORECASE)  # remove quality
        clean_text = re.sub(r'[\[\]\(\)\+\,\-]', ' ', clean_text)  # remove punctuation
        
        tokens = clean_text.split()
        
        found_languages: list[str] = []
        title_words: list[str] = []
        
        # Common trailing metadata words to skip if encountered after title
        garbage_words = {"full", "movie", "hd"}

        # 4. Identify title and languages
        for token in tokens:
            token_folded = token.casefold()
            
            if token_folded in lang_map:
                found_languages.append(lang_map[token_folded])
                # Once a language token is hit, stop accumulating title words
                break
            elif token_folded in garbage_words:
                continue
            else:
                title_words.append(token)
                
        return Metadata(
            title=" ".join(title_words).strip(),
            url=url,
            year=year,
            languages=found_languages,
            quality=quality
        )
    

if __name__ == "__main__":
    parsers = Parsers()
    metadata = parsers.parse_metadata("Idhayam Murali 2026 Tamil Full Movie WEB-DL", "https://example.com/movie")
    print(f"Metadata -> {metadata}")
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