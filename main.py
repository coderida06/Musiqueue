import customtkinter as ctk
import threading
import time
from collections import deque
from urllib.parse import quote, urlparse, parse_qs

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# SETUP
# =========================

ctk.set_appearance_mode("dark")

queue = deque()
skip_flag = threading.Event()
stop_flag = threading.Event()

options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.add_argument("--start-maximized")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

driver = webdriver.Chrome(options=options)

driver.execute_cdp_cmd(
    "Page.addScriptToEvaluateOnNewDocument",
    {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
)

driver.get("https://www.youtube.com")
time.sleep(2)


# =========================
# UI HELPERS
# =========================

def refresh_queue():
    queue_box.configure(state="normal")
    queue_box.delete("1.0", "end")
    if not queue:
        queue_box.insert("end", "  ✨  nothing queued yet — throw something in!")
    for i, song in enumerate(queue, start=1):
        queue_box.insert("end", f"  {i:>2}.  {song}\n")
        line_range = (f"{i}.0", f"{i}.end")
        if i == 1:
            queue_box.tag_add("next_up", *line_range)
        else:
            queue_box.tag_add("queued", *line_range)
    try:
        queue_box.tag_config("next_up", foreground=NEON_GREEN)
        queue_box.tag_config("queued", foreground=TEXT_LIGHT)
    except Exception:
        pass
    queue_box.configure(state="disabled")


def add_songs():
    songs = entry.get()
    added = False
    for song in songs.split(","):
        song = song.strip()
        if song:
            queue.append(song)
            added = True
    entry.delete(0, "end")
    refresh_queue()
    if added:
        pulse_button(add_btn, NEON_GREEN)


def skip_song():
    skip_flag.set()
    pulse_button(skip_btn, NEON_ORANGE)


def pulse_button(btn, color):
    original = btn.cget("fg_color")
    btn.configure(fg_color=color)
    app.after(180, lambda: btn.configure(fg_color=original))


# =========================
# YOUTUBE LOGIC
# =========================

def get_video_id(url):
    """Extract the v= param from a YouTube URL."""
    try:
        return parse_qs(urlparse(url).query).get("v", [None])[0]
    except Exception:
        return None


def dismiss_consent():
    try:
        btn = WebDriverWait(driver, 4).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[.//span[contains(text(),'Accept')]]")
            )
        )
        btn.click()
        time.sleep(1)
    except Exception:
        pass


def search_and_open(song):
    url = "https://www.youtube.com/results?search_query=" + quote(song)
    driver.get(url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a#video-title"))
        )
    except Exception:
        return False

    videos = driver.find_elements(By.CSS_SELECTOR, "a#video-title")
    if not videos:
        return False

    video_url = videos[0].get_attribute("href")
    if not video_url:
        return False

    driver.get(video_url)
    return True


