# 🎧 Apple Music Playlist Scanner to Telegram

Automated scanner for your shared Apple Music playlist (e.g. **CTRL+ALT+DROP 2.5**). Whenever **any new song is added**, it automatically sends an update with direct individual links to the newly added songs and the full playlist directly to your **Telegram channel**.

---

## ✨ Features

- **No Apple Developer Account or API Keys Required**: Seamlessly parses public/shared Apple Music playlist pages without needing a \$99/year developer membership.
- **Instant Drop Alerts**: Configured to alert after **any** newly added song (threshold = 1), or any custom threshold you choose.
- **Individual Clickable Song Links**: Each newly dropped track includes a direct clickable link to that specific song in Apple Music for instant previewing/downloading.
- **BPM & Key Annotations (with Camelot Notation)**: Optional automatic lookup for Tempo (BPM), Musical Key, and Camelot wheel notation (e.g. `⚡ 128 BPM • 11A (F#m)`) powered by GetSongBPM.
- **Smart Accumulative Delta Tracking**: Accurately tracks additions and deduplicates songs by Apple Music track ID.


- **Rich Telegram Drop Alert**:
  - Displays playlist name & direct Apple Music link.
  - Shows total track count and count of new additions.
  - Includes a bulleted list of the newly added song titles & artist names so you and your friend know exactly what to download.
- **Zero External Dependencies**: Built entirely with Python's standard library. Works immediately on Python 3.8+ with no `pip install` needed.
- **Flexible Execution**:
  - **Local Daemon Mode**: Keep it running in the background.
  - **Windows Task Scheduler**: One-click setup to check silently every 30 minutes.
  - **GitHub Actions (Cloud)**: Run 24/7 in the cloud for free with no computer left on.

---

## 🚀 Quick Setup Guide

### 1. Get your Apple Music Playlist Link
1. Open Apple Music (iPhone, Mac, Windows, or Web).
2. Go to your **CTRL+ALT+DROP** playlist.
3. Tap the **`...`** (options) button $\rightarrow$ **Share Playlist** $\rightarrow$ **Copy Link**.
   - Example URL: `https://music.apple.com/us/playlist/ctrl-alt-drop/pl.u-XXXXX`

---

### 2. Create your Telegram Bot & Channel

#### Step A: Get a Bot Token
1. Open Telegram and search for [`@BotFather`](https://t.me/BotFather).
2. Send `/newbot`.
3. Choose a display name (e.g. `CTRL+ALT+DROP Notifier`) and a bot username (e.g. `ctrl_alt_drop_bot`).
4. `@BotFather` will reply with your **HTTP API Token** (e.g. `7123456789:AAH...`). Copy this.

#### Step B: Create Channel & Add Bot
1. In Telegram, create a **New Channel** (e.g. `CTRL+ALT+DROP Downloads`).
2. Go to the Channel settings $\rightarrow$ **Administrators** $\rightarrow$ **Add Admin**.
3. Search for your bot's username and add it as an administrator (ensure the **"Post Messages"** permission is enabled).

#### Step C: Get your Channel ID
- If your channel is **Public** with a username (like `@ctrl_alt_drop`), your `TELEGRAM_CHAT_ID` is simply `@ctrl_alt_drop`.
- If your channel is **Private**:
  1. Post any message in the channel (e.g. "test").
  2. Put your bot token in `.env`.
  3. Run:
     ```bash
     python scanner.py --get-chat-id
     ```
  4. The script will automatically inspect recent updates and display your channel ID (starts with `-100...`).

---

### 3. Configure `.env`
In this project folder, copy `.env.example` to `.env`:

```bash
cp .env.example .env
```
*(On Windows: copy `.env.example` to `.env`)*

Edit `.env` with your values:
```ini
PLAYLIST_URL=https://music.apple.com/us/playlist/ctrl-alt-drop/pl.u-XXXXXXXX
TELEGRAM_BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=@your_channel_or_id
THRESHOLD=10
SCAN_INTERVAL_MINUTES=30
```

---

### 4. Verify the Connection

Test your Telegram bot setup:
```bash
python scanner.py --test-telegram
```
You should instantly see a test message appear in your Telegram channel!

Test the Apple Music playlist scanner with a dry-run (won't affect state or send spam):
```bash
python scanner.py --dry-run
```

---

## ⚙️ How to Run

### Option 1: Silent Windows Task Scheduler (Recommended for Windows)
Double-click `setup_windows_task.bat` or run:
```cmd
setup_windows_task.bat
```
This registers a scheduled Windows task that silently runs `python scanner.py --check` every 30 minutes in the background without popping up any black command prompt windows.

To remove it later:
```cmd
schtasks /delete /tn "AppleMusicPlaylistScanner" /f
```

---

### Option 2: Run in Terminal / Daemon Mode
Double-click `run_daemon.bat` or run:
```bash
python scanner.py --daemon
```
The script will stay running, check the playlist every 30 minutes (or your configured interval), and notify Telegram when 10+ songs are added.

---

### Option 3: 100% Free Cloud Automation (GitHub Actions)
If you don't want to leave your computer running:
1. Push this folder to a private GitHub repository.
2. Go to repository **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
3. Add the following repository secrets:
   - `PLAYLIST_URL`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. GitHub Actions will automatically scan every 30 minutes via `.github/workflows/scanner.yml` and persist the state back into the repo!

---

## 🛠️ CLI Commands & Flags

| Command | Description |
|---|---|
| `python scanner.py --check` | Run a single scan check now. |
| `python scanner.py --daemon` | Run continuously in the background. |
| `python scanner.py --status` | Display current tracking state and song counts. |
| `python scanner.py --dry-run` | Simulate a scan without sending Telegram messages or saving state. |
| `python scanner.py --force-alert` | Force send an alert message immediately with current tracks. |
| `python scanner.py --test-telegram` | Send a test notification to verify your Telegram Bot. |
| `python scanner.py --get-chat-id` | Auto-detect your Telegram channel ID from recent messages. |
| `python scanner.py --init` | Set current playlist as baseline without alerting. |
| `python scanner.py --threshold 15` | Override threshold count on the fly. |

---

## 📁 Files in this Project

- `scanner.py` — Main scanner engine with zero external dependencies.
- `.env.example` — Configuration template.
- `state.json` — Automatically created; records baseline track counts and track IDs.
- `run_check.bat` — Windows shortcut for a single check.
- `run_daemon.bat` — Windows shortcut to launch continuous scanning.
- `setup_windows_task.bat` — Windows Task Scheduler installer for automatic 30-min background scans.
- `.github/workflows/scanner.yml` — Cloud automation configuration for GitHub Actions.
