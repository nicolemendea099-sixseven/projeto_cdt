import sys
import json
import os
import subprocess
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except ImportError:
    PYGETWINDOW_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


# ---------- Configurações ----------
DISTRACTION_KEYWORDS = ["instagram", "tiktok", "whatsapp", "youtube"]

PRODUCTIVE_KEYWORDS = [
    "visual studio code",
    "vscode",
    "github desktop",
    "github",
]

PRODUCTIVE_PROCESS_NAMES = [
    "github desktop",
    "githubdesktop",
    "code",          # Visual Studio Code
    "code - insiders",
]

DISTRACTION_PROCESS_NAMES = [
    "whatsapp",
    "tiktok",
    "instagram",
    "youtube",
]

POLL_INTERVAL_MS = 3000        # Checa a janela ativa a cada 3s
DECAY_PER_TICK = 0.5           # Perda natural de felicidade (ociosidade)
BOOST_PRODUCTIVE = 2.5         # Ganho de felicidade ao usar apps produtivos
PENALTY_DISTRACTION = 4.0      # Perda ao usar apps de distração

XP_PER_PRODUCTIVE_TICK = 10    # XP ganho por tick produtivo
XP_PER_LEVEL = 100             # XP necessário para subir de nível

CRITICAL_HAPPINESS = 15        # Limite para disparar notificação nativa

STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tamagotchi_state.json"
)

# ---------- Configurações de janela flutuante ----------
CORNER_MARGIN = 16
FULL_SIZE = (380, 780)
MINI_SIZE = (170, 230)

CORNER_OPTIONS = [
    ("Sup. esquerdo", "top-left"),
    ("Sup. direito", "top-right"),
    ("Inf. esquerdo", "bottom-left"),
    ("Inf. direito", "bottom-right"),
]


# ---------- Detecção de janela ativa (multiplataforma) ----------
def get_active_window_title():
    if PYGETWINDOW_AVAILABLE:
        try:
            win = gw.getActiveWindow()
            if win and win.title:
                return win.title
        except Exception:
            pass

    try:
        if sys.platform == "darwin":
            script = (
                'tell application "System Events" to get name of first '
                'application process whose frontmost is true'
            )
            out = subprocess.check_output(["osascript", "-e", script])
            app_name = out.decode().strip()
            try:
                script2 = (
                    'tell application "System Events" to tell process "%s" '
                    'to get name of front window' % app_name
                )
                out2 = subprocess.check_output(["osascript", "-e", script2])
                title = out2.decode().strip()
                return f"{app_name} {title}"
            except Exception:
                return app_name

        elif sys.platform.startswith("linux"):
            out = subprocess.check_output(
                ["xdotool", "getactivewindow", "getwindowname"]
            )
            return out.decode().strip()

    except Exception:
        return None
    return None


def get_active_process_name():
    if not PSUTIL_AVAILABLE:
        return None

    try:
        if sys.platform == "win32":
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc = psutil.Process(pid.value)
            return proc.name().lower()

        elif sys.platform == "darwin":
            script = (
                'tell application "System Events" to get name of first '
                'application process whose frontmost is true'
            )
            out = subprocess.check_output(["osascript", "-e", script])
            return out.decode().strip().lower()

        elif sys.platform.startswith("linux"):
            pid_out = subprocess.check_output(
                ["xdotool", "getactivewindow", "getwindowpid"]
            )
            pid = int(pid_out.decode().strip())
            proc = psutil.Process(pid)
            return proc.name().lower()

    except Exception:
        return None
    return None


def classify_activity(title, process_name):
    title_lower = (title or "").lower()
    process_lower = (process_name or "").lower()

    if any(k in title_lower for k in DISTRACTION_KEYWORDS):
        return "distracao", title or "app de distração"

    if any(k in title_lower for k in PRODUCTIVE_KEYWORDS):
        return "produtivo", title or "app produtivo"

    if any(p in process_lower for p in DISTRACTION_PROCESS_NAMES):
        label = title or "app de distração"
        return "distracao", label

    if any(p in process_lower for p in PRODUCTIVE_PROCESS_NAMES):
        label = title or "GitHub Desktop"
        return "produtivo", label

    return "neutro", title


# ---------- Notificações nativas ----------
def try_send_notification(title, message):
    if not PLYER_AVAILABLE:
        return False, "A biblioteca 'plyer' não está instalada. Rode: pip install plyer"
    try:
        notification.notify(
            title=title, message=message,
            app_name="Tamagotchi de Produtividade", timeout=8,
        )
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def platform_notification_tips():
    if sys.platform == "darwin":
        return (
            "No macOS:\n"
            "• Ajustes do Sistema > Notificações > procure pelo Terminal ou app rodando Python.\n"
            "• Verifique se o Foco/Não Perturbe está desativado."
        )
    elif sys.platform == "win32":
        return (
            "No Windows:\n"
            "• Configurações > Sistema > Notificações — confira se estão ativadas.\n"
            "• Verifique se a Assistência de Foco está desligada."
        )
    else:
        return (
            "No Linux:\n"
            "• Requer 'notify-send' (libnotify-bin)."
        )


