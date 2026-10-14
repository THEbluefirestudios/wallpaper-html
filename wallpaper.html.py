#hol up i shuld comment all dis

#import block for not gui stuff
import atexit
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tkinter as tk
import winreg
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
#import block for gui stuff
import darkdetect
import pyautogui
import pystray
import sv_ttk
import webview
import win32con
import win32gui
import win32process
import psutil
import threading
import win32api
from PIL import Image, ImageTk
#do this coz pywinstyles is weird and not always installed, so we need to check if its there first
try:
    import pywinstyles
except ImportError:
    pywinstyles = None
#consts
SCRIPT_DIR = Path(__file__).resolve().parent
INTERNAL_DIR = SCRIPT_DIR / "internal"
WALLPAPERS_DIR = SCRIPT_DIR / "wallpapers"
SETTINGS_FILE = INTERNAL_DIR / "settings.json"
ICON_ICO = INTERNAL_DIR / "icon.ico"
ICON_PNG = INTERNAL_DIR / "icon.png"
READY_FILE = INTERNAL_DIR / "wallpaper_ready"
FIRST_FRAME_DELAY = 1.0
STARTUP_TIMEOUT = 15.0

STARTUP_NAME = "Wallpaper.HTML"
STARTUP_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"

SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()

CURRENT_SCREEN = 0

#objectivel setings u shuld use
DEFAULT_SETTINGS = {
    "current_wallpaper_dir": "",
    "run_on_startup": False,
    "hide_get_premium": False,
    "developer_mode": False,
    "pause_on_fullscreen": True
}

#the same ol' json funcs i use
def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return {**DEFAULT_SETTINGS, **json.load(f)}
    except (OSError, ValueError, TypeError):
        return dict(DEFAULT_SETTINGS)


def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


settings = load_settings()

MANIFEST_RE = re.compile(r"^\s*<!--\s*manifest(.*?)-->", re.DOTALL | re.IGNORECASE)

MANIFEST_DEFAULTS = {
    "name": "Untitled",
    "thumbnail": None,
    "author": "Unknown",
    "description": "",
}

#the "manifest", top 4 lines of wallpaper.html that is commented, ill document this dw
def read_manifest(html_path):
    html_path = Path(html_path)
    text = html_path.read_text(encoding="utf-8-sig")

    manifest = dict(MANIFEST_DEFAULTS)

    match = MANIFEST_RE.match(text)
    if not match:
        return manifest

    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        manifest[key.strip().lower()] = value.strip()
    if manifest["thumbnail"]:
        manifest["thumbnail"] = str((html_path.parent / manifest["thumbnail"]).resolve())

    return manifest

#read wallp dir
def list_wallpapers():
    wallpapers = []
    for folder in sorted(WALLPAPERS_DIR.iterdir()):
        if (folder / "wallpaper.html").is_file():
            manifest = read_manifest(folder / "wallpaper.html")
            if manifest["name"] != "Untitled":
                wallpapers.append({**manifest, "dir": folder.name})
    return wallpapers

# start, stop and pause wallp
wallpaper_process = None
wallpaper_started_at = 0.0
wallpaper_paused = False
process_lock = threading.RLock()


def start_wallpaper():
    global wallpaper_process, wallpaper_started_at
    stop_wallpaper()
    with process_lock:
        READY_FILE.unlink(missing_ok=True)
        wallpaper_started_at = time.monotonic()
        wallpaper_process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--wallpaper"], creationflags=subprocess.CREATE_NO_WINDOW)


def stop_wallpaper():
    global wallpaper_process, wallpaper_paused
    with process_lock:
        if wallpaper_process and wallpaper_process.poll() is None:
            pause_wallpaper(False)
            wallpaper_process.terminate()
            wallpaper_process.wait()
        wallpaper_process = None
        wallpaper_paused = False


def pause_wallpaper(paused):
    global wallpaper_paused # this is needed, shi lags so much when minectaft is open, and also eats a bit of my fps
    with process_lock:
        if not wallpaper_process or wallpaper_process.poll() is not None or paused == wallpaper_paused:
            return
        try:
            root = psutil.Process(wallpaper_process.pid)
            for p in [root] + root.children(recursive=True):
                try:
                    p.suspend() if paused else p.resume()
                except psutil.Error:
                    pass
        except psutil.Error:
            return
        wallpaper_paused = paused


IGNORED_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

