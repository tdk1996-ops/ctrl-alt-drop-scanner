#!/usr/bin/env python3
"""
Apple Music Playlist Telegram Scanner
Scans an Apple Music playlist (like CTRL+ALT+DROP) and sends a notification
to a Telegram channel when 10+ songs are added.
"""

import os
import sys
import json
import time
import re
import argparse
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

# Ensure utf-8 output on Windows terminals
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_env_file(filepath=".env"):
    """Simple zero-dependency .env file loader."""
    if not os.path.exists(filepath):
        return {}
    env_vars = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                env_vars[key] = val
    return env_vars


def get_config():
    """Load configuration from environment or .env file."""
    # Look for .env in current directory or script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, ".env")
    if not os.path.exists(env_path):
        env_path = ".env"

    file_env = load_env_file(env_path)

    def env(key, default=""):
        return os.environ.get(key, file_env.get(key, default))

    return {
        "PLAYLIST_URL": env("PLAYLIST_URL", ""),
        "TELEGRAM_BOT_TOKEN": env("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": env("TELEGRAM_CHAT_ID", ""),
        "THRESHOLD": int(env("THRESHOLD", "1")),
        "SCAN_INTERVAL_MINUTES": int(env("SCAN_INTERVAL_MINUTES", "30")),

        "STATE_FILE": env("STATE_FILE", os.path.join(script_dir, "state.json")),
    }


def fetch_playlist_html(url):
    """Fetch the Apple Music playlist web page."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP Error {e.code}: {e.reason} when accessing {url}")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch playlist: {e}")


def parse_playlist(html, default_url=""):
    """
    Extract playlist metadata and tracklist from Apple Music HTML.
    Returns:
        dict: {
            "name": str,
            "song_count": int,
            "tracks": list of dicts [{"id", "title", "artist"}],
            "url": str
        }
    """
    # 1. Playlist Name
    title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html)
    name = title_match.group(1) if title_match else "Apple Music Playlist"
    # Clean standard suffixes like " by ... on Apple Music"
    if " by " in name and " on Apple Music" in name:
        name = name.split(" by ")[0]
    elif " on Apple Music" in name:
        name = name.replace(" on Apple Music", "")

    # 2. Canonical or OG URL
    url_match = re.search(r'<meta\s+property=["\']og:url["\']\s+content=["\'](.*?)["\']', html)
    playlist_url = url_match.group(1) if url_match else default_url

    # 3. Song Count from meta tags
    song_count = None
    count_meta = re.search(r'<meta\s+property=["\']music:song_count["\']\s+content=["\'](\d+)["\']', html)
    if count_meta:
        song_count = int(count_meta.group(1))

    if song_count is None:
        # Fallback to description: "Playlist · 42 Songs" or "... 42 Songs."
        desc_match = re.search(r'<meta\s+(?:property=["\']og:description["\']|name=["\']description["\'])\s+content=["\'][^"\']*?(\d+)\s+Songs?', html)
        if desc_match:
            song_count = int(desc_match.group(1))

    # 4. Extract individual tracks and song URLs
    tracks = []
    seen_ids = set()

    # Pre-parse meta songs for fallback URLs
    meta_songs = re.findall(r'<meta\s+property=["\']music:song["\']\s+content=["\'](.*?)["\']', html)
    meta_url_map = {}
    for ms in meta_songs:
        tid = ms.rstrip("/").split("/")[-1]
        meta_url_map[tid] = ms

    script_match = re.search(
        r'<script\s+type=["\']application/json["\']\s+id=["\']serialized-server-data["\']>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if script_match:
        try:
            raw_data = json.loads(script_match.group(1))
            data_arr = raw_data.get("data", [])
            for entry in data_arr:
                inner_data = entry.get("data", {})
                for section in inner_data.get("sections", []):
                    if section.get("itemKind") == "trackLockup":
                        for item in section.get("items", []):
                            cd = item.get("contentDescriptor", {})
                            identifiers = cd.get("identifiers", {})
                            adam_id = str(identifiers.get("storeAdamID", ""))
                            track_id = item.get("id") or adam_id
                            title = item.get("title") or "Unknown Title"
                            artist = item.get("artistName") or "Unknown Artist"

                            # Direct song URL
                            song_url = cd.get("url") or meta_url_map.get(adam_id) or ""
                            if not song_url and adam_id:
                                song_url = f"https://music.apple.com/song/{adam_id}"

                            # Create a unique key
                            unique_key = track_id if track_id else f"{title} - {artist}"
                            if unique_key not in seen_ids:
                                seen_ids.add(unique_key)
                                tracks.append({
                                    "id": unique_key,
                                    "title": title,
                                    "artist": artist,
                                    "url": song_url,
                                })
        except Exception:
            pass

    # 5. Fallback for tracks using <meta property="music:song">
    if not tracks:
        for link in meta_songs:
            track_id = link.rstrip("/").split("/")[-1]
            if track_id not in seen_ids:
                seen_ids.add(track_id)
                tracks.append({
                    "id": track_id,
                    "title": f"Song {track_id}",
                    "artist": "",
                    "url": link,
                })

    # If song_count was still not determined, use tracks length
    if song_count is None:
        song_count = len(tracks)

    return {
        "name": name.strip(),
        "song_count": max(song_count, len(tracks)),
        "tracks": tracks,
        "url": playlist_url,
    }


def send_telegram_message(token, chat_id, message_html, disable_preview=False):
    """Send an HTML-formatted message via the Telegram Bot API."""
    if not token or not chat_id:
        raise ValueError("Telegram Bot Token and Chat ID must be configured.")

    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_preview,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        res_body = resp.read().decode("utf-8")
        return json.loads(res_body)


def get_telegram_updates(token):
    """Retrieve recent updates to inspect chat IDs for easy setup."""
    if not token:
        raise ValueError("Telegram Bot Token is required.")
    endpoint = f"https://api.telegram.org/bot{token}/getUpdates"
    req = urllib.request.Request(endpoint, headers={"User-Agent": "Scanner"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_state(filepath):
    """Load persistent scanner state."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not read state file ({e}). Starting fresh.")
    return None