def send_critical_notification(happiness):
    try_send_notification(
        "🐣 Tamagotchi precisando de você!",
        f"Felicidade em {int(happiness)}%. Volte ao foco antes que seu bichinho fique doente!",
    )


# ---------- Persistência de estado ----------
def load_state():
    default = {
        "happiness": 70, "xp": 0, "level": 1,
        "name": "", "appearance": "tradicional",
        "owner_name": "", "owner_nickname": "", "owner_age": "",
        "pinned": True, "mini_mode": False, "corner": "bottom-right",
        "target_minutes": 60, "seconds_focused": 0,
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                default["happiness"] = data.get("happiness", 70)
                default["xp"] = data.get("xp", 0)
                default["level"] = data.get("level", 1)
                default["name"] = data.get("name", "")
                default["appearance"] = data.get("appearance", "tradicional")
                default["owner_name"] = data.get("owner_name", "")
                default["owner_nickname"] = data.get("owner_nickname", "")
                default["owner_age"] = data.get("owner_age", "")
                default["pinned"] = data.get("pinned", True)
                default["mini_mode"] = data.get("mini_mode", False)
                default["corner"] = data.get("corner", "bottom-right")
                default["target_minutes"] = data.get("target_minutes", 60)
                default["seconds_focused"] = data.get("seconds_focused", 0)
        except Exception:
            pass
    return default


def save_state(happiness, xp, level, name, appearance, owner_name="", owner_nickname="",
               owner_age="", pinned=True, mini_mode=False, corner="bottom-right",
               target_minutes=60, seconds_focused=0):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(
                {
                    "happiness": happiness,
                    "xp": xp,
                    "level": level,
                    "name": name,
                    "appearance": appearance,
                    "owner_name": owner_name,
                    "owner_nickname": owner_nickname,
                    "owner_age": owner_age,
                    "pinned": pinned,
                    "mini_mode": mini_mode,
                    "corner": corner,
                    "target_minutes": target_minutes,
                    "seconds_focused": seconds_focused,
                    "updated": datetime.now().isoformat(),
                },
                f,
            )
    except Exception:
        pass


APPEARANCE_OPTIONS = [
    ("Tradicional", "tradicional"),
    ("🐱 Gato", "gato"),
    ("🐶 Cachorro", "cachorro"),
    ("🐰 Coelho", "coelho"),
]


# ---------- Paleta visual ----------
COLORS = {
    "bg": "#eef1f8",
    "card": "#ffffff",
    "card_border": "#e4e7f2",
    "text": "#2d2d3a",
    "text_muted": "#8b8fa3",
    "primary": "#7c5cfc",
    "primary_dark": "#6a48f2",
    "primary_light": "#efeaff",
    "track": "#eef0f7",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "warning_bg": "#fff4e5",
    "warning_fg": "#b45309",
}

MOOD_COLORS = {
    "eufórico": {"body": "#ffc94d", "light": "#ffe6a3", "aura": "#fff6e0"},
    "feliz":    {"body": "#8fd67f", "light": "#c3ecb8", "aura": "#e9f9e4"},
    "neutro":   {"body": "#7aa8f0", "light": "#b7d0f7", "aura": "#e7f0fd"},
    "triste":   {"body": "#9aa3b0", "light": "#c7ced8", "aura": "#eef0f4"},
    "doente":   {"body": "#ef8a8a", "light": "#f6bcbc", "aura": "#fde9e9"},
    "irritado": {"body": "#ef5b57", "light": "#f5a19e", "aura": "#fde3e2"},
}

FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_STATUS = ("Segoe UI", 13, "bold")
FONT_SUB = ("Segoe UI", 9)
FONT_SMALL = ("Segoe UI", 8)
FONT_BTN = ("Segoe UI", 9, "bold")


def rounded_rect_points(x1, y1, x2, y2, r):
    r = max(1, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2 - r, x1, y1 + r, x1, y1,
    ]


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command=None, bg=None, fg="#ffffff",
                 hover_bg=None, width=140, height=34, font=FONT_BTN,
                 parent_bg=None):
        bg = bg or COLORS["primary"]
        pbg = parent_bg if parent_bg is not None else parent["bg"]
        super().__init__(parent, width=width, height=height, bg=pbg,
                          highlightthickness=0)
        self.command = command
        self.bg_color = bg
        self.hover_bg = hover_bg or bg
        self.fg = fg
        self.font = font
        self.w = width
        self.h = height
        self.text = text
        self.text_id = None
        self._render(self.bg_color)
        if command:
            self.configure(cursor="hand2")
            self.bind("<Button-1>", lambda e: self.command())
            self.bind("<Enter>", lambda e: self._render(self.hover_bg))
            self.bind("<Leave>", lambda e: self._render(self.bg_color))

    def _render(self, color):
        self.delete("all")
        r = self.h / 2
        self.create_polygon(rounded_rect_points(1, 1, self.w - 1, self.h - 1, r),
                             smooth=True, fill=color, outline="")
        self.text_id = self.create_text(self.w / 2, self.h / 2, text=self.text,
                                        fill=self.fg, font=self.font)

    def set_text(self, text):
        self.text = text
        self._render(self.bg_color)