#took help of claude using my new credits i bought
#making contstants coz i had trouble tweaking these
COVER_TOLERANCE = 0 #pixles forgiven, like if a window is 1px off the edge, it still counts as covering the desktop
COVER_GRID_COLUMNS = 24 # sample area on x axis
COVER_GRID_ROWS = 14# sample area on y axis
IGNORED_EXTENDED_STYLES = win32con.WS_EX_TRANSPARENT | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW


def is_cloaked(hwnd):
    cloaked = ctypes.c_int(0)
    ctypes.windll.dwmapi.DwmGetWindowAttribute(ctypes.c_void_p(hwnd), 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return cloaked.value != 0


def get_visible_rect(hwnd):
    rect = (ctypes.c_long * 4)()
    if ctypes.windll.dwmapi.DwmGetWindowAttribute(ctypes.c_void_p(hwnd), 9, rect, ctypes.sizeof(rect)) == 0:
        return tuple(rect)
    return win32gui.GetWindowRect(hwnd)


def get_covering_rects():
    process = wallpaper_process
    wallpaper_process_id = process.pid if process else None
    rects = []

    def collect(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                return True
            if win32gui.GetClassName(hwnd) in IGNORED_CLASSES or is_cloaked(hwnd):
                return True
            if win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) & IGNORED_EXTENDED_STYLES:
                return True
            if win32process.GetWindowThreadProcessId(hwnd)[1] == wallpaper_process_id:
                return True
            rects.append(get_visible_rect(hwnd))
        except Exception:
            pass
        return True

    win32gui.EnumWindows(collect, None)
    return rects


def is_desktop_covered():
    monitor = win32api.MonitorFromPoint((0, 0), win32con.MONITOR_DEFAULTTOPRIMARY)
    left, top, right, bottom = win32api.GetMonitorInfo(monitor)["Work"]
    rects = [(rect[0] - COVER_TOLERANCE, rect[1] - COVER_TOLERANCE, rect[2] + COVER_TOLERANCE, rect[3] + COVER_TOLERANCE) for rect in get_covering_rects()]
    if not rects:
        return False
    for column in range(COVER_GRID_COLUMNS):
        x = left + (column + 0.5) * (right - left) / COVER_GRID_COLUMNS
        for row in range(COVER_GRID_ROWS):
            y = top + (row + 0.5) * (bottom - top) / COVER_GRID_ROWS
            if not any(rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3] for rect in rects):
                return False
    return True


def is_wallpaper_ready():
    return READY_FILE.exists() or time.monotonic() - wallpaper_started_at > STARTUP_TIMEOUT


def fullscreen_watcher(): #me watch if fsc app
    while True:
        try:
            want_paused = settings["pause_on_fullscreen"] and is_wallpaper_ready() and is_desktop_covered()
        except Exception:
            want_paused = False
        pause_wallpaper(want_paused)
        time.sleep(1)

def set_wallpaper(name):
    settings["current_wallpaper_dir"] = name
    save_settings()
    if name:
        start_wallpaper()
        
    else:
        stop_wallpaper()


def set_startup(enabled):
    if enabled:
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        exe = pythonw if pythonw.exists() else Path(sys.executable)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, STARTUP_NAME, 0, winreg.REG_SZ, f'"{exe}" "{Path(__file__).resolve()}"')
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, STARTUP_APPROVED_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, STARTUP_NAME, 0, winreg.REG_BINARY, b"\x02" + bytes(11))
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, STARTUP_NAME)
        except FileNotFoundError:
            pass


TITLE = "Wallpaper"

#quick find progman, send that one code, find workerw, also in win11 i think worker w is child of progman, and dis app for win11 and 10, so both methods merged to 1
def get_desktop_parent():
    progman = win32gui.FindWindow("Progman", None)
    win32gui.SendMessageTimeout(progman, 0x052C, 0, 0, win32con.SMTO_NORMAL, 1000)
    child = win32gui.FindWindowEx(progman, 0, "WorkerW", None)
    if child:
        return child
    found = 0

    def enum_cb(hwnd, _):
        nonlocal found
        if win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None):
            found = win32gui.FindWindowEx(0, hwnd, "WorkerW", None)
        return True

    win32gui.EnumWindows(enum_cb, None)
    return found or progman


def attach_to_desktop(window):
    hwnd = 0

    for _ in range(50):
        try:
            hwnd = int(window.native.Handle.ToInt64())
        except Exception:
            hwnd = win32gui.FindWindow(None, TITLE)
        if hwnd and win32gui.IsWindow(hwnd):
            break
        time.sleep(0.1)

    parent = get_desktop_parent()

    if not (hwnd and win32gui.IsWindow(hwnd) and parent and win32gui.IsWindow(parent)):
        print("A handle is invalid, not attaching.")
        window.destroy()
        return
    
    win32gui.SetParent(hwnd, parent)
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    style = (style & ~win32con.WS_POPUP) | win32con.WS_CHILD
    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)

    w = ctypes.windll.user32.GetSystemMetrics(0)
    h = ctypes.windll.user32.GetSystemMetrics(1)
    win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, 0, 0, w, h,  win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)


