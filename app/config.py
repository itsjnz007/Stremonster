from dotenv import load_dotenv
import os

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TUNNEL_URL = os.getenv("TUNNEL_URL")

CACHE_DIR = ".cache"

MANIFEST_WEB: dict[str, object] = {
    'id': 'org.jnz.stremonster.web',
    'version': '1.0.2',
    'name': 'Stremonster - Web',
    'description': 'Fast streaming addon with web-based links (no torrents)',
    'types': ['movie', 'series'],
    'catalogs': [],
    'resources': ["stream"]
}

MANIFEST_TORRENTS: dict[str, object] = {
    'id': 'org.jnz.stremonster.torrents',
    'version': '1.0.2',
    'name': 'Stremonster - Torrents',
    'description': 'Torrent streams with speed testing (slower but more sources)',
    'types': ['movie', 'series'],
    'catalogs': [],
    'resources': ["stream"]
}

CATALOG_BUILDER = {
    "global": {
        "movie": {
            "popular": "https://api.themoviedb.org/3/movie/popular",
            "now_playing": "https://api.themoviedb.org/3/movie/now_playing"
        },
        "series": {
            "popular": "https://api.themoviedb.org/3/tv/popular",
        }
    },
    "tamil": {
        "movie": {
            "popular": "https://api.themoviedb.org/3/discover/movie?with_original_language=ta&sort_by=popularity.desc",
        }
    },
    "malayalam": {
        "movie": {
            "popular": "https://api.themoviedb.org/3/discover/movie?with_original_language=ml&sort_by=popularity.desc",
        }
    },
}

def get_catalog_metadata(catalog_builder: dict[str, dict[str, str]] = CATALOG_BUILDER) -> list[dict[str, str]]:
    metadata = []
    for region, types in catalog_builder.items():
        for media_type, categories in types.items():
            for category, url in categories.items():
                catalog_id = f"{region}_{media_type}_{category}"
                metadata.append({
                    "id": catalog_id,
                    "name": f"{category.replace('_', ' ').title()} ({region.title()})",
                    "type": media_type,
                    "description": f"TMDB {media_type} for {region} region, category: {category}",
                    "extra": {
                        "tmdb_url": url
                    }
                })
    return metadata

MANIFEST_CATALOG: dict[str, object] = {
    "id": "org.tmdb.regional.catalogs",
    "version": "1.0.0",
    "name": "Stremonster - Catalogs",
    "description": "Movies and series from TMDB in multiple languages (India, Tamil, Malayalam, Hindi)",
    "resources": ["catalog"],
    "types": ["movie", "series"],
    "catalogs": get_catalog_metadata()
}

ABSOLUTE_EPISODE_FOR = [
    "tt0388629",
]

if __name__ == "__main__":
    from pprint import pprint
    pprint(MANIFEST_CATALOG)