class RoundedBar(tk.Canvas):
    def __init__(self, parent, width, height, track_color, fill_color,
                 bg, text_fg="#ffffff", radius=None):
        super().__init__(parent, width=width, height=height, bg=bg,
                          highlightthickness=0)
        self.w = width
        self.h = height
        self.fill_color = fill_color
        self.text_fg = text_fg
        self.radius = radius if radius is not None else height / 2
        self.create_polygon(rounded_rect_points(1, 1, width - 1, height - 1,
                                                  self.radius),
                             smooth=True, fill=track_color, outline="")
        self.fill_id = None
        self.text_id = self.create_text(width / 2, height / 2, text="",
                                         font=FONT_SMALL, fill=text_fg)

    def set(self, fraction, text="", fill_color=None):
        fraction = max(0.0, min(1.0, fraction))
        if self.fill_id is not None:
            self.delete(self.fill_id)
            self.fill_id = None
        color = fill_color or self.fill_color
        fw = 1 + (self.w - 2) * fraction
        if fw > 3:
            self.fill_id = self.create_polygon(
                rounded_rect_points(1, 1, fw, self.h - 1, self.radius),
                smooth=True, fill=color, outline=""
            )
        self.itemconfig(self.text_id, text=text)
        self.tag_raise(self.text_id)