def run_wallpaper():
    global TITLE
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        '--autoplay-policy=no-user-gesture-required '
        '--host-rules="MAP * ~NOTFOUND, EXCLUDE localhost"'
    )
    html_file = WALLPAPERS_DIR / settings["current_wallpaper_dir"] / "wallpaper.html"
    manifest = read_manifest(html_file)

    if manifest["name"] != "Untitled":
        TITLE = manifest["name"]
        window = webview.create_window(TITLE, html_file.resolve().as_uri(), frameless=True, easy_drag=False, x=0, y=0, width=SCREEN_WIDTH, height=SCREEN_HEIGHT, js_api=None)

        def on_loaded():
            time.sleep(FIRST_FRAME_DELAY)
            READY_FILE.write_text("ready")

        window.events.loaded += on_loaded  #type: ignore
        webview.start(attach_to_desktop, window) #type: ignore
    else:
        print(f"Manifest for wallpaper '{settings['current_wallpaper_dir']}' is missing or invalid.")


images = []

#ok now we start gui heheheheheh
def load_image(path, size):
    if not path or not Path(path).is_file():
        return None
    img = Image.open(path)
    img.thumbnail(size)
    photo = ImageTk.PhotoImage(img)
    images.append(photo)
    return photo


def create_premium_satire_window():
    win_premium = tk.Toplevel()
    win_premium.title("Wallpaper.HTML Premium")
    win_premium.iconbitmap(str(ICON_ICO))
    win.update()
    apply_theme_to_titlebar(win_premium)
    win.deiconify()
    win_premium.geometry("500x500")
    win_premium.resizable(False, False)
    win_premium.transient(win)

    premium_label_frame = ttk.Frame(win_premium, padding=20)
    premium_label_frame.pack(pady=10, padx=20, fill="x")
    ttk.Label(premium_label_frame, text="Wallpaper.HTML Premium", font=("Courier", 18, "bold")).pack(pady=20, side="left")
    premium_icon = load_image(ICON_PNG, (48, 48))
    ttk.Label(premium_label_frame,  image=premium_icon).pack(pady=10, side="right") #type:ignore
    ttk.Label(win_premium, text="You already HAVE PREMIUM! 😭🥀💀", font=("Segoe UI", 14)).pack(pady=10)

    premium_card_frame = ttk.Frame(win_premium, style="Card.TFrame", padding=20)
    premium_card_frame.pack(pady=20, padx=20, fill="both", expand=True)
    ttk.Label(premium_card_frame, text="Premium Features: (free btw)", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 10))
    ttk.Separator(premium_card_frame, orient="horizontal").pack(fill="x", pady=(0, 10))
    ttk.Label(premium_card_frame, text="Everything in free:\n• All wallpapers are free to use and share.\n• No ads\n• Full access to all features.\n• Support the developer and future updates.", font=("Segoe UI", 12), justify="left").pack(anchor="w")
    win.update()
    apply_theme_to_titlebar(win_premium)
    win.deiconify()


def apply_theme_to_titlebar(root):
    version = sys.getwindowsversion()
    if version.major == 10 and version.build >= 22000:
        pywinstyles.change_header_color(root, "#1c1c1c" if sv_ttk.get_theme() == "dark" else "#fafafa") #type: ignore
    elif version.major == 10:
        pywinstyles.apply_style(root, "dark" if sv_ttk.get_theme() == "dark" else "normal")#type: ignore
        root.wm_attributes("-alpha", 0.99)
        root.wm_attributes("-alpha", 1)


def toggle_see_premium_btn():
    topbar_addbtn.pack_forget()
    if not settings["hide_get_premium"]:
        topbar_addbtn.pack(side="right", padx=10, pady=5)

#all the stuff for ui, like build cmds, so can can just put them all in another func and rn that on __main__
def build_topbar():
    global topbar_addbtn
    topbar_frame = ttk.Frame(win, height=30)

    topbar_frame.pack(side="top", fill="x")

    header_icon = load_image(ICON_PNG, (28, 28))
    topbar_title = ttk.Label(topbar_frame, text=" Wallpaper.HTML", image=header_icon, compound="left", font=("Courier", 16, "bold")) #type: ignore
    topbar_title.pack(side="left", padx=15, pady = 10)

    topbar_addbtn = ttk.Button(topbar_frame, text=" 💎 Get Premium", style="Accent.TButton", command=create_premium_satire_window)
    toggle_see_premium_btn()

    topbar_hsep = ttk.Separator(win, orient="horizontal")
    topbar_hsep.pack(side="top", fill="x", pady=5, padx=10)


