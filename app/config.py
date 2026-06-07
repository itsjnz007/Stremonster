TUNNEL_URL = "https://stremonster.dpdns.org"
# TUNNEL_URL = "http://localhost:5000"
# TUNNEL_URL = "https://fraction-essex-pee-jones.trycloudflare.com"

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

MANIFEST_TMDB: dict[str, object] = {
    "id": "org.tmdb.regional.catalogs",
    "version": "1.0.0",
    "name": "Stremonster - Catalogs",
    "description": "Movies and series from TMDB in multiple languages (India, Tamil, Malayalam, Hindi)",
    "resources": ["catalog"],
    "types": ["movie", "series"],
    "catalogs": [
        # Movies (India)
        # {
        #     "type": "movie",
        #     "id": "popular_IN",
        #     "name": "Popular (India)"
        # },
        {
            "type": "movie",
            "id": "now_playing_IN",
            "name": "Now Playing"
        },
        # Recommended (Top Rated) Movies (India)
        {
            "type": "movie",
            "id": "recommended_IN",
            "name": "Top Rated"
        },
        # Series (India)
        # {
        #     "type": "series",
        #     "id": "popular_IN",
        #     "name": "Popular (India)"
        # },
        # Recommended (Top Rated) Series (India)
        {
            "type": "series",
            "id": "recommended_IN",
            "name": "Top Rated"
        },
        # Movies (Tamil)
        {
            "type": "movie",
            "id": "popular_TL",
            "name": "Popular (Tamil)"
        },
        # {
        #     "type": "movie",
        #     "id": "now_playing_TL",
        #     "name": "Now Playing (Tamil)"
        # },
        # Series (Tamil)
        # {
        #     "type": "series",
        #     "id": "popular_TL",
        #     "name": "Popular (Tamil)"
        # },
        # Movies (Malayalam)
        {
            "type": "movie",
            "id": "popular_ML",
            "name": "Popular (Malayalam)"
        },
        # {
        #     "type": "movie",
        #     "id": "now_playing_ML",
        #     "name": "Now Playing (Malayalam)"
        # },
        # Series (Malayalam)
        # {
        #     "type": "series",
        #     "id": "popular_ML",
        #     "name": "Popular (Malayalam)"
        # },
        # Movies (Hindi)
        {
            "type": "movie",
            "id": "popular_HI",
            "name": "Popular (Hindi)"
        },
        # {
        #     "type": "movie",
        #     "id": "now_playing_HI",
        #     "name": "Now Playing (Hindi)"
        # },
        # Series (Hindi)
        # {
        #     "type": "series",
        #     "id": "popular_HI",
        #     "name": "Popular (Hindi)"
        # },
    ]
}

ABSOLUTE_EPISODE_FOR = [
    "tt0388629",
]


# Legacy manifest for backward compatibility
MANIFEST = MANIFEST_WEB