def save_state(filepath, state):
    """Save scanner state safely to disk."""
    dir_name = os.path.dirname(filepath)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    # Atomic replace
    if os.path.exists(filepath):
        os.replace(tmp_path, filepath)
    else:
        os.rename(tmp_path, filepath)


def build_alert_message(playlist_name, playlist_url, added_count, total_count, new_tracks=None):
    """Construct a clean, engaging Telegram HTML notification."""
    now_str = datetime.now().strftime("%b %d, %Y - %I:%M %p")
    header_alert = (
        "🔥 <b>New track added!</b>"
        if added_count == 1
        else f"🔥 <b>+{added_count} new songs added!</b>"
    )
    msg = [
        f"🎧 <b>{playlist_name} Update!</b> 🎧",
        f"<i>{now_str}</i>\n",
        header_alert,
        f"📊 <b>Total tracks:</b> {total_count} songs\n",
    ]

    if new_tracks and len(new_tracks) > 0:
        msg.append("<b>🎵 Newly Added Tracks:</b>")
        preview_tracks = new_tracks[:20]
        for t in preview_tracks:
            title = t.get("title", "Unknown")
            artist = t.get("artist", "")
            song_url = t.get("url", "")
            artist_part = f" — {artist}" if artist else ""
            if song_url:
                msg.append(f'• <a href="{song_url}"><b>{title}</b></a>{artist_part}')
            else:
                msg.append(f"• <b>{title}</b>{artist_part}")

        if len(new_tracks) > 20:
            msg.append(f"<i>...and {len(new_tracks) - 20} more tracks</i>")
        msg.append("")

    msg.append(f'📁 <b>Full Playlist:</b>\n<a href="{playlist_url}">{playlist_url}</a>')
    return "\n".join(msg)