def build_bottom_bar():
    bottom_bar_frame = ttk.Frame(win, height=30)
    bottom_bar_frame.pack(side="bottom", fill="x")

    bottom_bar_label = ttk.Label(bottom_bar_frame, text="Made with ❤️by @THEbluefirestudios", foreground="#474747", font=("Segoe UI", 10))
    bottom_bar_label.pack(side="right", padx=15, pady=5)

def build_sidebar():
    global sidebar_wp_btn, sidebar_st_btn
    sidebar_frame = ttk.Frame(win, width=200)
    sidebar_frame.pack(side="left", fill="y")

    sidebar_wp_btn = ttk.Button(sidebar_frame, text="🖼️ Wallpapers", command=lambda: show_screen(0), style="Accent.TButton" if CURRENT_SCREEN==0 else "Unaccent.TButton")
    sidebar_wp_btn.pack(pady=5, padx=10, fill="x")
    sidebar_st_btn = ttk.Button(sidebar_frame, text="⚙️ Settings", command=lambda: show_screen(1), style="Accent.TButton" if CURRENT_SCREEN==1 else "Unaccent.TButton")
    sidebar_st_btn.pack(pady=5, padx=10, fill="x")

#highliight the current scren btn, tk dosent have hamburger menus, so like this the closest thing we have :((
def show_screen(index):
    global CURRENT_SCREEN
    CURRENT_SCREEN = index
    screen_frame.destroy()
    sidebar_wp_btn.configure(style="Accent.TButton" if index == 0 else "Unaccent.TButton")
    sidebar_st_btn.configure(style="Accent.TButton" if index == 1 else "Unaccent.TButton")
    build_screen(index)

#funcs for btns and shi
def add_wallpaper():
    chosen = filedialog.askdirectory()
    if not chosen:
        return
    src = Path(chosen)
    dest = WALLPAPERS_DIR / src.name
    if not (src / "wallpaper.html").is_file():
        messagebox.showerror("Wallpaper.HTML", "That folder has no wallpaper.html file.")
        return
    if dest.exists():
        messagebox.showerror("Wallpaper.HTML", "A wallpaper with that folder name already exists.")
        return
    shutil.copytree(src, dest)
    if read_manifest(dest / "wallpaper.html")["name"] == "Untitled":
        shutil.rmtree(dest, ignore_errors=True)
        messagebox.showerror("Wallpaper.HTML", "Invalid wallpaper: the manifest is missing or has no name.")
        return
    show_screen(0)


def toggle_wallpaper(info):
    set_wallpaper("" if settings["current_wallpaper_dir"] == info["dir"] else info["dir"])
    show_screen(0)


def delete_wallpaper(info):

    if not messagebox.askyesno("Wallpaper.HTML", f"Delete \"{info['name']}\"?"):
        return
    
    if settings["current_wallpaper_dir"] == info["dir"]:
        set_wallpaper("")

    shutil.rmtree(WALLPAPERS_DIR / info["dir"], ignore_errors=True)
    show_screen(0)


def build_card_list(parent):
    canvas = tk.Canvas(parent, highlightthickness=0, background=ttk.Style().lookup("TFrame", "background"))
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = ttk.Frame(canvas)
    window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
    canvas.bind_all("<MouseWheel>", lambda e: canvas.winfo_exists() and canvas.yview_scroll(int(-e.delta / 120), "units"))
    return inner

