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
import threading
import time
import tkinter as tk
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

SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()

CURRENT_SCREEN = 0

DEFAULT_SETTINGS = {
    "current_wallpaper_dir": "",
    "pause_on_fullscreen": True,
    "hide_get_premium": False,
    "developer_mode": False,
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

DEFAULTS = {
    "name": "Untitled",
    "thumbnail": None,
    "author": "Unknown",
    "description": "",
}

#the "manifest", top 4 lines of wallpaper.html that is commented
def read_manifest(html_path):
    html_path = Path(html_path)
    text = html_path.read_text(encoding="utf-8-sig")

    manifest = dict(DEFAULTS)

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


def list_wallpapers():
    wallpapers = []
    for folder in sorted(WALLPAPERS_DIR.iterdir()):
        if (folder / "wallpaper.html").is_file():
            manifest = read_manifest(folder / "wallpaper.html")
            if manifest["name"] != "Untitled":
                wallpapers.append({**manifest, "dir": folder.name})
    return wallpapers


wallpaper_proc = None


def start_wallpaper():
    global wallpaper_proc
    stop_wallpaper()
    wallpaper_proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--wallpaper"], creationflags=subprocess.CREATE_NO_WINDOW)


def stop_wallpaper():
    global wallpaper_proc
    if wallpaper_proc and wallpaper_proc.poll() is None:
        wallpaper_proc.terminate()
        wallpaper_proc.wait()
    wallpaper_proc = None


def set_wallpaper(name):
    settings["current_wallpaper_dir"] = name
    save_settings()
    if name:
        start_wallpaper()
    else:
        stop_wallpaper()


TITLE = "Wallpaper"

#the js for like pausing wllpapers, like lively!
PAUSE_JS = "document.querySelectorAll('video').forEach(v => v.pause()); document.dispatchEvent(new Event('wallpaper-pause'));"
RESUME_JS = "document.querySelectorAll('video').forEach(v => v.play().catch(() => {})); document.dispatchEvent(new Event('wallpaper-resume'));"

#quick find progman, send that one code, find workerw, also in win11 i think worker w is chil or progman, and dis app for win11 and 10, so both methods merged to 1
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

#shuld it?
def should_pause():
    fg = win32gui.GetForegroundWindow()

    if not fg or not win32gui.IsWindowVisible(fg) or win32gui.IsIconic(fg):
        return False

    if win32gui.GetClassName(fg) in {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}:
        return False
    
    left, top, right, bottom = win32gui.GetWindowRect(fg)
    covers_screen = left <= 0 and top <= 0 and right >= SCREEN_WIDTH and bottom >= SCREEN_HEIGHT
    return covers_screen or bool(win32gui.IsZoomed(fg)) #type: ignore


def watch_fullscreen(window):
    paused = False
    while True:
        try:
            want = load_settings()["pause_on_fullscreen"] and should_pause()
            if want != paused:
                window.evaluate_js(PAUSE_JS if want else RESUME_JS)
                paused = want
        except Exception as e:
            print("watcher error:", e)
        time.sleep(1)


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

    threading.Thread(target=watch_fullscreen, args=(window,), daemon=True).start()


def run_wallpaper():
    global TITLE
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = '--host-rules="MAP * ~NOTFOUND, EXCLUDE localhost"'
    html_file = WALLPAPERS_DIR / settings["current_wallpaper_dir"] / "wallpaper.html"
    manifest = read_manifest(html_file)

    if manifest["name"] != "Untitled":
        TITLE = manifest["name"]
        window = webview.create_window(TITLE, html_file.resolve().as_uri(), frameless=True, easy_drag=False, x=0, y=0, width=SCREEN_WIDTH, height=SCREEN_HEIGHT, js_api=None)
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

    topbar_addbtn = ttk.Button(topbar_frame, text=" 💎 Get Premium", style="Accent.TButton",
                               command=lambda: messagebox.showinfo("Wallpaper.HTML", "Premium unlocked! (It's free.)"))
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
    # Add more widgets to the sidebar as needed, no more

#highliight the current scren btn, tk dosent have hamburger menus, so like this the closest thing we have :((
def show_screen(index):
    global CURRENT_SCREEN
    CURRENT_SCREEN = index
    screen_frame.destroy()
    sidebar_wp_btn.configure(style="Accent.TButton" if index == 0 else "Unaccent.TButton")
    sidebar_st_btn.configure(style="Accent.TButton" if index == 1 else "Unaccent.TButton")
    build_screen(index)


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

        add_setting_row(settings_frame, "Pause Wallpaper on Fullscreen: ", "pause_on_fullscreen")
        add_setting_row(settings_frame, "Hide \"Get Premium\" option: ", "hide_get_premium", toggle_see_premium_btn)
        add_setting_row(settings_frame, "Developer Mode (Allow Non-verified wallpapers): ", "developer_mode")


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
win.iconbitmap(str(ICON_ICO))
win.geometry("960x540")
win.minsize(800, 450)
win.title("Wallpaper.HTML")
theme = "dark" if darkdetect.isDark() else "light"
sv_ttk.set_theme(theme)
win.update()
apply_theme_to_titlebar(win)
build_ui()

tray = pystray.Icon("wallpaper_html", Image.open(ICON_ICO), "Wallpaper.HTML", pystray.Menu(
    pystray.MenuItem("Open", lambda: win.after(0, win.deiconify), default=True),
    pystray.MenuItem("Quit", lambda: win.after(0, quit_app))))
tray.run_detached()
win.protocol("WM_DELETE_WINDOW", win.withdraw)
atexit.register(stop_wallpaper)

if settings["current_wallpaper_dir"]:
    start_wallpaper()

tk.mainloop()