def run_scan(config, dry_run=False, force_alert=False, init_only=False):
    """
    Execute a single scan cycle.
    Returns:
        dict: summary of scan results
    """
    url = config.get("PLAYLIST_URL")
    if not url:
        raise ValueError("PLAYLIST_URL is not set. Please add it to your .env file.")

    threshold = config.get("THRESHOLD", 1)

    state_file = config.get("STATE_FILE", "state.json")
    bot_token = config.get("TELEGRAM_BOT_TOKEN")
    chat_id = config.get("TELEGRAM_CHAT_ID")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scanning playlist...")
    html = fetch_playlist_html(url)
    data = parse_playlist(html, default_url=url)

    playlist_name = data["name"]
    current_count = data["song_count"]
    tracks = data["tracks"]

    print(f"Playlist: '{playlist_name}'")
    print(f"Current song count: {current_count} (parsed {len(tracks)} track details)")

    state = load_state(state_file)

    if state is None or init_only:
        # First-time initialization
        new_state = {
            "playlist_name": playlist_name,
            "playlist_url": url,
            "last_notified_count": current_count,
            "last_notified_time": datetime.now().isoformat(),
            "known_track_ids": [t["id"] for t in tracks],
            "last_seen_count": current_count,
            "last_scan_time": datetime.now().isoformat(),
        }
        if not dry_run:
            save_state(state_file, new_state)
        print(f"✅ Baseline established with {current_count} songs.")
        print(f"Next alert will trigger when {threshold}+ new songs are added (at {current_count + threshold} songs).")
        return {
            "action": "initialized",
            "current_count": current_count,
            "threshold": threshold,
        }

    last_count = state.get("last_notified_count", current_count)
    known_ids = set(state.get("known_track_ids", []))

    # Calculate newly added tracks
    new_tracks = [t for t in tracks if t["id"] not in known_ids]
    new_by_ids = len(new_tracks)
    new_by_count = max(0, current_count - last_count)
    added_count = max(new_by_ids, new_by_count)

    print(f"Last notified count: {last_count}")
    print(f"New songs accumulated: {added_count} / {threshold} needed")

    # Update latest scan metadata in state
    state["last_seen_count"] = current_count
    state["last_scan_time"] = datetime.now().isoformat()
    state["playlist_name"] = playlist_name

    should_alert = (added_count >= threshold) or force_alert

    if should_alert:
        print(f"🚀 Trigger condition met! (+{added_count} songs >= threshold {threshold})")
        msg = build_alert_message(
            playlist_name=playlist_name,
            playlist_url=url,
            added_count=added_count,
            total_count=current_count,
            new_tracks=new_tracks if new_tracks else None,
        )

        if dry_run:
            print("\n--- [DRY RUN] Telegram Message Preview ---")
            print(msg)
            print("------------------------------------------\n")
        else:
            if not bot_token or not chat_id:
                print("❌ Cannot send Telegram notification: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing!")
            else:
                print("Sending notification to Telegram channel...")
                resp = send_telegram_message(bot_token, chat_id, msg)
                if resp.get("ok"):
                    print("✅ Notification successfully sent to Telegram!")
                else:
                    print(f"❌ Telegram API Error: {resp}")

            # Advance baseline
            state["last_notified_count"] = current_count
            state["last_notified_time"] = datetime.now().isoformat()
            # Merge known tracks
            current_ids = set(state.get("known_track_ids", []))
            for t in tracks:
                current_ids.add(t["id"])
            state["known_track_ids"] = list(current_ids)
            save_state(state_file, state)

        return {
            "action": "alerted",
            "added_count": added_count,
            "total_count": current_count,
        }
    else:
        # Still below threshold
        needed = threshold - added_count
        print(f"⏳ Waiting for {needed} more song{'s' if needed != 1 else ''} to trigger notification.")
        # If tracks were parsed, we can remember their IDs so we track them progressively
        current_ids = set(state.get("known_track_ids", []))
        for t in tracks:
            current_ids.add(t["id"])
        state["known_track_ids"] = list(current_ids)
        if not dry_run:
            save_state(state_file, state)

        return {
            "action": "pending",
            "added_count": added_count,
            "needed": needed,
            "total_count": current_count,
        }


def run_daemon_loop(config):
    """Run scanner continuously at the configured interval."""
    interval_sec = config.get("SCAN_INTERVAL_MINUTES", 30) * 60
    print(f"🔄 Starting background scanner daemon. Checking every {config.get('SCAN_INTERVAL_MINUTES', 30)} minutes.")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            run_scan(config)
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error during scan: {e}")

        print(f"Sleeping for {config.get('SCAN_INTERVAL_MINUTES', 30)} minutes...\n")
        time.sleep(interval_sec)


