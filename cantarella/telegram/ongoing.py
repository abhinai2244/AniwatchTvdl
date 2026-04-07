from pyrogram.enums import ParseMode
from cantarella.core.proxy import get_random_proxy, get_proxy_dict
import asyncio
import os
from bs4 import BeautifulSoup
from curl_cffi import requests as c_requests
import json
import re
from pyrogram import Client
from cantarella.telegram.download import _handle_download
from cantarella.scraper.cantarellatv import cantarellatvDownloader
from cantarella.core.database import db
from cantarella.telegram.pages import post_to_main_channel
from cantarella.core.anilist import TextEditor
from config import SET_INTERVAL, TARGET_CHAT_ID, MAIN_CHANNEL, LOG_CHANNEL

BASE_URL = "https://aniwatchtv.to"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

from datetime import datetime

def fetch_schedule_list():
    """Fetch cantarella's daily schedule via AJAX."""
    try:
        session = c_requests.Session()
        proxy_dict = get_proxy_dict(get_random_proxy())
        if proxy_dict:
            session.proxies.update(proxy_dict)

        # Current date in YYYY-MM-DD format
        date_str = datetime.now().strftime("%Y-%m-%d")

        # AJAX for schedule list, tzOffset = -330 for IST (Indian Standard Time)
        url = f"{BASE_URL}/ajax/schedule/list?date={date_str}&tzOffset=-330"
        resp = session.get(url, headers=HEADERS, impersonate="chrome")
        if resp.status_code == 200:
            html = resp.json().get('html', '')
            if not html.strip() or "No data to display" in html:
                return []

            soup = BeautifulSoup(html, 'html.parser')

            results = []
            # Updated selector for the provided HTML structure
            for item in soup.select('li'):
                time_elem = item.select_one('.time')
                title_elem = item.select_one('.film-name')
                link_elem = item.select_one('a.tsl-link')

                if title_elem and link_elem:
                    href = link_elem.get('href')
                    anime_id = href.split('/')[-1].split('?')[0]
                    results.append({
                        'id': anime_id,
                        'title': title_elem.text.strip(),
                        'time': time_elem.text.strip() if time_elem else "Unknown"
                    })
            return results
    except Exception as e:
        print(f"Error fetching schedule: {e}")
    return []

def fetch_recently_updated():
    try:
        session = c_requests.Session()
        proxy_dict = get_proxy_dict(get_random_proxy())
        if proxy_dict:
            session.proxies.update(proxy_dict)
        results = []

        # Try fetching from home page first
        home_url = f"{BASE_URL}/home"
        resp = session.get(home_url, headers=HEADERS, impersonate="chrome")
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            latest_ep_heading = soup.find('h2', string='Latest Episode')
            if latest_ep_heading:
                section = latest_ep_heading.find_parent('section')
                if section:
                    for item in section.select('.flw-item'):
                        title_elem = item.select_one('.film-name a')
                        if not title_elem:
                            continue
                        title = title_elem.get('title') or title_elem.text.strip()
                        href = title_elem.get('href')
                        anime_id = href.split('/')[-1].split('?')[0]
                        full_url = f"{BASE_URL}{href}" if href.startswith('/') else f"{BASE_URL}/{href}"
                        results.append({
                            'title': title,
                            'id': anime_id,
                            'url': full_url
                        })

        # Fallback to recently-updated if home page parsing failed or returned empty
        if not results:
            print("Could not find Latest Episodes on home page, falling back to /recently-updated")
            fallback_url = f"{BASE_URL}/recently-updated"
            resp = session.get(fallback_url, headers=HEADERS, impersonate="chrome")
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for item in soup.select('.film_list-wrap .flw-item'):
                    title_elem = item.select_one('.film-name a')
                    if not title_elem:
                        continue
                    title = title_elem.get('title') or title_elem.text.strip()
                    href = title_elem.get('href')
                    anime_id = href.split('/')[-1].split('?')[0]
                    full_url = f"{BASE_URL}{href}" if href.startswith('/') else f"{BASE_URL}/{href}"
                    results.append({
                        'title': title,
                        'id': anime_id,
                        'url': full_url
                    })

        return results
    except Exception as e:
        print(f"Error fetching recently updated: {e}")
        return []