# ---------- Interface gráfica ----------
class Tamagotchi(tk.Tk):
    def __init__(self):
        super().__init__()
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])

        state = load_state()
        self.happiness = state["happiness"]
        self.xp = state["xp"]
        self.level = state["level"]
        self.notified_critical = False
        self.last_category = None

        self.pet_name = state["name"]
        self.appearance = state["appearance"]
        self.owner_name = state["owner_name"]
        self.owner_nickname = state["owner_nickname"]
        self.owner_age = state["owner_age"]

        self.pinned = state["pinned"]
        self.mini_mode = state["mini_mode"]
        self.corner = state["corner"]

        self.target_minutes = state.get("target_minutes", 60)
        self.seconds_focused = state.get("seconds_focused", 0)

        is_first_time = not bool(self.owner_name)

        if is_first_time:
            self.geometry(f"{FULL_SIZE[0]}x{FULL_SIZE[1]}")
            self.update_idletasks()
            (
                name,
                appearance,
                owner_name,
                owner_nickname,
                owner_age,
                target_minutes,
            ) = self.ask_profile_setup(
                initial_name="",
                initial_appearance="tradicional",
                initial_owner_name="",
                initial_owner_nickname="",
                initial_owner_age="",
                initial_target_minutes=60,
                first_time=True,
            )
            self.pet_name = name
            self.appearance = appearance
            self.owner_name = owner_name
            self.owner_nickname = owner_nickname
            self.owner_age = owner_age
            self.target_minutes = target_minutes
            self.persist_state()
            self.speech_text = f"Bem vindo a seu Tamagotchi {self.owner_name}!"
        else:
            self.speech_text = f"Bem vindo novamente {self.owner_name}!"

        self.title(f"🐣 {self.pet_name} — Tamagotchi da Produtividade")

        # ----- Cartão central -----
        self.card = tk.Frame(self, bg=COLORS["card"],
                             highlightbackground=COLORS["card_border"],
                             highlightthickness=1)
        self.card.pack(fill="both", expand=True, padx=14, pady=14)

        header = tk.Frame(self.card, bg=COLORS["card"])
        header.pack(fill="x", pady=(18, 4))

        self.badge_level = RoundedButton(
            header, text=f"⭐ Nível {self.level}", command=None,
            bg=COLORS["primary_light"], fg=COLORS["primary_dark"],
            width=110, height=28, font=("Segoe UI", 9, "bold"),
            parent_bg=COLORS["card"],
        )
        self.badge_level.pack()

        self.label_name = tk.Label(
            self.card, text=self.pet_name, font=FONT_TITLE,
            fg=COLORS["text"], bg=COLORS["card"]
        )
        self.label_name.pack(pady=(6, 0))

        # ----- Bichinho -----
        self.canvas = tk.Canvas(
            self.card, width=320, height=220, bg=COLORS["card"],
            highlightthickness=0
        )
        self.canvas.pack(pady=(6, 2))
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        self.label_status = tk.Label(
            self.card, text="Iniciando...", font=FONT_STATUS,
            fg=COLORS["text"], bg=COLORS["card"]
        )
        self.label_status.pack(pady=(0, 2))

        # Botão para expandir quando estiver no modo mini
        self.btn_expand = RoundedButton(
            self.card, text="🔍 Expandir", command=self.toggle_mini,
            bg=COLORS["primary"], fg="#ffffff", hover_bg=COLORS["primary_dark"],
            width=120, height=28, parent_bg=COLORS["card"]
        )

        self.label_app = tk.Label(
            self.card, text="", font=FONT_SUB, fg=COLORS["text_muted"],
            bg=COLORS["card"], wraplength=300
        )
        self.label_app.pack(pady=(0, 4))

        self.label_warning = tk.Label(
            self.card, text="", font=("Segoe UI", 8, "bold"),
            fg=COLORS["warning_fg"], bg=COLORS["card"],
            wraplength=280, justify="center", padx=10, pady=6
        )
        self.label_warning.pack(pady=(0, 6), fill="x", padx=16)

        # ----- Botões -----
        self.buttons_row1 = tk.Frame(self.card, bg=COLORS["card"])
        self.buttons_row1.pack(pady=(0, 6))

        self.btn_diagnose = RoundedButton(
            self.buttons_row1, text="🔍 Diagnosticar", command=self.show_diagnostics,
            bg=COLORS["track"], fg=COLORS["text"], hover_bg="#e2e5f0",
            width=150, height=32, parent_bg=COLORS["card"]
        )
        self.btn_diagnose.pack(side="left", padx=5)

        self.btn_test_notification = RoundedButton(
            self.buttons_row1, text="🔔 Testar notificação", command=self.test_notification,
            bg=COLORS["track"], fg=COLORS["text"], hover_bg="#e2e5f0",
            width=150, height=32, parent_bg=COLORS["card"]
        )
        self.btn_test_notification.pack(side="left", padx=5)

        self.buttons_row2 = tk.Frame(self.card, bg=COLORS["card"])
        self.buttons_row2.pack(pady=(0, 10))

        self.btn_edit_profile = RoundedButton(
            self.buttons_row2, text="✏️ Editar perfil", command=self.edit_profile,
            bg=COLORS["primary"], fg="#ffffff", hover_bg=COLORS["primary_dark"],
            width=150, height=32, parent_bg=COLORS["card"]
        )
        self.btn_edit_profile.pack()

        # ----- Linha: fixar no canto + modo mini -----
        self.buttons_row3 = tk.Frame(self.card, bg=COLORS["card"])
        self.buttons_row3.pack(pady=(0, 10))

        self.btn_pin = RoundedButton(
            self.buttons_row3, text="", command=self.toggle_pin,
            bg=COLORS["track"], fg=COLORS["text"], hover_bg="#e2e5f0",
            width=150, height=32, parent_bg=COLORS["card"]
        )
        self.btn_pin.pack(side="left", padx=5)

        self.btn_mini = RoundedButton(
            self.buttons_row3, text="🔻 Modo mini (canto)", command=self.toggle_mini,
            bg=COLORS["track"], fg=COLORS["text"], hover_bg="#e2e5f0",
            width=150, height=32, parent_bg=COLORS["card"]
        )
        self.btn_mini.pack(side="left", padx=5)

        # ----- Tempo de Trabalho / Meta -----
        self.label_target_title = tk.Label(
            self.card, text="TEMPO DE TRABALHO / META", font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["card"]
        )
        self.label_target_title.pack(pady=(4, 2))

        self.bar_target = RoundedBar(
            self.card, width=300, height=20, track_color=COLORS["track"],
            fill_color=COLORS["primary"], bg=COLORS["card"], text_fg="#ffffff"
        )
        self.bar_target.pack(pady=(0, 2))

        self.label_time_details = tk.Label(
            self.card, text="", font=FONT_SMALL,
            fg=COLORS["text_muted"], bg=COLORS["card"]
        )
        self.label_time_details.pack(pady=(0, 8))

        # ----- Barra de felicidade -----
        self.label_happiness_title = tk.Label(
            self.card, text="FELICIDADE", font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["card"])
        self.label_happiness_title.pack(pady=(2, 2))

        self.bar_happiness = RoundedBar(
            self.card, width=300, height=20, track_color=COLORS["track"],
            fill_color=COLORS["success"], bg=COLORS["card"], text_fg="#ffffff"
        )
        self.bar_happiness.pack(pady=(0, 8))

        # ----- Barra de XP -----
        self.label_xp_title = tk.Label(
            self.card, text="EXPERIÊNCIA", font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["card"])
        self.label_xp_title.pack(pady=(0, 2))

        self.bar_xp = RoundedBar(
            self.card, width=300, height=14, track_color=COLORS["primary_light"],
            fill_color=COLORS["primary"], bg=COLORS["card"], text_fg=COLORS["text"]
        )
        self.bar_xp.pack(pady=(0, 2))

        self.label_xp = tk.Label(
            self.card, text="", font=FONT_SMALL,
            fg=COLORS["text_muted"], bg=COLORS["card"]
        )
        self.label_xp.pack(pady=(0, 8))

        # Widgets que somem no modo mini
        self.full_only_widgets = [
            self.badge_level, self.label_name, self.label_app, self.label_warning,
            self.buttons_row1, self.buttons_row2, self.buttons_row3,
            self.label_target_title, self.bar_target, self.label_time_details,
            self.label_happiness_title, self.bar_happiness,
            self.label_xp_title, self.bar_xp, self.label_xp,
        ]

        self.update_pin_button_text()
        self.apply_layout_mode()
        self.refresh_stats()
        self.after(200, self.start_polling)

    def on_canvas_click(self, event):
        if self.mini_mode:
            self.toggle_mini()

    def persist_state(self):
        save_state(
            self.happiness,
            self.xp,
            self.level,
            self.pet_name,
            self.appearance,
            self.owner_name,
            self.owner_nickname,
            self.owner_age,
            self.pinned,
            self.mini_mode,
            self.corner,
            self.target_minutes,
            self.seconds_focused,
        )

    def toggle_pin(self):
        self.pinned = not self.pinned
        self.update_pin_button_text()
        self.wm_attributes("-topmost", self.pinned)
        self.persist_state()

    def update_pin_button_text(self):
        txt = "📌 Fixado" if self.pinned else "📌 Desfixado"
        self.btn_pin.set_text(txt)

    def toggle_mini(self):
        self.mini_mode = not self.mini_mode
        self.apply_layout_mode()
        self.persist_state()

    def apply_layout_mode(self):
        self.wm_attributes("-topmost", self.pinned)

        if self.mini_mode:
            self.btn_mini.set_text("🔺 Modo expandido")
            for w in self.full_only_widgets:
                w.pack_forget()

            self.btn_expand.pack(pady=(4, 0))
            self.canvas.config(cursor="hand2")

            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = MINI_SIZE
            m = CORNER_MARGIN

            if self.corner == "top-left":
                x, y = m, m
            elif self.corner == "top-right":
                x, y = sw - w - m, m
            elif self.corner == "bottom-left":
                x, y = m, sh - h - m - 40
            else:
                x, y = sw - w - m, sh - h - m - 40

            self.geometry(f"{w}x{h}+{x}+{y}")
            self.canvas.config(width=140, height=130)
        else:
            self.btn_expand.pack_forget()
            self.canvas.config(cursor="")

            self.btn_mini.set_text("🔻 Modo mini")
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = FULL_SIZE
            x = (sw - w) // 2
            y = (sh - h) // 2
            self.geometry(f"{w}x{h}+{x}+{y}")

            self.badge_level.pack()
            self.label_name.pack(pady=(6, 0))
            self.label_app.pack(pady=(0, 4))
            self.label_warning.pack(pady=(0, 6), fill="x", padx=16)
            self.buttons_row1.pack(pady=(0, 6))
            self.buttons_row2.pack(pady=(0, 10))
            self.buttons_row3.pack(pady=(0, 10))

            self.label_target_title.pack(pady=(4, 2))
            self.bar_target.pack(pady=(0, 2))
            self.label_time_details.pack(pady=(0, 8))

            self.label_happiness_title.pack(pady=(2, 2))
            self.bar_happiness.pack(pady=(0, 8))

            self.label_xp_title.pack(pady=(0, 2))
            self.bar_xp.pack(pady=(0, 2))
            self.label_xp.pack(pady=(0, 8))

            self.canvas.config(width=320, height=220)

        self.draw_pet()

    def draw_pet(self):
        self.canvas.delete("all")

        if self.happiness >= 85:
            mood = "eufórico"
        elif self.happiness >= 60:
            mood = "feliz"
        elif self.happiness >= 40:
            mood = "neutro"
        elif self.happiness >= 25:
            mood = "triste"
        elif self.happiness >= 15:
            mood = "irritado"
        else:
            mood = "doente"

        colors = MOOD_COLORS.get(mood, MOOD_COLORS["neutro"])

        if self.mini_mode:
            cx, cy = 70, 65
            scale = 0.50
        else:
            cx, cy = 160, 120
            scale = 1.0

        def s(val):
            return val * scale

        # Sombra e Aura
        self.canvas.create_oval(cx - s(75), cy + s(65), cx + s(75), cy + s(85), fill="#e5e7eb", outline="")
        self.canvas.create_oval(cx - s(95), cy - s(95), cx + s(95), cy + s(95), fill=colors["aura"], outline="")
        self.canvas.create_oval(cx - s(80), cy - s(80), cx + s(80), cy + s(80), fill=colors["light"], outline="")

        # Orelhas
        if self.appearance == "gato":
            self.canvas.create_polygon(cx - s(65), cy - s(40), cx - s(35), cy - s(90), cx - s(15), cy - s(60), fill=colors["body"], outline="")
            self.canvas.create_polygon(cx + s(15), cy - s(60), cx + s(35), cy - s(90), cx + s(65), cy - s(40), fill=colors["body"], outline="")
        elif self.appearance == "coelho":
            self.canvas.create_oval(cx - s(45), cy - s(130), cx - s(15), cy - s(40), fill=colors["body"], outline="")
            self.canvas.create_oval(cx + s(15), cy - s(130), cx + s(45), cy - s(40), fill=colors["body"], outline="")
            self.canvas.create_oval(cx - s(38), cy - s(120), cx - s(22), cy - s(50), fill=colors["light"], outline="")
            self.canvas.create_oval(cx + s(22), cy - s(120), cx + s(38), cy - s(50), fill=colors["light"], outline="")
        elif self.appearance == "cachorro":
            self.canvas.create_oval(cx - s(85), cy - s(40), cx - s(45), cy + s(30), fill=colors["body"], outline="")
            self.canvas.create_oval(cx + s(45), cy - s(40), cx + s(85), cy + s(30), fill=colors["body"], outline="")

        # Corpo
        self.canvas.create_oval(cx - s(65), cy - s(65), cx + s(65), cy + s(65), fill=colors["body"], outline="")

        # Olhos
        if mood == "doente":
            font_sz = int(20 * scale)
            self.canvas.create_text(cx - s(25), cy - s(10), text="x", font=("Segoe UI", font_sz, "bold"), fill="#4b5563")
            self.canvas.create_text(cx + s(25), cy - s(10), text="x", font=("Segoe UI", font_sz, "bold"), fill="#4b5563")
        elif mood == "eufórico":
            self.canvas.create_arc(cx - s(35), cy - s(20), cx - s(15), cy, start=0, extent=180, style="arc", width=int(3 * scale), outline="#1f2937")
            self.canvas.create_arc(cx + s(15), cy - s(20), cx + s(35), cy, start=0, extent=180, style="arc", width=int(3 * scale), outline="#1f2937")
        else:
            self.canvas.create_oval(cx - s(32), cy - s(18), cx - s(18), cy - s(4), fill="#1f2937", outline="")
            self.canvas.create_oval(cx + s(18), cy - s(18), cx + s(32), cy - s(4), fill="#1f2937", outline="")

        # Boca
        if mood in ["feliz", "eufórico"]:
            self.canvas.create_arc(cx - s(20), cy - s(5), cx + s(20), cy + s(25), start=180, extent=180, fill="#ef4444", outline="")
        elif mood in ["triste", "irritado", "doente"]:
            self.canvas.create_arc(cx - s(20), cy + s(10), cx + s(20), cy + s(35), start=0, extent=180, style="arc", width=int(3 * scale), outline="#1f2937")
        else:
            self.canvas.create_line(cx - s(15), cy + s(15), cx + s(15), cy + s(15), width=int(3 * scale), fill="#1f2937")

        if self.appearance in ["gato", "cachorro", "coelho"]:
            self.canvas.create_polygon(cx - s(6), cy + s(2), cx + s(6), cy + s(2), cx, cy + s(8), fill="#374151", outline="")

        # Balão de fala (Apenas modo expandido)
        if self.speech_text and not self.mini_mode:
            bx, by = 160, 25
            self.canvas.create_polygon(
                bx - 120, by - 20, bx + 120, by - 20, bx + 120, by + 15,
                bx + 15, by + 15, bx, by + 28, bx - 5, by + 15,
                bx - 120, by + 15,
                fill="#ffffff", outline=COLORS["primary"], width=2
            )
            self.canvas.create_text(
                bx, by - 3, text=self.speech_text,
                font=("Segoe UI", 8, "bold"), fill=COLORS["text"], width=230, justify="center"
            )

    def refresh_stats(self):
        happiness_pct = max(0, min(100, self.happiness))
        xp_pct = max(0.0, min(1.0, self.xp / max(1, XP_PER_LEVEL)))

        self.bar_happiness.set(happiness_pct / 100, text=f"{int(happiness_pct)}%")
        self.bar_xp.set(xp_pct, text=f"{int(self.xp)}/{XP_PER_LEVEL} XP")
        self.label_xp.config(text=f"Nível {self.level} • {self.xp} XP")
        self.badge_level.set_text(f"⭐ Nível {self.level}")

        target_seconds = max(1, self.target_minutes * 60)
        target_pct = max(0.0, min(1.0, self.seconds_focused / target_seconds))
        
        mins = self.seconds_focused // 60
        secs = self.seconds_focused % 60
        time_formatted = f"{mins}m {secs:02d}s"
        
        self.bar_target.set(target_pct, text=f"{int(target_pct * 100)}% da Meta")
        self.label_time_details.config(
            text=f"Focado: {time_formatted} / Meta: {self.target_minutes} min"
        )

        if self.happiness <= CRITICAL_HAPPINESS:
            self.label_status.config(text="Preciso de atenção!")
        elif self.happiness >= 70:
            self.label_status.config(text="Estou feliz!")
        else:
            self.label_status.config(text="Estou bem.")

        self.draw_pet()

    def start_polling(self):
        self.poll_activity()

    def poll_activity(self):
        title = get_active_window_title()
        process_name = get_active_process_name()
        category, label = classify_activity(title, process_name)

        self.label_app.config(text=f"Ativo: {label[:35]}")

        if category == "produtivo":
            self.happiness = min(100, self.happiness + BOOST_PRODUCTIVE)
            self.xp += XP_PER_PRODUCTIVE_TICK
            
            seconds_added = POLL_INTERVAL_MS // 1000
            self.seconds_focused += seconds_added

            self.speech_text = "Muito bem! Continue focado!"
            if self.xp >= XP_PER_LEVEL:
                self.level += 1
                self.xp = 0
                self.speech_text = f"Subiu para o Nível {self.level}! 🎉"

        elif category == "distracao":
            self.happiness = max(0, self.happiness - PENALTY_DISTRACTION)
            self.speech_text = "Ei! Volte ao trabalho!"

        else:
            self.happiness = max(0, self.happiness - DECAY_PER_TICK)

        if self.happiness <= CRITICAL_HAPPINESS and not self.notified_critical:
            send_critical_notification(self.happiness)
            self.notified_critical = True
        elif self.happiness > CRITICAL_HAPPINESS:
            self.notified_critical = False

        self.refresh_stats()
        self.persist_state()

        self.after(POLL_INTERVAL_MS, self.poll_activity)

    def show_diagnostics(self):
        title = get_active_window_title()
        process_name = get_active_process_name()
        category, label = classify_activity(title, process_name)

        mins = self.seconds_focused // 60
        secs = self.seconds_focused % 60

        details = [
            f"Janela ativa: {title or 'não detectada'}",
            f"Processo: {process_name or 'não detectado'}",
            f"Classificação: {category}",
            f"Rótulo: {label}",
            f"Usuário: {self.owner_name} ({self.owner_nickname}), {self.owner_age} anos",
            f"Tempo Focado: {mins}m {secs}s / Meta: {self.target_minutes} min",
        ]
        messagebox.showinfo("Diagnóstico", "\n".join(details))

    def test_notification(self):
        ok, error = try_send_notification(
            "🐣 Teste do Tamagotchi",
            "Se você está vendo esta mensagem, as notificações estão funcionando."
        )
        if ok:
            messagebox.showinfo("Notificação", "Notificação enviada com sucesso.")
        else:
            messagebox.showwarning(
                "Notificação",
                f"Não foi possível enviar a notificação.\n\n{error}\n\n{platform_notification_tips()}"
            )

    def ask_profile_setup(
        self,
        initial_name="",
        initial_appearance="tradicional",
        initial_owner_name="",
        initial_owner_nickname="",
        initial_owner_age="",
        initial_target_minutes=60,
        first_time=False,
    ):
        dialog = tk.Toplevel(self)
        dialog.title("Configurar Perfil" if first_time else "Editar Perfil")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=COLORS["bg"])

        window_w, window_h = 340, 580
        pos_x = self.winfo_x() + (self.winfo_width() // 2) - (window_w // 2)
        pos_y = self.winfo_y() + (self.winfo_height() // 2) - (window_h // 2)
        dialog.geometry(f"{window_w}x{window_h}+{pos_x}+{pos_y}")

        card = tk.Frame(dialog, bg=COLORS["card"], highlightbackground=COLORS["card_border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        title_text = "✨ Novo Perfil" if first_time else "✏️ Editar Perfil"
        tk.Label(
            card, text=title_text, font=("Segoe UI", 12, "bold"),
            fg=COLORS["text"], bg=COLORS["card"]
        ).pack(pady=(12, 10))

        # Campo: Seu Nome
        tk.Label(
            card, text="SEU NOME", font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["card"]
        ).pack(anchor="w", padx=20, pady=(0, 2))
        f_owner_name = tk.Frame(card, bg=COLORS["track"], bd=0)
        f_owner_name.pack(padx=20, pady=(0, 8), fill="x")
        entry_owner_name = tk.Entry(
            f_owner_name, font=("Segoe UI", 9), bg=COLORS["track"],
            fg=COLORS["text"], bd=0, relief="flat"
        )
        entry_owner_name.pack(padx=8, pady=5, fill="x")
        entry_owner_name.insert(0, initial_owner_name)

        # Campo: Seu Apelido e Idade
        row_user_info = tk.Frame(card, bg=COLORS["card"])
        row_user_info.pack(padx=20, pady=(0, 8), fill="x")

        col_nick = tk.Frame(row_user_info, bg=COLORS["card"])
        col_nick.pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Label(
            col_nick, text="APELIDO", font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["card"]
        ).pack(anchor="w", pady=(0, 2))
        f_nick = tk.Frame(col_nick, bg=COLORS["track"], bd=0)
        f_nick.pack(fill="x")
        entry_owner_nickname = tk.Entry(
            f_nick, font=("Segoe UI", 9), bg=COLORS["track"],
            fg=COLORS["text"], bd=0, relief="flat"
        )
        entry_owner_nickname.pack(padx=8, pady=5, fill="x")
        entry_owner_nickname.insert(0, initial_owner_nickname)

        col_age = tk.Frame(row_user_info, bg=COLORS["card"])
        col_age.pack(side="right", fill="x", expand=True, padx=(4, 0))
        tk.Label(
            col_age, text="IDADE", font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["card"]
        ).pack(anchor="w", pady=(0, 2))
        f_age = tk.Frame(col_age, bg=COLORS["track"], bd=0)
        f_age.pack(fill="x")
        entry_owner_age = tk.Entry(
            f_age, font=("Segoe UI", 9), bg=COLORS["track"],
            fg=COLORS["text"], bd=0, relief="flat"
        )
        entry_owner_age.pack(padx=8, pady=5, fill="x")
        entry_owner_age.insert(0, initial_owner_age)

        # Campo: Meta de Trabalho (Minutos)
        tk.Label(
            card, text="META DE TRABALHO (MINUTOS)", font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["card"]
        ).pack(anchor="w", padx=20, pady=(0, 2))
        f_target = tk.Frame(card, bg=COLORS["track"], bd=0)
        f_target.pack(padx=20, pady=(0, 8), fill="x")
        entry_target_minutes = tk.Entry(
            f_target, font=("Segoe UI", 9), bg=COLORS["track"],
            fg=COLORS["text"], bd=0, relief="flat"
        )
        entry_target_minutes.pack(padx=8, pady=5, fill="x")
        entry_target_minutes.insert(0, str(initial_target_minutes))

        # Campo: Nome do Pet
        tk.Label(
            card, text="NOME DO PET", font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["card"]
        ).pack(anchor="w", padx=20, pady=(0, 2))
        entry_frame = tk.Frame(card, bg=COLORS["track"], bd=0)
        entry_frame.pack(padx=20, pady=(0, 8), fill="x")
        entry_name = tk.Entry(
            entry_frame, font=("Segoe UI", 9), bg=COLORS["track"],
            fg=COLORS["text"], bd=0, relief="flat"
        )
        entry_name.pack(padx=8, pady=5, fill="x")
        entry_name.insert(0, initial_name)

        # Campo: Aparência
        tk.Label(
            card, text="APARÊNCIA DO PET", font=("Segoe UI", 8, "bold"),
            fg=COLORS["text_muted"], bg=COLORS["card"]
        ).pack(anchor="w", padx=20, pady=(0, 4))

        selected_appearance = tk.StringVar(value=initial_appearance)
        btn_dict = {}

        def select_type(val):
            selected_appearance.set(val)
            for key, btn in btn_dict.items():
                if key == val:
                    btn._render(COLORS["primary"])
                    btn.fg = "#ffffff"
                    btn.itemconfig(btn.text_id, fill="#ffffff")
                else:
                    btn._render(COLORS["track"])
                    btn.fg = COLORS["text"]
                    btn.itemconfig(btn.text_id, fill=COLORS["text"])

        grid_frame = tk.Frame(card, bg=COLORS["card"])
        grid_frame.pack(padx=20, pady=(0, 12), fill="x")

        for idx, (label_text, value) in enumerate(APPEARANCE_OPTIONS):
            r, c = divmod(idx, 2)
            is_selected = (value == initial_appearance)
            bg_color = COLORS["primary"] if is_selected else COLORS["track"]
            fg_color = "#ffffff" if is_selected else COLORS["text"]

            btn = RoundedButton(
                grid_frame, text=label_text,
                command=lambda v=value: select_type(v),
                bg=bg_color, fg=fg_color, hover_bg=COLORS["primary_dark"],
                width=125, height=30, parent_bg=COLORS["card"]
            )
            btn.grid(row=r, column=c, padx=4, pady=3)
            btn_dict[value] = btn

        # Botão Salvar
        def save():
            name = entry_name.get().strip() or "Tama"
            appearance = selected_appearance.get()
            owner_name = entry_owner_name.get().strip() or "Amigo"
            owner_nickname = entry_owner_nickname.get().strip() or owner_name
            owner_age = entry_owner_age.get().strip() or ""
            try:
                target_minutes = int(entry_target_minutes.get().strip())
            except ValueError:
                target_minutes = 60

            self.pet_name = name
            self.appearance = appearance
            self.owner_name = owner_name
            self.owner_nickname = owner_nickname
            self.owner_age = owner_age
            self.target_minutes = target_minutes

            self.persist_state()
            self.title(f"🐣 {self.pet_name} — Tamagotchi da Produtividade")
            dialog.destroy()

        btn_save = RoundedButton(
            card, text="Confirmar", command=save,
            bg=COLORS["primary"], fg="#ffffff", hover_bg=COLORS["primary_dark"],
            width=260, height=36, parent_bg=COLORS["card"]
        )
        btn_save.pack(pady=(0, 8))

        entry_owner_name.focus_set()
        dialog.wait_window(dialog)
        return (
            self.pet_name,
            self.appearance,
            self.owner_name,
            self.owner_nickname,
            self.owner_age,
            self.target_minutes,
        )

    def edit_profile(self):
        (
            name,
            appearance,
            owner_name,
            owner_nickname,
            owner_age,
            target_minutes,
        ) = self.ask_profile_setup(
            initial_name=self.pet_name,
            initial_appearance=self.appearance,
            initial_owner_name=self.owner_name,
            initial_owner_nickname=self.owner_nickname,
            initial_owner_age=self.owner_age,
            initial_target_minutes=self.target_minutes,
            first_time=False,
        )
        self.pet_name = name
        self.appearance = appearance
        self.owner_name = owner_name
        self.owner_nickname = owner_nickname
        self.owner_age = owner_age
        self.target_minutes = target_minutes

        self.label_name.config(text=self.pet_name)
        self.refresh_stats()


if __name__ == "__main__":
    app = Tamagotchi()
    app.mainloop()