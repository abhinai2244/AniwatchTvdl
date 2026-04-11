#@cantarellabots
from aiohttp import ClientSession
from asyncio import sleep as asleep
from random import choice
from datetime import datetime
import re

# Simple cache for AniList data
ani_cache = {}
#@cantarellabots
# Dummy reporting utility
class Report:
    async def report(self, message, level="info", log=True):
        print(f"[{level.upper()}] {message}")

rep = Report()

# Dummy decorator for logging
def handle_logs(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            print(f"Error in {func.__name__}: {e}")
            return None
    return wrapper

# Simple parser fallback if guessit is not available
try:
    from guessit import guessit as parse
except ImportError:
    def parse(name):
        # Very basic parsing
        return {"anime_title": name}

CAPTION_FORMAT = """
<blockquote><b>◆ {title} ◆</b></blockquote>
<b>✦━━━━━━━━━━━━━━━━━━━━━━━━✦</b>
<blockquote><i>➥ Sᴇᴀsᴏɴ:- {anime_season}
➥ Eᴘɪsᴏᴅᴇ:- {ep_no}
➥ Sᴛᴀᴛᴜs:- {status}
➥ Gᴇɴʀᴇs:- {genres}
➥ Aᴜᴅɪᴏ:- {audio}</i></blockquote>
<b>✦━━━━━━━━━━━━━━━━━━━━━━━━✦</b>
<b><i>⌬ Pᴏᴡᴇʀᴇᴅ ʙʏ:- @cantarellabots</i></b>
"""

GENRES_EMOJI = {
    "Action": "👊", "Adventure": "🪂", "Comedy": "🤣",
    "Drama": "🎭", "Ecchi": "💋", "Fantasy": "🧞",
    "Hentai": "🔞", "Horror": "☠️", "Mahou Shoujo": "☯️", "Mecha": "🤖", "Mystery": "🔮",
    "Psychological": "♟️", "Romance": "💞", "Sci-Fi": "🛸", "Slice of Life": "☘️",
    "Sports": "⚽️", "Supernatural": "🫧", "Thriller": "🥶",
    "Isekai": "🌌", "Historical": "🏯", "Music": "🎶", "Martial Arts": "🥋",
    "School": "🏫", "Military": "🎖️", "Demons": "😈", "Vampire": "🧛‍♂️", "Space": "🚀",
    "Game": "🎮", "Crime": "🚓", "Parody": "😂", "Detective": "🕵️‍♂️", "Tragedy": "💔",
    "Yaoi": "👨‍❤️‍👨", "Yuri": "👩‍❤️‍👩", "Kids": "🧒", "Harem": "👸", "Music & Idol": "🎤",
    "Post-Apocalyptic": "☢️", "Cyberpunk": "💽", "Samurai": "🗡️", "Time Travel": "⏳"
}

GENRE_NORMALIZATION = {
    "Action & Adventure": "Action",
    "Romantic Comedy": "Comedy",
    "Shounen": "Action",
    "Shoujo": "Romance",
    "Seinen": "Drama",
    "Josei": "Drama",
    "Slice-of-Life": "Slice of Life",
    "Magical Girl": "Mahou Shoujo",
    "Science Fiction": "Sci-Fi",
    "Psychological Thriller": "Psychological",
    "Suspense": "Thriller",
    "Martial-Arts": "Martial Arts",
    "Fantasy Adventure": "Fantasy",
    "Post Apocalypse": "Post-Apocalyptic",
    "Cyber Punk": "Cyberpunk",
    "Historical Drama": "Historical",
    "Romance Comedy": "Romance",
    "Action Comedy": "Action",
    "Super Power": "Supernatural",
    "Game Based": "Game",
    "Music Idol": "Music & Idol",
    "Sports Drama": "Sports",
    "Military Sci-Fi": "Military",
    "Time-Travel": "Time Travel",
    "Detective Mystery": "Detective"
}

ANIME_GRAPHQL_QUERY = """
query ($id: Int, $search: String, $seasonYear: Int) {
  Media(id: $id, type: ANIME, format_not_in: [MUSIC, MANGA, NOVEL, ONE_SHOT], search: $search, seasonYear: $seasonYear, sort: POPULARITY_DESC) {
    id
    idMal
    title {
      romaji
      english
      native
    }
    type
    format
    status(version: 2)
    description(asHtml: false)
    startDate {
      year
      month
      day
    }
    endDate {
      year
      month
      day
    }
    season
    seasonYear
    episodes
    duration
    chapters
    volumes
    countryOfOrigin
    source
    hashtag
    trailer {
      id
      site
      thumbnail
    }
    updatedAt
    coverImage {
      large
    }
    bannerImage
    genres
    synonyms
    averageScore
    meanScore
    popularity
    trending
    favourites
    studios {
      nodes {
        name
        siteUrl
      }
    }
    isAdult
    nextAiringEpisode {
      airingAt
      timeUntilAiring
      episode
    }
    airingSchedule {
      edges {
        node {
          airingAt
          timeUntilAiring
          episode
        }
      }
    }
    externalLinks {
      url
      site
    }
    siteUrl
  }
}
"""

def normalize_genres(genres: list) -> list:
    normalized = []
    for genre in genres or []:
        genre_key = GENRE_NORMALIZATION.get(genre, genre)
        if genre_key in GENRES_EMOJI:
            emoji = GENRES_EMOJI[genre_key]
            normalized.append(f"{emoji} {genre_key}")
    return normalized

class AniLister:
    def __init__(self, anime_name: str, year: int) -> None:
        self.__api = "https://graphql.anilist.co"
        self.__ani_name = anime_name
        self.__ani_year = year
        self.__vars = {'search': self.__ani_name, 'seasonYear': self.__ani_year}

    def __update_vars(self, year: bool = True) -> None:
        if year:
            self.__ani_year -= 1
            self.__vars['seasonYear'] = self.__ani_year
        else:
            self.__vars = {'search': self.__ani_name}

    async def post_data(self):
        async with ClientSession() as sess:
            async with sess.post(self.__api, json={'query': ANIME_GRAPHQL_QUERY, 'variables': self.__vars}) as resp:
                return (resp.status, await resp.json(), resp.headers)

    async def get_anidata(self):
        cache_key = f"{self.__ani_name}:{self.__ani_year}"
        if cache_key in ani_cache:
            return ani_cache[cache_key]
        
        # Try without seasonYear first as it is more robust to find the correct anime
        self.__update_vars(year=False)
        res_code, resp_json, res_heads = await self.post_data()
        
        # If not found, try with the current year and decrement
        if res_code == 404:
            self.__ani_year = datetime.now().year
            self.__vars = {'search': self.__ani_name, 'seasonYear': self.__ani_year}
            res_code, resp_json, res_heads = await self.post_data()
            
            while res_code == 404 and self.__ani_year > 2020:
                self.__update_vars()
                await rep.report(f"AniList Query Name: {self.__ani_name}, Retrying with {self.__ani_year}", "warning", log=False)
                res_code, resp_json, res_heads = await self.post_data()

        # If still 404, try to simplify name (HiAnime often uses double spaces or long strings)
        if res_code == 404:
            # Try splitting by double space or common markers and taking the first part
            simple_name = re.split(r'  | - |: ', self.__ani_name)[0].strip()
            if simple_name != self.__ani_name:
                self.__ani_name = simple_name
                self.__update_vars(year=False)
                res_code, resp_json, res_heads = await self.post_data()
        if res_code == 200:
            data = resp_json.get('data', {}).get('Media', {}) or {}
            ani_cache[cache_key] = data
            return data
        elif res_code == 429:
            retry_after = int(res_heads.get('Retry-After', 10))
            await asleep(retry_after * 1.5)
            return await self.get_anidata()
        elif res_code in [500, 501, 502]:
            await asleep(5)
            return await self.get_anidata()
        await rep.report(f"AniList API Error: {res_code}", "error", log=False)
        return {}

    @handle_logs
    async def _parse_anilist_data(self, data):
        if not data or not data.get("data", {}).get("Media"):
            return {}
        anime = data["data"]["Media"]
        genres = normalize_genres(anime.get("genres", []))
        return {
            "id": anime.get("id"),
            "idMal": anime.get("idMal"),
            "title": anime.get("title", {}),
            "status": anime.get("status", "").replace("_", " ").title(),
            "description": anime.get("description"),
            "startDate": anime.get("startDate", {}),
            "endDate": anime.get("endDate", {}),
            "episodes": anime.get("episodes"),
            "genres": genres,
            "averageScore": anime.get("averageScore"),
            "coverImage": anime.get("coverImage", {})
        }

    @handle_logs
    async def get_anilist_id(self, mal_id: int = None, name: str = None, year: int = None):
        if mal_id:
            variables = {'idMal': mal_id}
        else:
            variables = {'search': name, 'seasonYear': year} if year else {'search': name}

        async with ClientSession() as sess:
            async with sess.post(self.__api, json={'query': ANIME_GRAPHQL_QUERY, 'variables': variables}) as resp:
                res_code = resp.status
                resp_json = await resp.json()
                res_heads = resp.headers

        if res_code == 200 and resp_json.get('data', {}).get('Media'):
            return resp_json['data']['Media']['id']
        elif res_code == 429:
            f_timer = int(res_heads.get('Retry-After', 10))
            await rep.report(f"AniList ID Fetch Rate Limit: Sleeping for {f_timer}s", "error")
            await asleep(f_timer)
            return await self.get_anilist_id(mal_id, name, year)
        await rep.report(f"Failed to fetch AniList ID for {name or mal_id}", "error")
        return None

class TextEditor:
    def __init__(self, name):
        self.__name = name
        self.adata = {}
        self.pdata = parse(name)
        self.anilister = AniLister(self.__name, datetime.now().year)

    async def load_anilist(self):
        cache_names = set()
        # Try different combinations of name to find it on AniList
        for no_s, no_y in [(False, False), (False, True), (True, False), (True, True)]:
            ani_name = await self.parse_name(no_s, no_y)
            if not ani_name or ani_name in cache_names:
                continue
            cache_names.add(ani_name)
            self.anilister._AniLister__ani_name = ani_name
            self.anilister._AniLister__vars['search'] = ani_name
            self.adata = await self.anilister.get_anidata()
            if self.adata:
                break  

    @handle_logs
    async def parse_name(self, no_s=False, no_y=False):
        anime_name = self.pdata.get("anime_title") or self.__name
        anime_season = self.pdata.get("anime_season")
        anime_year = self.pdata.get("anime_year")
        if anime_name:
            pname = str(anime_name)
            if not no_s and anime_season:
                pname += f" {anime_season}"
            if not no_y and anime_year:
                pname += f" {anime_year}"
            return pname
        return str(anime_name)

    @handle_logs
    async def get_poster(self):
        anime_id = self.adata.get("id")
        if anime_id and str(anime_id).isdigit():
            return f"https://img.anili.st/media/{anime_id}"
        return "https://envs.sh/YsH.jpg"