async def check_and_download_ongoing(client: Client, chat_id: int):
    print("Checking for recently updated anime...")
    recent_animes = await asyncio.to_thread(fetch_recently_updated)

    downloader = cantarellatvDownloader()

    # 0. Fetch the schedule to ONLY process scheduled anime
    scheduled_data = await asyncio.to_thread(fetch_schedule_list)
    scheduled_ids = {item['id'] for item in scheduled_data}

    for idx, anime in enumerate(recent_animes):
        try:
            entries = await asyncio.to_thread(downloader.list_episodes, anime['url'])
            if not entries:
                print(f"Waiting for episode: {anime['title']} (Anime page exists, but no episodes listed yet)")
                continue

            # Usually the latest episode is the last one in the list
            latest_ep = entries[-1]
            ep_url = latest_ep['url']

            # Use episode number or ID for identifier to prevent re-downloads when title changes
            ep_num = latest_ep.get('ep_number')
            ep_id = latest_ep.get('ep_id')
            if ep_num and ep_id:
                ep_identifier = f"{anime['id']}_{ep_num}_{ep_id}"
            else:
                ep_identifier = f"{anime['id']}_{latest_ep.get('title', 'Unknown')}"

            old_ep_identifier = f"{anime['id']}_{latest_ep.get('title', 'Unknown')}"

            is_new_processed = await db.is_processed(ep_identifier)
            is_old_processed = await db.is_processed(old_ep_identifier)

            if is_new_processed or is_old_processed:
                # Ensure the new identifier is also marked as processed if the old one was
                if is_old_processed and not is_new_processed:
                    await db.mark_processed(ep_identifier)
                continue

            print(f"New episode found: {anime['title']} - {latest_ep.get('title', 'Unknown')}")

            # Clean title for better AniList searching (remove extra spaces)
            clean_search_title = re.sub(r'\s+', ' ', anime['title']).strip()

            # Metadata Correction using AniList
            te = TextEditor(clean_search_title)
            await te.load_anilist()
            data = te.adata

            # 1. Strict Schedule check as requested
            is_scheduled = anime['id'] in scheduled_ids

            country_of_origin = data.get("countryOfOrigin", "")
            is_chinese = country_of_origin == "CN"

            if is_chinese and not is_scheduled:
                print(f"⏭️ Skipping unscheduled Chinese anime (Donghua): {anime['title']}")
                await db.mark_processed(ep_identifier)
                continue

            # User requested ONLY English name for filenames and search to avoid errors
            romaji_title = data.get('title', {}).get('romaji')
            english_title = data.get('title', {}).get('english')

            # Prioritize English title as requested
            anime_name = english_title or romaji_title or anime['title']

            if not (romaji_title or english_title):
                    # Clean up trailing number from fallback name if it was likely a season
                    anime_name = re.sub(r'\s+\d+$', '', anime_name).strip()

            ani_season = "1"
            ani_ep_num = "0"

            # 1. Try extracting numeric season from HiAnime title first (most reliable for "Season X" or trailing numbers)
            # Catch "Season 5" or "Anime 5" (common for Chinese/Donghua on HiAnime)
            match_s = re.search(r'Season (\d+)', anime['title'], re.I)
            if not match_s:
                 # Check for trailing number in the title (e.g. "Yong Sheng 5")
                 match_s = re.search(r'\s+(\d+)$', anime['title'])

            if match_s:
                ani_season = match_s.group(1)
            else:
                # 2. Try guessit from TextEditor (pdata)
                te_season = te.pdata.get('anime_season')
                if te_season:
                    ani_season = str(te_season)
                else:
                    # 3. Fallback to AniList data
                    match_s2 = re.search(r'Season (\d+)', anime_name, re.I)
                    if match_s2:
                        ani_season = match_s2.group(1)

            # 4. Extract Episode number
            if data.get('nextAiringEpisode'):
                # This works if the episode just aired and is the next expected one
                ani_ep_num = str(data['nextAiringEpisode']['episode'] - 1)
            else:
                # Fallback to parsing the episode list entry title
                match_ep = re.search(r'Episode (\d+)', latest_ep.get('title', ''))
                if match_ep:
                    ani_ep_num = match_ep.group(1)
                else:
                    # Try guessit on the entry title
                    from guessit import guessit
                    g = guessit(latest_ep.get('title', ''))
                    if g.get('episode'):
                        ani_ep_num = str(g['episode'])

            # Manual Fixes for specific anime if needed (e.g. Dr. Stone)
            if "Dr. Stone" in anime_name:
                if "New World" in anime['title']:
                    ani_season = "3"
                if "Science Future" in anime['title'] or "Season 4" in anime['title']:
                    ani_season = "4"

            # Send a starting message to edit (in LOG_CHANNEL if set)

            log_id = int(LOG_CHANNEL) if LOG_CHANNEL else chat_id
            anime_name_sc = anime_name
            status_msg = await client.send_message(log_id, f"<blockquote>🔄 ᴀᴜᴛᴏ-ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ɴᴇᴡ ᴇᴘɪꜱᴏᴅᴇ: {anime_name_sc} - ꜱ{ani_season}ᴇ{ani_ep_num}...</blockquote>", parse_mode=ParseMode.HTML)

            # Use the existing download logic (downloading to TARGET_CHAT_ID)
            # quality="all" will download 360p, 720p, 1080p sequentially
            uploaded_msgs = await _handle_download(
                client, status_msg, ep_url, status_msg,
                is_playlist=False, quality="all", chat_id=chat_id,
                name_override=anime_name,
                season_override=str(ani_season),
                ep_num_override=str(ani_ep_num) if ani_ep_num else None
            )

            if uploaded_msgs:
                # Create a quality map for the main channel
                quality_map = {}
                for msg in uploaded_msgs:
                    match = re.search(r'\[(\d+p)\]', msg.caption or "")
                    if match:
                        quality_map[match.group(1)] = msg.id

                await post_to_main_channel(client, ep_url, uploaded_msgs, quality_map)

            # Mark as processed
            await db.mark_processed(ep_identifier)

        except Exception as e:
            print(f"Error processing {anime['title']}: {e}")

async def ongoing_task(client: Client):
    if not TARGET_CHAT_ID:
        print("WARNING: TARGET_CHAT_ID is not set in environment or config.py. Ongoing auto-downloads are disabled.")
        return

    try:
        target_chat_id = int(TARGET_CHAT_ID)
    except ValueError:
        print("WARNING: TARGET_CHAT_ID must be a valid integer chat ID. Ongoing auto-downloads are disabled.")
        return

    print(f"Starting ongoing checker. Interval: {SET_INTERVAL}s, Target Chat: {target_chat_id}")

    while True:
        ongoing_enabled = await db.get_user_setting(0, "ongoing_enabled", False)
        if ongoing_enabled:
            try:
                await check_and_download_ongoing(client, target_chat_id)
            except Exception as e:
                print(f"Error in ongoing task loop: {e}")
        else:
            pass  # Paused via /settings, loop stays alive

        await asyncio.sleep(SET_INTERVAL)