# thw wallp card
def build_wallpaper_card(parent, info):
    active = settings["current_wallpaper_dir"] == info["dir"]

    card = ttk.Frame(parent, style="Card.TFrame", padding=10)
    card.pack(fill="x", padx=20, pady=6)

    photo = load_image(info["thumbnail"], (160, 90))
    thumb = ttk.Label(card, image=photo) if photo else ttk.Label(card, text="No preview", width=20, anchor="center")
    thumb.pack(side="left")

    buttons = ttk.Frame(card)
    buttons.pack(side="right", padx=(10, 0))
    ttk.Button(buttons, text="✕ Unset" if active else "✓ Set", width=10, style="TButton" if active else "Accent.TButton", command=lambda: toggle_wallpaper(info)).pack(pady=2, fill="x")
    ttk.Button(buttons, text="🗑 Delete", width=10, command=lambda: delete_wallpaper(info)).pack(pady=2, fill="x")

    text = ttk.Frame(card)
    text.pack(side="left", fill="both", expand=True, padx=12)
    ttk.Label(text, text=info["name"], font=("Segoe UI", 12, "bold")).pack(anchor="w")
    ttk.Label(text, text=f"by {info['author']}" + ("  - Current" if active else ""), font=("Segoe UI", 9)).pack(anchor="w")
    desc = ttk.Label(text, text=info["description"], font=("Segoe UI", 10), justify="left")
    desc.pack(anchor="w", pady=(4, 0))
    text.bind("<Configure>", lambda e: desc.configure(wraplength=max(e.width - 10, 100)))


def add_setting_row(parent, label_text, key, on_change=None):
    row = ttk.Frame(parent, height=50)
    row.pack(pady=10, padx=20, fill="x")
    ttk.Label(row, text=label_text, font=("Segoe UI", 12)).pack(side="left", padx=10)
    var = tk.BooleanVar(value=settings[key])

    def changed():
        settings[key] = var.get()
        save_settings()
        if on_change:
            on_change()

    toggle = ttk.Checkbutton(row, variable=var, command=changed)
    toggle.var = var #type: ignore
    toggle.pack(side="right", padx=10)


def build_screen(crnt_scrn):
    global screen_frame
    if crnt_scrn == 0:
        wallpapers_frame = ttk.Frame(win)
        wallpapers_frame.pack(side="right", fill="both", expand=True)
        screen_frame = wallpapers_frame
        wallpapers_label = ttk.Label(wallpapers_frame, text="Your Wallpapers: ", font=("Segoe UI", 14))
        wallpapers_label.pack(pady=20)

        new_wallpaper_btn = ttk.Button(wallpapers_frame, text="➕ Add New Wallpaper", style="Accent.TButton", command=add_wallpaper)
        new_wallpaper_btn.pack(pady=10, padx=20, side = "bottom", fill="x")

        card_list = build_card_list(wallpapers_frame)

        for info in list_wallpapers():
            build_wallpaper_card(card_list, info)

    elif crnt_scrn == 1:
        settings_frame = ttk.Frame(win)
        settings_frame.pack(side="right", fill="both", expand=True)
        screen_frame = settings_frame
        settings_label = ttk.Label(settings_frame, text="Settings:", font=("Segoe UI", 14))
        settings_label.pack(pady=20)

        add_setting_row(settings_frame, "Run Wallpaper.HTML on Startup: ", "run_on_startup", lambda: set_startup(settings["run_on_startup"]))
        add_setting_row(settings_frame, "Hide \"Get Premium\" option: ", "hide_get_premium", toggle_see_premium_btn)
        add_setting_row(settings_frame, "Developer Mode (Allow Non-verified wallpapers): ", "developer_mode")
        add_setting_row(settings_frame, "Pause wallpaper on fullscreened app: ", "pause_on_fullscreen")


def build_ui():
    build_topbar()
    build_bottom_bar()
    build_sidebar()
    build_screen(CURRENT_SCREEN)
    #wait vro


def quit_app():
    stop_wallpaper()
    tray.stop()
    win.destroy()


if "--wallpaper" in sys.argv:
    run_wallpaper()
    sys.exit()

# if __name__ == "__main__": i dont remebr why i commented this, and then i forgot, and it still works so why should i care
WALLPAPERS_DIR.mkdir(exist_ok=True)
win = tk.Tk()

win.withdraw()
win.iconbitmap(str(ICON_ICO))
win.geometry("960x540")
win.minsize(800, 450)
win.title("Wallpaper.HTML")
theme = "dark" if darkdetect.isDark() else "light"
sv_ttk.set_theme(theme)
win.update()
apply_theme_to_titlebar(win)
build_ui()


tray = pystray.Icon("wallpaper_html", Image.open(ICON_ICO), "Wallpaper.HTML", pystray.Menu(pystray.MenuItem("Open", lambda: win.after(0, win.deiconify), default=True),pystray.MenuItem("Quit", lambda: win.after(0, quit_app))))
tray.run_detached()
win.protocol("WM_DELETE_WINDOW", win.withdraw)
atexit.register(stop_wallpaper)
threading.Thread(target=fullscreen_watcher, daemon=True).start()

if settings["run_on_startup"]:
    set_startup(True)

if settings["current_wallpaper_dir"]:
    start_wallpaper()

tk.mainloop()