def main():
    parser = argparse.ArgumentParser(description="Apple Music Playlist Scanner for Telegram")
    parser.add_argument("--check", action="store_true", help="Run a single check now")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in the background")
    parser.add_argument("--init", action="store_true", help="Initialize or reset baseline without sending an alert")
    parser.add_argument("--dry-run", action="store_true", help="Scan and simulate alert without sending to Telegram")
    parser.add_argument("--force-alert", action="store_true", help="Force send an alert message regardless of threshold")
    parser.add_argument("--test-telegram", action="store_true", help="Send a simple test message to verify Telegram bot setup")
    parser.add_argument("--get-chat-id", action="store_true", help="Inspect Telegram bot updates to find your channel or chat ID")
    parser.add_argument("--status", action="store_true", help="Display current tracking state")
    parser.add_argument("--threshold", type=int, default=None, help="Override threshold of songs")
    parser.add_argument("--interval", type=int, default=None, help="Override scan interval in minutes")
    parser.add_argument("--url", type=str, default=None, help="Override playlist URL")

    args = parser.parse_args()
    config = get_config()

    if args.threshold is not None:
        config["THRESHOLD"] = args.threshold
    if args.interval is not None:
        config["SCAN_INTERVAL_MINUTES"] = args.interval
    if args.url:
        config["PLAYLIST_URL"] = args.url

    # Action 1: Discover Chat ID
    if args.get_chat_id:
        token = config.get("TELEGRAM_BOT_TOKEN")
        if not token:
            print("❌ TELEGRAM_BOT_TOKEN is not set in .env! Please set it first.")
            sys.exit(1)
        print("Fetching recent updates from Telegram Bot API...")
        try:
            updates = get_telegram_updates(token)
            results = updates.get("result", [])
            if not results:
                print("No recent messages found. Please post a message in your Telegram channel or DM the bot, then run this command again.")
            else:
                print(f"Found {len(results)} recent update(s):\n")
                for u in results[-5:]:
                    chat = None
                    if "channel_post" in u:
                        chat = u["channel_post"].get("chat", {})
                        text = u["channel_post"].get("text", "")
                        print(f"📢 Channel Post: ID={chat.get('id')} | Title='{chat.get('title')}' | Username=@{chat.get('username')} | Text='{text}'")
                    elif "message" in u:
                        chat = u["message"].get("chat", {})
                        text = u["message"].get("text", "")
                        print(f"💬 Direct/Group Message: ID={chat.get('id')} | Type={chat.get('type')} | Name='{chat.get('title') or chat.get('first_name')}' | Text='{text}'")
                print("\n👉 Copy the negative number (e.g. -100xxxxxxxxxx) or @username and put it in TELEGRAM_CHAT_ID in .env")
        except Exception as e:
            print(f"Error fetching updates: {e}")
        return

    # Action 2: Test Telegram
    if args.test_telegram:
        token = config.get("TELEGRAM_BOT_TOKEN")
        chat_id = config.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            print("❌ TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing from .env!")
            sys.exit(1)
        test_msg = (
            "✅ <b>Apple Music Scanner Connection Test</b>\n\n"
            "Your Telegram Bot is successfully connected! You will receive notifications here when 10+ new songs are added to your playlist."
        )
        print(f"Sending test message to {chat_id}...")
        try:
            res = send_telegram_message(token, chat_id, test_msg)
            if res.get("ok"):
                print("🎉 Success! Test message sent successfully.")
            else:
                print(f"❌ Telegram Error: {res}")
        except Exception as e:
            print(f"❌ Error sending test message: {e}")
        return

    # Action 3: Status
    if args.status:
        state = load_state(config.get("STATE_FILE", "state.json"))
        if not state:
            print("No state file found. Run with --init or --check to start tracking.")
        else:
            print("📊 Current Scanner State:")
            print(f"  Playlist Name: {state.get('playlist_name')}")
            print(f"  Playlist URL: {state.get('playlist_url')}")
            print(f"  Last Notified Count: {state.get('last_notified_count')}")
            print(f"  Last Notified Time: {state.get('last_notified_time')}")
            print(f"  Known Track IDs count: {len(state.get('known_track_ids', []))}")
            print(f"  Last Scan Time: {state.get('last_scan_time')}")
            print(f"  Configured Threshold: {config.get('THRESHOLD')}")
        return

    # Action 4: Run scan or daemon
    if args.daemon:
        run_daemon_loop(config)
    else:
        # Default is single check
        try:
            run_scan(
                config,
                dry_run=args.dry_run,
                force_alert=args.force_alert,
                init_only=args.init,
            )
        except Exception as e:
            print(f"❌ Scan failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
