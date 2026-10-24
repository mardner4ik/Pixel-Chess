"""Music selections with attribution and bundled audio paths."""

SOUNDTRACKS = (
    {
        "id": "friday_morning",
        "title": "Friday Morning",
        "file": "ambient.ogg",
        "isrc": "USUAN1100224",
    },
    {
        "id": "easy_lemon",
        "title": "Easy Lemon",
        "file": "music/easy_lemon.ogg",
        "isrc": "USUAN1200076",
    },
    {
        "id": "immersed",
        "title": "Immersed",
        "file": "music/immersed.ogg",
        "isrc": "USUAN1600010",
    },
    {
        "id": "morning",
        "title": "Morning",
        "file": "music/morning.ogg",
        "isrc": "USUAN2300003",
    },
    {
        "id": "evening",
        "title": "Evening",
        "file": "music/evening.ogg",
        "isrc": "USUAN2300002",
    },
)

SOUNDTRACKS_BY_ID = {track["id"]: track for track in SOUNDTRACKS}
