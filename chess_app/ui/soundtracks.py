"""Music selections with attribution and bundled audio paths."""

SOUNDTRACKS = (
    {
        "id": "friday_morning",
        "title": "Friday Morning",
        "file": "ambient.wav",
        "isrc": "USUAN1100224",
    },
    {
        "id": "easy_lemon",
        "title": "Easy Lemon",
        "file": "music/easy_lemon.wav",
        "isrc": "USUAN1200076",
    },
    {
        "id": "immersed",
        "title": "Immersed",
        "file": "music/immersed.wav",
        "isrc": "USUAN1600010",
    },
    {
        "id": "morning",
        "title": "Morning",
        "file": "music/morning.wav",
        "isrc": "USUAN2300003",
    },
    {
        "id": "evening",
        "title": "Evening",
        "file": "music/evening.wav",
        "isrc": "USUAN2300002",
    },
)

SOUNDTRACKS_BY_ID = {track["id"]: track for track in SOUNDTRACKS}
