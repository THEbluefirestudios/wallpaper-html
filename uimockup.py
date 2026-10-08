import tkinter as tk
from tkinter import ttk
import sv_ttk
import darkdetect
import sys

try:
    import pywinstyles
except ImportError:
    pywinstyles = None


CURRENT_SCREEN = 0

def apply_theme_to_titlebar(root):
    version = sys.getwindowsversion()
    if version.major == 10 and version.build >= 22000:
        pywinstyles.change_header_color(root, "#1c1c1c" if sv_ttk.get_theme() == "dark" else "#fafafa") #type: ignore
    elif version.major == 10:
        pywinstyles.apply_style(root, "dark" if sv_ttk.get_theme() == "dark" else "normal")#type: ignore
        root.wm_attributes("-alpha", 0.99)
        root.wm_attributes("-alpha", 1)



def build_topbar():
    topbar_frame = ttk.Frame(win, height=30)

    topbar_frame.pack(side="top", fill="x")

    topbar_title = ttk.Label(topbar_frame, text="Wallpaper.HTML", background="#1c1c1c", foreground="#ffffff", font=("Courier", 16, "bold"))
    topbar_title.pack(side="left", padx=15, pady = 10)

    topbar_addbtn = ttk.Button(topbar_frame, text=" 💎 Get Premium", style="Accent.TButton")
    topbar_addbtn.pack(side="right", padx=10, pady = 5)

    topbar_hsep = ttk.Separator(win, orient="horizontal")
    topbar_hsep.pack(side="top", fill="x", pady=5, padx=10)


def build_bottom_bar():
    bottom_bar_frame = ttk.Frame(win, height=30)
    bottom_bar_frame.pack(side="bottom", fill="x")

    bottom_bar_label = ttk.Label(bottom_bar_frame, text="Made with ❤️by @THEbluefirestudios", foreground="#474747", font=("Segoe UI", 10))
    bottom_bar_label.pack(side="right", padx=15, pady=5)

def build_sidebar():
    sidebar_frame = ttk.Frame(win, width=200)
    sidebar_frame.pack(side="left", fill="y")

    sidebar_wp_btn = ttk.Button(sidebar_frame, text="🖼️ Wallpapers", style="Accent.TButton" if CURRENT_SCREEN==0 else "Unaccent.TButton")
    sidebar_wp_btn.pack(pady=5, padx=10, fill="x")
    sidebar_st_btn = ttk.Button(sidebar_frame, text="⚙️ Settings", style="Accent.TButton" if CURRENT_SCREEN==1 else "Unaccent.TButton")
    sidebar_st_btn.pack(pady=5, padx=10, fill="x")
    # Add more widgets to the sidebar as needed

def build_screen(crnt_scrn):
    if crnt_scrn == 0:
        wallpapers_frame = ttk.Frame(win)
        wallpapers_frame.pack(side="right", fill="both", expand=True)
        wallpapers_label = ttk.Label(wallpapers_frame, text="Your Wallpapers: ", font=("Segoe UI", 14))
        wallpapers_label.pack(pady=20)

        new_wallpaper_btn = ttk.Button(wallpapers_frame, text="➕ Add New Wallpaper", style="Accent.TButton") # open a folderpicker dialog, then copy that folder to scriptdir/wallpapers, check for metadata, if its valid, good, add it, if it isnt, messagebox + delete that folder from the wallpapers dir
        new_wallpaper_btn.pack(pady=10, padx=20, side = "bottom", fill="x")

        # I need u to add wallpaper cards here with title, author, desc, a thumbnail, and like 2 buttons to the right of the card to toggel set/unset as walp, and delete wallp
    elif crnt_scrn == 1:
        settings_frame = ttk.Frame(win)
        settings_frame.pack(side="right", fill="both", expand=True)
        settings_label = ttk.Label(settings_frame, text="Settings:", font=("Segoe UI", 14))
        settings_label.pack(pady=20)

        settings_pausewallp_on_fsc = ttk.Frame(settings_frame, height=50)
        settings_pausewallp_on_fsc.pack(pady=10, padx=20, fill="x")
        settings1_label = ttk.Label(settings_pausewallp_on_fsc, text="Pause Wallpaper on Fullscreen: ", font=("Segoe UI", 12))
        settings1_label.pack(side="left", padx=10)
        settings1_toggle = ttk.Checkbutton(settings_pausewallp_on_fsc)
        settings1_toggle.pack(side="right", padx=10)

        settings_hide_getpremium = ttk.Frame(settings_frame, height=50)
        settings_hide_getpremium.pack(pady=10, padx=20, fill="x")
        settings2_label = ttk.Label(settings_hide_getpremium, text="Hide \"Get Premium\" option: ", font=("Segoe UI", 12))
        settings2_label.pack(side="left", padx=10)
        settings2_toggle = ttk.Checkbutton(settings_hide_getpremium)
        settings2_toggle.pack(side="right", padx=10)

        settings_devmode = ttk.Frame(settings_frame, height=50)
        settings_devmode.pack(pady=10, padx=20, fill="x")
        settings3_label = ttk.Label(settings_devmode, text="Developer Mode (Allow Non-verified wallpapers): ", font=("Segoe UI", 12))
        settings3_label.pack(side="left", padx=10)
        settings3_toggle = ttk.Checkbutton(settings_devmode)
        settings3_toggle.pack(side="right", padx=10)




def build_ui():
    build_topbar()
    build_bottom_bar()
    build_sidebar()
    build_screen(CURRENT_SCREEN)
    #wait vro
# if __name__ == "__main__":
win = tk.Tk()
apply_theme_to_titlebar(win)
win.geometry("960x540")
win.minsize(800, 450)
win.title("Wallpaper.HTML")
build_ui()
theme = "dark" if darkdetect.isDark() else "light"
sv_ttk.set_theme(theme)

tk.mainloop()