def wait_for_playback_start(timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if skip_flag.is_set():
            return False
        try:
            state = driver.execute_script("""
                let v = document.querySelector('video');
                if (!v)                                     return 'no_video';
                if (v.error)                                return 'error';
                if (v.currentTime > 0 && !v.paused)        return 'playing';
                return 'loading';
            """)
            if state == 'playing':
                return True
            if state == 'error':
                return False
        except Exception:
            return False
        time.sleep(0.5)
    return False


def wait_until_video_ends(expected_video_id):
    """
    Poll until:
      - video.ended       → natural end
      - video.error       → playback error
      - URL video ID changes → YouTube autoplayed something else
      - skip_flag set     → user skipped
    """
    while True:
        if skip_flag.is_set():
            skip_flag.clear()
            return

        # ── Autoplay guard ──────────────────────────────────────
        try:
            current_id = get_video_id(driver.current_url)
            if current_id and current_id != expected_video_id:
                return
        except Exception:
            return

        # ── Playback state ──────────────────────────────────────
        try:
            state = driver.execute_script("""
                let v = document.querySelector('video');
                if (!v)       return 'no_video';
                if (v.error)  return 'error';
                if (v.ended)  return 'ended';
                return 'playing';
            """)
            if state in ("ended", "error", "no_video"):
                return
        except Exception:
            return

        time.sleep(1)


def set_status(text, color=None):
    def _update():
        current_song.set(text)
        if color:
            status_label.configure(text_color=color)
    app.after(0, _update)


def play_song(song):
    set_status(f"🔍 Searching: {song}", NEON_PURPLE)

    if not search_and_open(song):
        set_status(f"❌ Not found: {song}", NEON_RED)
        time.sleep(2)
        return

    set_status(f"⏳ Loading: {song}", NEON_ORANGE)

    if not wait_for_playback_start():
        skip_flag.clear()
        set_status(f"⚠️ Skipped (error): {song}", NEON_RED)
        time.sleep(1)
        return

    # Lock in the video ID we actually navigated to
    expected_video_id = get_video_id(driver.current_url)

    set_status(f"▶ Playing: {song}", NEON_GREEN)
    wait_until_video_ends(expected_video_id)


# =========================
# PLAYER LOOP
# =========================

def player_loop():
    dismiss_consent()

    while not stop_flag.is_set():
        if queue:
            song = queue.popleft()
            app.after(0, refresh_queue)
            try:
                play_song(song)
            except Exception:
                import traceback
                traceback.print_exc()
        else:
            set_status("⏸ Waiting for songs...", TEXT_MUTED)
            time.sleep(1)


# =========================
# GUI — funky neon theme
# =========================

BG          = "#0d0d1a"
CARD_BG     = "#181830"
INPUT_BG    = "#20203f"
TEXT_LIGHT  = "#f5f5ff"
TEXT_MUTED  = "#9a9ac2"

NEON_PINK   = "#ff2ea6"
NEON_CYAN   = "#00f0ff"
NEON_PURPLE = "#a742ff"
NEON_GREEN  = "#39ff8f"
NEON_ORANGE = "#ff9f1c"
NEON_RED    = "#ff4d6d"

GLOW_CYCLE = [NEON_PINK, NEON_PURPLE, NEON_CYAN, NEON_GREEN, NEON_ORANGE]

app = ctk.CTk()
app.geometry("840x720")
app.title("YT Queue Player")
app.configure(fg_color=BG)

# ---- Header ----
header = ctk.CTkFrame(app, fg_color="transparent")
header.pack(pady=(26, 8), fill="x")

ctk.CTkLabel(
    header,
    text="🎧 MUSIQUEUE ",
    font=("Arial Black", 30, "bold"),
    text_color=NEON_PINK
).pack()

ctk.CTkLabel(
    header,
    text="search  •  queue  •  vibe",
    font=("Arial", 12, "italic"),
    text_color=NEON_CYAN
).pack(pady=(2, 0))

# ---- Now Playing glowing card ----
now_playing_card = ctk.CTkFrame(
    app, fg_color=CARD_BG, corner_radius=20,
    border_width=3, border_color=NEON_CYAN
)
now_playing_card.pack(pady=18, padx=28, fill="x")

ctk.CTkLabel(
    now_playing_card,
    text="⚡ NOW PLAYING ⚡",
    font=("Arial", 13, "bold"),
    text_color=NEON_CYAN
).pack(pady=(14, 4))

current_song = ctk.StringVar(value="⏸ Waiting for songs...")

status_label = ctk.CTkLabel(
    now_playing_card,
    textvariable=current_song,
    font=("Arial", 19, "bold"),
    text_color=TEXT_MUTED,
    wraplength=720,
    justify="center"
)
status_label.pack(pady=(0, 18), padx=18)

# animate the card border cycling through neon colors for extra funk
_glow_index = 0
def animate_glow():
    global _glow_index
    now_playing_card.configure(border_color=GLOW_CYCLE[_glow_index % len(GLOW_CYCLE)])
    _glow_index += 1
    app.after(900, animate_glow)

# ---- Queue card ----
queue_card = ctk.CTkFrame(app, fg_color=CARD_BG, corner_radius=20)
queue_card.pack(pady=8, padx=28, fill="both", expand=True)

ctk.CTkLabel(
    queue_card,
    text="📜 UP NEXT",
    font=("Arial", 15, "bold"),
    text_color=NEON_PINK
).pack(pady=(14, 6), anchor="w", padx=20)

queue_box = ctk.CTkTextbox(
    queue_card,
    fg_color=INPUT_BG,
    text_color=TEXT_LIGHT,
    corner_radius=14,
    font=("Consolas", 14),
    state="disabled",
    wrap="word"
)
queue_box.pack(pady=(0, 18), padx=20, fill="both", expand=True)
refresh_queue()

# ---- Input row ----
input_row = ctk.CTkFrame(app, fg_color="transparent")
input_row.pack(pady=(4, 8), padx=28, fill="x")

entry = ctk.CTkEntry(
    input_row,
    placeholder_text="search songs",
    fg_color=INPUT_BG,
    border_color=NEON_PURPLE,
    border_width=2,
    corner_radius=14,
    height=44,
    font=("Arial", 13)
)
entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
entry.bind("<Return>", lambda e: add_songs())

add_btn = ctk.CTkButton(
    input_row,
    text="➕ ADD",
    command=add_songs,
    fg_color=NEON_GREEN,
    hover_color="#22cc6e",
    text_color="#0b0b17",
    font=("Arial", 14, "bold"),
    corner_radius=14,
    height=44,
    width=100
)
add_btn.pack(side="left")

# ---- Action row ----
action_row = ctk.CTkFrame(app, fg_color="transparent")
action_row.pack(pady=(0, 10))

skip_btn = ctk.CTkButton(
    action_row,
    text="⏭ SKIP",
    command=skip_song,
    fg_color=NEON_ORANGE,
    hover_color="#e08800",
    text_color="#0b0b17",
    font=("Arial", 14, "bold"),
    corner_radius=14,
    height=42,
    width=160
)
skip_btn.pack()

# =========================
# START
# =========================

threading.Thread(target=player_loop, daemon=True).start()
app.after(900, animate_glow)
app.mainloop()

stop_flag.set()
driver.quit()
