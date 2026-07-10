"""
Spam Detector - 트레이 상주형 다크 카드 UI 데스크탑 앱.

기능:
- 트레이 아이콘으로 상주, 더블클릭/메뉴로 커스텀 다크 창 토글
- 좌측 사이드바로 홈(판정)/기록/Gmail 3개 페이지 전환
- 이메일 4필드(제목/발신자/본문/첨부) 입력 -> 3단계 판정(스팸/검토/정상) -> MySQL(messages) 저장
- 스팸 / 정상 으로 사용자 직접 등록(user_reports) -> 재학습용 피드백
- "기록" 페이지 -> 최근 판정 이력/통계
- "Gmail" 페이지 -> 최근 메일 가져와 판정·저장 (최초 1회 브라우저 인증 필요)
- 트레이 메뉴 "데모 시연" -> 데모 샘플(demo_samples.csv)로 성능 시연

실행: python app/app.py
"""
import os
import sys
import threading
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw, ImageTk
import pandas as pd

from src.predict import SpamPredictor
from src.predict_router import predict_email_tier_auto
from src import database
from config.config import DEMO_PATH, SPAM_THRESHOLD, GMAIL_PAGE_SIZE

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_TITLE = "Spam Detector"

FONT = ("Malgun Gothic", 13)
FONT_SMALL = ("Malgun Gothic", 11)
FONT_RESULT = ("Malgun Gothic", 13, "bold")
FONT_BTN = ("Malgun Gothic", 13, "bold")
FONT_STAT = ("Malgun Gothic", 20, "bold")

# --- 다크 카드 팔레트 (PC Manager 스타일 레퍼런스 기준) ---
BG = "#15151f"
SIDEBAR_BG = "#1b1b26"
CARD_BG = "#20212e"
CARD_BG_ALT = "#262738"
TEXT = "#f0f1f5"
TEXT_MUTED = "#8b8c9c"
ACCENT = "#34a8ff"
ACCENT_HOVER = "#2b8fdb"

COLOR_SPAM_TEXT, COLOR_SPAM_BG = "#ff6b6b", "#3a1f24"
COLOR_REVIEW_TEXT, COLOR_REVIEW_BG = "#ffce54", "#3a331c"
COLOR_HAM_TEXT, COLOR_HAM_BG = "#4cd97b", "#1c3327"
COLOR_NEUTRAL_TEXT, COLOR_NEUTRAL_BG = TEXT_MUTED, CARD_BG_ALT
COLOR_INFO_TEXT = ACCENT

# tier('spam'|'review'|'ham') -> (표시 문구, 글자색, 배경색)  SPEC.md 7장 색 매핑 (● = 색 도트, 아이콘 대신 색으로 구분)
TIER_DISPLAY = {
    "spam": ("● 스팸", COLOR_SPAM_TEXT, COLOR_SPAM_BG),
    "review": ("● 검토 필요", COLOR_REVIEW_TEXT, COLOR_REVIEW_BG),
    "ham": ("● 정상", COLOR_HAM_TEXT, COLOR_HAM_BG),
}

ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "img")

GMAIL_FILTER_MAP = {"스팸": "spam", "정상": "ham", "전체": None}


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def load_icon(filename, color, size=20):
    """data/img 의 단색 실루엣 PNG(투명배경)을 지정 색으로 재색상 처리해 CTkImage 로 반환."""
    img = Image.open(os.path.join(ICON_DIR, filename)).convert("RGBA")
    alpha = img.split()[3]
    solid = Image.new("RGBA", img.size, _hex_to_rgb(color) + (0,))
    solid.putalpha(alpha)
    solid = solid.resize((size, size), Image.LANCZOS)
    return ctk.CTkImage(light_image=solid, dark_image=solid, size=(size, size))


def make_tray_image():
    """리소스 파일 없이 즉석에서 트레이 아이콘 이미지 생성."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 14, 60, 50), radius=8, fill=(52, 168, 255, 255))
    d.polygon([(8, 18), (32, 36), (56, 18)], outline=(255, 255, 255, 255), width=3)
    return img


class SpamDetectorApp:
    def __init__(self):
        self.predictor = SpamPredictor()  # 모델 없으면 SystemExit

        self.root = ctk.CTk()
        self.root.title(APP_TITLE)
        self.root.overrideredirect(True)
        self.root.geometry("1024x640")
        self.root.configure(fg_color=BG)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self.nav_buttons = {}
        self.active_page = None
        self._gmail_importing = False
        self.gmail_page = 0
        self.gmail_label_filter = "spam"
        self._drag_x = 0
        self._drag_y = 0

        self._build_titlebar()
        self._build_sidebar()
        self._build_content()
        self.show_page("home")

        self._set_window_icon()
        self._force_taskbar_icon()

        self.tray_icon = None
        self._start_tray()

    def _set_window_icon(self):
        self._icon_photo = ImageTk.PhotoImage(make_tray_image())
        self.root.iconphoto(True, self._icon_photo)

    def _force_taskbar_icon(self):
        """overrideredirect(True) 창은 기본적으로 작업표시줄에서 숨겨지므로,
        Windows 확장 윈도우 스타일을 직접 바꿔 작업표시줄 아이콘을 강제로 표시."""
        try:
            import ctypes
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            self.root.withdraw()
            self.root.after(10, self.root.deiconify)
        except Exception:
            pass

    # --- 커스텀 타이틀바 (OS 제목표시줄 없음, 직접 드래그) ---

    def _build_titlebar(self):
        titlebar = ctk.CTkFrame(self.root, fg_color=SIDEBAR_BG, height=40, corner_radius=0)
        titlebar.grid(row=0, column=0, columnspan=2, sticky="ew")
        titlebar.pack_propagate(False)

        icon_lbl = ctk.CTkLabel(titlebar, image=load_icon("gmail_683155.png", ACCENT, 18), text="")
        icon_lbl.pack(side="left", padx=(14, 6))
        label = ctk.CTkLabel(titlebar, text="Spam Detector", font=FONT, text_color=TEXT)
        label.pack(side="left")

        ctk.CTkButton(titlebar, image=load_icon("cancel_8532373.png", TEXT_MUTED, 12),
                      text="", width=32, height=28, corner_radius=6,
                      fg_color="transparent", hover_color=COLOR_SPAM_BG,
                      command=self.hide_main).pack(side="right", padx=(0, 8), pady=6)
        ctk.CTkButton(titlebar, image=load_icon("minimise_11450898.png", TEXT_MUTED, 12),
                      text="", width=32, height=28, corner_radius=6,
                      fg_color="transparent", hover_color=CARD_BG_ALT,
                      command=self.hide_main).pack(side="right", padx=0, pady=6)

        for widget in (titlebar, icon_lbl, label):
            widget.bind("<ButtonPress-1>", self._start_move)
            widget.bind("<B1-Motion>", self._do_move)

    def _start_move(self, event):
        self._drag_x, self._drag_y = event.x, event.y

    def _do_move(self, event):
        x = self.root.winfo_pointerx() - self._drag_x
        y = self.root.winfo_pointery() - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    # --- 좌측 아이콘 사이드바 ---

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self.root, fg_color=SIDEBAR_BG, width=36, corner_radius=0)
        sidebar.grid(row=1, column=0, sticky="ns")
        sidebar.pack_propagate(False)

        nav_items = [
            ("home", "home-page_3405248.png"),
            ("history", "list_151917.png"),
            ("gmail", "gmail_683155.png"),
            ("trusted", "favorite_17110228.png"),
        ]
        self.nav_icons = {}
        for i, (key, filename) in enumerate(nav_items):
            self.nav_icons[key] = {
                "inactive": load_icon(filename, TEXT_MUTED, 18),
                "active": load_icon(filename, TEXT, 18),
            }
            btn = ctk.CTkButton(
                sidebar, image=self.nav_icons[key]["inactive"], text="",
                width=36, height=36, corner_radius=8,
                fg_color="transparent", hover_color=CARD_BG,
                command=lambda k=key: self.show_page(k))
            btn.pack(pady=(16 if i == 0 else 6, 0))
            self.nav_buttons[key] = btn

        ctk.CTkFrame(sidebar, fg_color="transparent").pack(fill="both", expand=True)

        ctk.CTkButton(sidebar, text="⏻", width=36, height=36, corner_radius=8,
                      font=("Malgun Gothic", 14), fg_color="transparent",
                      text_color=TEXT_MUTED, hover_color=COLOR_SPAM_BG,
                      command=self.quit_app).pack(pady=(0, 16))

    # --- 콘텐츠 영역 (페이지 전환) ---

    def _build_content(self):
        content = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        content.grid(row=1, column=1, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self.page_home = self._build_home_page(content)
        self.page_history = self._build_history_page(content)
        self.page_gmail = self._build_gmail_page(content)
        self.page_trusted = self._build_trusted_page(content)
        for p in (self.page_home, self.page_history, self.page_gmail, self.page_trusted):
            p.grid(row=0, column=0, sticky="nsew")

    def show_page(self, name):
        {"home": self.page_home, "history": self.page_history,
         "gmail": self.page_gmail, "trusted": self.page_trusted}[name].tkraise()
        self.active_page = name
        for key, btn in self.nav_buttons.items():
            active = key == name
            btn.configure(fg_color=(ACCENT if active else "transparent"),
                          image=self.nav_icons[key]["active" if active else "inactive"])
        if name == "history":
            self._refresh_history()
        if name == "gmail":
            self._refresh_gmail_list()
        if name == "trusted":
            self._refresh_trusted_list()
        self._refresh_stats()

    # --- 홈 페이지: 입력 / 결과 / 통계 카드 ---

    def _build_home_page(self, parent):
        page = ctk.CTkFrame(parent, fg_color=BG)

        input_card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=14)
        input_card.pack(fill="both", expand=True, padx=16, pady=(16, 10))

        field_row = ctk.CTkFrame(input_card, fg_color="transparent")
        field_row.pack(fill="x", padx=14, pady=(14, 6))
        field_row.grid_columnconfigure((0, 1), weight=1)
        self.subject_entry = ctk.CTkEntry(field_row, placeholder_text="제목", font=FONT_SMALL,
                                           fg_color=BG, border_color=CARD_BG_ALT, text_color=TEXT)
        self.subject_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.sender_entry = ctk.CTkEntry(field_row, placeholder_text="발신자", font=FONT_SMALL,
                                          fg_color=BG, border_color=CARD_BG_ALT, text_color=TEXT)
        self.sender_entry.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.body_box = ctk.CTkTextbox(input_card, height=90, font=FONT_SMALL, corner_radius=10,
                                        fg_color=BG, text_color=TEXT)
        self.body_box.pack(fill="both", expand=True, padx=14, pady=6)

        self.attachment_entry = ctk.CTkEntry(
            input_card, placeholder_text="첨부파일명 (선택, 예: invoice.pdf)", font=FONT_SMALL,
            fg_color=BG, border_color=CARD_BG_ALT, text_color=TEXT)
        self.attachment_entry.pack(fill="x", padx=14, pady=(0, 6))

        ctk.CTkButton(input_card, text="판정하기", height=42, corner_radius=10,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, font=FONT_BTN,
                      command=self.on_check).pack(fill="x", padx=14, pady=(6, 14))

        result_card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=14)
        result_card.pack(fill="x", padx=16, pady=10)
        self.result_chip = ctk.CTkLabel(
            result_card, text="제목/본문을 입력하고 판정하기를 눌러주세요.",
            font=FONT_RESULT, text_color=COLOR_NEUTRAL_TEXT, fg_color=COLOR_NEUTRAL_BG,
            corner_radius=10, height=50, wraplength=580, justify="left")
        self.result_chip.pack(fill="x", padx=14, pady=(14, 8))

        report_row = ctk.CTkFrame(result_card, fg_color="transparent")
        report_row.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkButton(report_row, text="스팸으로 등록", corner_radius=8,
                      fg_color=COLOR_SPAM_BG, text_color=COLOR_SPAM_TEXT, hover_color="#4a262c",
                      command=lambda: self.on_report("spam")).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(report_row, text="정상으로 등록", corner_radius=8,
                      fg_color=COLOR_HAM_BG, text_color=COLOR_HAM_TEXT, hover_color="#234030",
                      command=lambda: self.on_report("ham")).pack(side="left", expand=True, fill="x", padx=(4, 0))

        stats_card = ctk.CTkFrame(page, fg_color=CARD_BG_ALT, corner_radius=14)
        stats_card.pack(fill="x", padx=16, pady=10)
        stats_row = ctk.CTkFrame(stats_card, fg_color="transparent")
        stats_row.pack(fill="x", padx=14, pady=14)
        stats_row.grid_columnconfigure((0, 1, 2), weight=1)
        self.stat_total_label = self._make_stat(stats_row, 0, "판정 건수")
        self.stat_spam_label = self._make_stat(stats_row, 1, "스팸")
        self.stat_ham_label = self._make_stat(stats_row, 2, "정상")

        return page

    def _make_stat(self, parent, col, caption):
        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=0, column=col, sticky="ew")
        num_label = ctk.CTkLabel(cell, text="0", font=FONT_STAT, text_color=ACCENT)
        num_label.pack()
        ctk.CTkLabel(cell, text=caption, font=FONT_SMALL, text_color=TEXT_MUTED).pack()
        return num_label

    def _refresh_stats(self):
        try:
            stats = database.fetch_stats()
            self.stat_total_label.configure(text=str(stats["total"] or 0))
            self.stat_spam_label.configure(text=str(stats["spam_count"] or 0))
            self.stat_ham_label.configure(text=str(stats["ham_count"] or 0))
        except Exception:
            for lbl in (self.stat_total_label, self.stat_spam_label, self.stat_ham_label):
                lbl.configure(text="-")

    # --- 기록 페이지 ---

    def _build_history_page(self, parent):
        page = ctk.CTkFrame(parent, fg_color=BG)
        ctk.CTkLabel(page, text="최근 판정 기록", font=FONT, text_color=TEXT).pack(
            anchor="w", padx=16, pady=(16, 6))

        card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=14)
        card.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Dark.Treeview", background=CARD_BG, fieldbackground=CARD_BG,
                         foreground=TEXT, borderwidth=0, rowheight=26, font=FONT_SMALL)
        style.configure("Dark.Treeview.Heading", background=CARD_BG_ALT, foreground=TEXT_MUTED,
                         font=FONT_SMALL, relief="flat")
        style.map("Dark.Treeview", background=[("selected", ACCENT)], foreground=[("selected", TEXT)])
        style.map("Dark.Treeview.Heading", background=[("active", CARD_BG_ALT)])
        style.configure("Dark.Vertical.TScrollbar", background=CARD_BG_ALT,
                         troughcolor=CARD_BG, bordercolor=CARD_BG,
                         arrowcolor=TEXT_MUTED, relief="flat")

        tree_area = ctk.CTkFrame(card, fg_color=CARD_BG, corner_radius=0)
        tree_area.pack(fill="both", expand=True, padx=10, pady=10)
        tree_area.grid_rowconfigure(0, weight=1)
        tree_area.grid_columnconfigure(0, weight=1)

        columns = ("time", "label", "prob", "content")
        self.tree = ttk.Treeview(tree_area, columns=columns, show="headings", height=14,
                                  style="Dark.Treeview")
        headings = {"time": "시각", "label": "판정", "prob": "확률", "content": "제목"}
        widths = {"time": 90, "label": 60, "prob": 60, "content": 420}
        for c in columns:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w", stretch=(c == "content"))
        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(tree_area, orient="vertical", command=self.tree.yview,
                             style="Dark.Vertical.TScrollbar")
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        return page

    def _title_preview(self, content, limit=80):
        text = content.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").replace("\t", " ").strip()
        if text.startswith("제목: "):
            text = text[len("제목: "):]
        return (text[:limit] + "…") if len(text) > limit else text

    def _refresh_history(self):
        try:
            rows = database.fetch_recent(20)
        except Exception:
            rows = []
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            content = self._title_preview(r["content"])
            self.tree.insert("", "end", values=(
                r["created_at"].strftime("%m-%d %H:%M"), r["predicted_label"],
                f"{r['spam_prob']:.0%}", content))

    def _refresh_data(self):
        self._refresh_stats()
        self._refresh_history()

    # --- Gmail 페이지 ---

    def _build_gmail_page(self, parent):
        page = ctk.CTkFrame(parent, fg_color=BG)

        list_card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=14)
        list_card.pack(fill="both", expand=True, padx=16, pady=16)

        header_row = ctk.CTkFrame(list_card, fg_color="transparent")
        header_row.pack(fill="x", padx=14, pady=(14, 4))
        ctk.CTkLabel(header_row, text="가져온 메일 목록", font=FONT, text_color=TEXT).pack(side="left")
        self.gmail_select_all_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(header_row, text="전체 선택", variable=self.gmail_select_all_var,
                         command=self._toggle_select_all_gmail, font=FONT_SMALL,
                         text_color=TEXT_MUTED, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                         border_color=CARD_BG_ALT).pack(side="right", padx=(0, 10))
        ctk.CTkButton(header_row, text="가져오기", width=100, height=30, corner_radius=8,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, font=FONT_SMALL,
                      command=self.on_gmail_import).pack(side="right", padx=(0, 10))

        filter_row = ctk.CTkFrame(list_card, fg_color="transparent")
        filter_row.pack(fill="x", padx=18, pady=(0, 1))
        self.gmail_filter_seg = ctk.CTkSegmentedButton(
            filter_row, values=list(GMAIL_FILTER_MAP.keys()), command=self.on_gmail_filter_change,
            width=280, height=38, fg_color=CARD_BG_ALT, selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER, unselected_color=CARD_BG_ALT,
            unselected_hover_color=CARD_BG, text_color=TEXT,
            font=("Malgun Gothic", 13, "bold"))
        self.gmail_filter_seg.set("스팸")
        self.gmail_filter_seg.pack(side="left")

        self.gmail_status_label = ctk.CTkLabel(list_card, text="", font=FONT_SMALL,
                                                text_color=TEXT_MUTED, wraplength=900, justify="left",
                                                height=1)
        self.gmail_status_label.pack(anchor="w", padx=14, pady=(0, 0))

        self.gmail_list_frame = ctk.CTkScrollableFrame(list_card, fg_color=CARD_BG, height=300)
        self.gmail_list_frame.pack(fill="both", expand=True, padx=10, pady=(1, 4))
        self.gmail_checks = {}

        page_row = ctk.CTkFrame(list_card, fg_color="transparent")
        page_row.pack(fill="x", padx=14, pady=(0, 10))
        self.gmail_prev_btn = ctk.CTkButton(page_row, text="◀ 이전", width=80, height=28,
                                             corner_radius=8, fg_color=CARD_BG_ALT, text_color=TEXT,
                                             hover_color=CARD_BG, font=FONT_SMALL,
                                             command=self.on_gmail_prev_page)
        self.gmail_prev_btn.pack(side="left")
        self.gmail_page_label = ctk.CTkLabel(page_row, text="1 / 1", font=FONT_SMALL,
                                              text_color=TEXT_MUTED)
        self.gmail_page_label.pack(side="left", expand=True)
        self.gmail_next_btn = ctk.CTkButton(page_row, text="다음 ▶", width=80, height=28,
                                             corner_radius=8, fg_color=CARD_BG_ALT, text_color=TEXT,
                                             hover_color=CARD_BG, font=FONT_SMALL,
                                             command=self.on_gmail_next_page)
        self.gmail_next_btn.pack(side="right")

        action_grid = ctk.CTkFrame(list_card, fg_color="transparent")
        action_grid.pack(fill="x", padx=14, pady=(0, 14))
        action_grid.grid_columnconfigure((0, 1, 2, 3), weight=1)

        buttons = [
            ("삭제\n(휴지통, 복구가능)", COLOR_SPAM_BG, COLOR_SPAM_TEXT, "#4a262c",
             lambda: self.on_gmail_bulk_action("trash")),
            ("스팸처리\n(스팸함으로)", COLOR_REVIEW_BG, COLOR_REVIEW_TEXT, "#4a4020",
             lambda: self.on_gmail_bulk_action("spam")),
            ("스팸 아님\n(정상 처리, 복귀)", COLOR_HAM_BG, COLOR_HAM_TEXT, "#234030",
             lambda: self.on_gmail_bulk_action("not_spam")),
            ("발신자 신뢰\n(항상 정상 처리)", CARD_BG_ALT, ACCENT, CARD_BG,
             self.on_gmail_trust_action),
        ]
        for col, (text, fg, tc, hover, cmd) in enumerate(buttons):
            padx = (0, 3) if col == 0 else (3, 0) if col == len(buttons) - 1 else 3
            ctk.CTkButton(action_grid, text=text, corner_radius=8, fg_color=fg, text_color=tc,
                          hover_color=hover, font=("Malgun Gothic", 11), height=48,
                          command=cmd).grid(row=0, column=col, sticky="ew", padx=padx)

        return page

    def _refresh_gmail_list(self):
        for w in self.gmail_list_frame.winfo_children():
            w.destroy()
        self.gmail_checks = {}
        self.gmail_select_all_var.set(False)

        try:
            total = database.count_gmail_pending(label=self.gmail_label_filter)
        except Exception:
            total = 0
        total_pages = max(1, -(-total // GMAIL_PAGE_SIZE))  # 올림 나눗셈
        self.gmail_page = max(0, min(self.gmail_page, total_pages - 1))

        try:
            gmail_rows = database.fetch_gmail_pending(
                GMAIL_PAGE_SIZE, self.gmail_page * GMAIL_PAGE_SIZE,
                label=self.gmail_label_filter)   # 조치완료(actioned) 제외
        except Exception:
            gmail_rows = []

        self.gmail_page_label.configure(text=f"{self.gmail_page + 1} / {total_pages}  (총 {total}건)")
        self.gmail_prev_btn.configure(state=("normal" if self.gmail_page > 0 else "disabled"))
        self.gmail_next_btn.configure(state=("normal" if self.gmail_page < total_pages - 1 else "disabled"))

        if not gmail_rows:
            ctk.CTkLabel(self.gmail_list_frame, text="가져온 메일이 없습니다.", font=FONT_SMALL,
                         text_color=TEXT_MUTED).pack(anchor="w", padx=4, pady=8)
            return

        for r in gmail_rows:
            tier_color = COLOR_SPAM_TEXT if r["predicted_label"] == "spam" else COLOR_HAM_TEXT
            sender = self._title_preview(r["sender"] or "(발신자 없음)", limit=60)
            preview = self._title_preview(r["content"], limit=200)
            var = ctk.BooleanVar(value=False)
            row = ctk.CTkFrame(self.gmail_list_frame, fg_color="transparent")
            row.pack(anchor="w", padx=4, pady=5, fill="x")
            cb = ctk.CTkCheckBox(row, text="", variable=var, width=20,
                                  fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=CARD_BG_ALT)
            cb.pack(side="left", anchor="n", pady=(2, 0))
            dot = ctk.CTkLabel(row, text="●", text_color=tier_color, font=FONT_SMALL, width=14)
            dot.pack(side="left", anchor="n", pady=(2, 0))
            text_col = ctk.CTkFrame(row, fg_color="transparent")
            text_col.pack(side="left", fill="x", expand=True)
            sender_lbl = ctk.CTkLabel(text_col, text=sender, text_color=TEXT_MUTED,
                                       font=FONT_SMALL, anchor="w")
            sender_lbl.pack(anchor="w", fill="x")
            preview_lbl = ctk.CTkLabel(text_col, text=preview, text_color=TEXT, font=FONT_SMALL, anchor="w")
            preview_lbl.pack(anchor="w", fill="x")
            for w in (dot, text_col, sender_lbl, preview_lbl):
                w.bind("<Button-1>", lambda e, v=var: v.set(not v.get()))
            self.gmail_checks[r["gmail_id"]] = var

    def _toggle_select_all_gmail(self):
        value = self.gmail_select_all_var.get()
        for var in self.gmail_checks.values():
            var.set(value)

    def on_gmail_filter_change(self, value):
        self.gmail_label_filter = GMAIL_FILTER_MAP[value]
        self.gmail_page = 0
        self._refresh_gmail_list()

    def on_gmail_prev_page(self):
        if self.gmail_page > 0:
            self.gmail_page -= 1
            self._refresh_gmail_list()

    def on_gmail_next_page(self):
        self.gmail_page += 1
        self._refresh_gmail_list()

    def on_gmail_import(self):
        if self._gmail_importing:
            return
        self._gmail_importing = True
        self.gmail_status_label.configure(text="가져오는 중… (첫 실행은 인증창이 뜰 수 있어요)",
                                           text_color=COLOR_INFO_TEXT)
        threading.Thread(target=self._gmail_import_worker, daemon=True).start()

    def _gmail_import_worker(self):
        try:
            from src.gmail_pipeline import run
            saved, total = run()
            msg = f"완료: 총 {total}건 중 신규 {saved}건 저장했습니다."
            ok = True
        except SystemExit as e:
            msg = f"Gmail 설정이 필요합니다.\n{e}"
            ok = False
        except Exception as e:
            msg = f"가져오기 실패: {e}"
            ok = False
        self.root.after(0, lambda: self._on_gmail_import_done(msg, ok))

    def _on_gmail_import_done(self, msg, ok):
        self._gmail_importing = False
        self.gmail_status_label.configure(text=msg, text_color=(COLOR_INFO_TEXT if ok else COLOR_SPAM_TEXT))
        if ok:
            self.gmail_page = 0
            self._refresh_data()
            self._refresh_gmail_list()

    def on_gmail_bulk_action(self, action):
        selected = [gid for gid, var in self.gmail_checks.items() if var.get()]
        if not selected:
            self.gmail_status_label.configure(text="선택된 메일이 없습니다.", text_color=COLOR_NEUTRAL_TEXT)
            return
        if action == "trash":
            label, warn = "휴지통 이동", "Gmail 휴지통으로 이동합니다 (30일 내 복구 가능)."
        elif action == "spam":
            label, warn = "스팸 처리", "Gmail 스팸함으로 이동합니다 (Gmail 필터 학습에도 반영됩니다)."
        else:
            label, warn = "스팸 아님 처리", "정상(ham)으로 모델 학습에 반영되고, 스팸함이면 받은편지함으로 복귀합니다."
        if not messagebox.askyesno("Gmail 조치 확인", f"선택한 {len(selected)}건을 {label}할까요?\n{warn}"):
            return
        self.gmail_status_label.configure(text=f"{label} 처리 중…", text_color=COLOR_INFO_TEXT)
        threading.Thread(target=self._gmail_bulk_worker, args=(selected, action, label), daemon=True).start()

    def _gmail_bulk_worker(self, gmail_ids, action, label):
        try:
            if action == "not_spam":
                from src.gmail_pipeline import mark_not_spam
                reported, ok_count = mark_not_spam(gmail_ids)
                msg = f"{label} 완료: 학습 반영 {reported}건, Gmail 처리 {ok_count}건"
            else:
                from src.gmail_service import apply_action
                ok_count, fail_count = apply_action(gmail_ids, action)
                msg = f"{label} 완료: 성공 {ok_count}건" + (f", 실패 {fail_count}건" if fail_count else "")
            database.mark_gmail_actioned(gmail_ids)   # 처리된 메일은 목록에서 숨김
            ok = True
        except SystemExit as e:
            msg = f"Gmail 설정이 필요합니다.\n{e}"
            ok = False
        except Exception as e:
            msg = f"{label} 실패: {e}"
            ok = False
        self.root.after(0, lambda: self._on_gmail_bulk_done(msg, ok))

    def _on_gmail_bulk_done(self, msg, ok):
        self.gmail_status_label.configure(text=msg, text_color=(COLOR_INFO_TEXT if ok else COLOR_SPAM_TEXT))
        if ok:
            self._refresh_gmail_list()

    def on_gmail_trust_action(self):
        selected = [gid for gid, var in self.gmail_checks.items() if var.get()]
        if not selected:
            self.gmail_status_label.configure(text="선택된 메일이 없습니다.", text_color=COLOR_NEUTRAL_TEXT)
            return
        if not messagebox.askyesno(
                "신뢰 발신자 등록",
                f"선택한 {len(selected)}건의 발신자를 신뢰 목록에 등록할까요?\n"
                "앞으로 이 발신자의 메일은 스팸 판정과 무관하게 항상 정상으로 처리됩니다."):
            return
        try:
            added = database.trust_senders_by_gmail_ids(selected, use_domain=False)
            self.gmail_status_label.configure(
                text=f"신뢰 발신자 등록 완료: {len(added)}명", text_color=COLOR_INFO_TEXT)
        except Exception as e:
            self.gmail_status_label.configure(text=f"신뢰 등록 실패: {e}", text_color=COLOR_SPAM_TEXT)

    # --- 신뢰 발신자 페이지 ---

    def _build_trusted_page(self, parent):
        page = ctk.CTkFrame(parent, fg_color=BG)

        add_card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=14)
        add_card.pack(fill="x", padx=16, pady=(16, 10))
        ctk.CTkLabel(add_card, text="신뢰 발신자", font=FONT, text_color=TEXT).pack(
            anchor="w", padx=14, pady=(14, 4))
        ctk.CTkLabel(
            add_card, text="등록한 이메일/도메인은 스팸 판정과 무관하게 항상 정상으로 처리됩니다.",
            font=FONT_SMALL, text_color=TEXT_MUTED, justify="left").pack(
            anchor="w", padx=14, pady=(0, 10))

        input_row = ctk.CTkFrame(add_card, fg_color="transparent")
        input_row.pack(fill="x", padx=14, pady=(0, 6))
        input_row.grid_columnconfigure((0, 1), weight=1)
        self.trusted_pattern_entry = ctk.CTkEntry(
            input_row, placeholder_text="이메일 또는 도메인 (예: naver.com)", font=FONT_SMALL,
            fg_color=BG, border_color=CARD_BG_ALT, text_color=TEXT)
        self.trusted_pattern_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.trusted_note_entry = ctk.CTkEntry(
            input_row, placeholder_text="메모 (선택)", font=FONT_SMALL,
            fg_color=BG, border_color=CARD_BG_ALT, text_color=TEXT)
        self.trusted_note_entry.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        ctk.CTkButton(add_card, text="+ 추가", height=38, corner_radius=8,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER, font=FONT_BTN,
                      command=self.on_add_trusted_sender).pack(fill="x", padx=14, pady=(0, 14))

        list_card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=14)
        list_card.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        ctk.CTkLabel(list_card, text="등록된 신뢰 발신자", font=FONT, text_color=TEXT).pack(
            anchor="w", padx=14, pady=(14, 6))
        self.trusted_list_frame = ctk.CTkScrollableFrame(list_card, fg_color=CARD_BG, height=260)
        self.trusted_list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        return page

    def _refresh_trusted_list(self):
        for w in self.trusted_list_frame.winfo_children():
            w.destroy()
        try:
            rows = database.fetch_trusted_senders()
        except Exception:
            rows = []
        if not rows:
            ctk.CTkLabel(self.trusted_list_frame, text="등록된 신뢰 발신자가 없습니다.",
                         font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=4, pady=8)
            return
        for r in rows:
            row = ctk.CTkFrame(self.trusted_list_frame, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=3)
            text = r["pattern"] + (f"   ({r['note']})" if r.get("note") else "")
            ctk.CTkLabel(row, text=text, font=FONT_SMALL, text_color=TEXT, anchor="w").pack(
                side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="삭제", width=52, height=26, corner_radius=6,
                          fg_color=COLOR_SPAM_BG, text_color=COLOR_SPAM_TEXT, hover_color="#4a262c",
                          font=FONT_SMALL,
                          command=lambda p=r["pattern"]: self.on_remove_trusted_sender(p)).pack(side="right")

    def on_add_trusted_sender(self):
        pattern = self.trusted_pattern_entry.get().strip()
        note = self.trusted_note_entry.get().strip() or None
        if not pattern:
            return
        try:
            database.add_trusted_sender(pattern, note)
        except Exception as e:
            print(f"(신뢰 발신자 추가 실패: {e})")
            return
        self.trusted_pattern_entry.delete(0, "end")
        self.trusted_note_entry.delete(0, "end")
        self._refresh_trusted_list()

    def on_remove_trusted_sender(self, pattern):
        try:
            database.remove_trusted_sender(pattern)
        except Exception as e:
            print(f"(신뢰 발신자 삭제 실패: {e})")
        self._refresh_trusted_list()

    # --- 입력 필드 헬퍼 ---

    def set_result(self, text, text_color, bg_color):
        self.result_chip.configure(text=text, text_color=text_color, fg_color=bg_color)

    def _get_fields(self):
        return (self.subject_entry.get().strip(), self.sender_entry.get().strip(),
                self.body_box.get("1.0", "end").strip(), self.attachment_entry.get().strip())

    def _compose_content(self, subject, sender, body, attachment):
        """DB 저장/이력 표시용 사람이 읽는 형태로 필드를 합침 (모델 입력 조합은 predict.py 쪽에서 처리)."""
        parts = []
        if subject:
            parts.append(f"제목: {subject}")
        if sender:
            parts.append(f"발신: {sender}")
        parts.append(body)
        if attachment:
            parts.append(f"첨부: {attachment}")
        # Gmail 경로(gmail_pipeline.py)와 동일하게 5000자로 캡(일관성, DB TEXT 과다저장 방지)
        return "\n".join(parts)[:5000]

    def _clear_fields(self):
        self.subject_entry.delete(0, "end")
        self.sender_entry.delete(0, "end")
        self.body_box.delete("1.0", "end")
        self.attachment_entry.delete(0, "end")

    # --- 이벤트 핸들러 ---

    def on_check(self):
        subject, sender, body, attachment = self._get_fields()
        if not subject and not body:
            self.set_result("제목 또는 본문을 입력하세요", COLOR_NEUTRAL_TEXT, COLOR_NEUTRAL_BG)
            return
        try:
            tier, prob, lang = predict_email_tier_auto(
                subject=subject, sender=sender, body=body, attachment=attachment)
        except SystemExit as e:
            self.set_result(f"모델이 없습니다. 먼저 학습하세요 (python src/train.py, train_en.py)\n{e}",
                             COLOR_SPAM_TEXT, COLOR_SPAM_BG)
            return
        except Exception as e:
            self.set_result(f"판정 실패: {e}", COLOR_SPAM_TEXT, COLOR_SPAM_BG)
            return
        try:
            trusted = bool(sender) and database.is_trusted(sender)
        except Exception:
            trusted = False
        if trusted:
            tier, prob = "ham", 0.0
        label_text, text_color, bg_color = TIER_DISPLAY[tier]
        lang_text = "KO" if lang == "ko" else "EN"
        result_text = f"{label_text}   (스팸 확률 {prob:.1%} · 감지 언어 {lang_text})"

        content = self._compose_content(subject, sender, body, attachment)
        # predicted_label 이 3단계(ham/review/spam)로 확장됨 -> tier 그대로 저장(표시와 일치)
        db_label = tier
        try:
            database.save_prediction(content, db_label, prob, sender=sender or None)
        except Exception as e:
            result_text += f"\n(주의: 결과 저장 실패 - {e})"
        self.set_result(result_text, text_color, bg_color)
        self._clear_fields()
        self._refresh_data()

    def on_report(self, user_label):
        subject, sender, body, attachment = self._get_fields()
        if not subject and not body:
            self.set_result("등록할 제목 또는 본문을 입력하세요", COLOR_NEUTRAL_TEXT, COLOR_NEUTRAL_BG)
            return
        content = self._compose_content(subject, sender, body, attachment)
        try:
            database.save_report(content, user_label)
            self.set_result(f"사용자 등록 완료: {user_label}", COLOR_INFO_TEXT, COLOR_NEUTRAL_BG)
        except Exception as e:
            self.set_result(f"등록 실패: {e}", COLOR_SPAM_TEXT, COLOR_SPAM_BG)
        self._clear_fields()
        self._refresh_data()

    def run_demo(self):
        if not os.path.exists(DEMO_PATH):
            self._popup_text("데모 파일이 없습니다. python src/make_seed_data.py 실행.")
            return
        df = pd.read_csv(DEMO_PATH)
        df["pred"] = df["text"].apply(lambda t: self.predictor.predict(t)[0])
        acc = (df["pred"] == df["label"]).mean()
        wrong = df[df["pred"] != df["label"]]
        lines = [f"■ 데모 샘플 {len(df)}건 정확도: {acc:.1%}",
                 f"■ 오답 {len(wrong)}건", ""]
        for _, r in wrong.head(8).iterrows():
            lines.append(f"[정답 {r['label']} / 예측 {r['pred']}] {r['text'][:70]}")
        self._popup_text("\n".join(lines), title="데모 샘플 시연 결과")

    def _popup_text(self, text, title="알림"):
        win = ctk.CTkToplevel(self.root)
        win.title(title)
        win.geometry("420x360")
        win.configure(fg_color=BG)
        box = ctk.CTkTextbox(win, font=FONT_SMALL, fg_color=CARD_BG, text_color=TEXT, corner_radius=10)
        box.pack(fill="both", expand=True, padx=10, pady=10)
        box.insert("1.0", text)
        box.configure(state="disabled")

    # --- 메인 창 표시/숨김 (트레이 상주) ---

    def show_main(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()
        self.root.after(10, lambda: self.root.attributes("-topmost", False))

    def hide_main(self):
        self.root.withdraw()

    def toggle_main(self):
        if self.root.state() == "withdrawn":
            self.show_main()
        else:
            self.hide_main()

    def _open_to(self, page_name):
        self.show_main()
        self.show_page(page_name)

    # --- 시스템 트레이 ---

    def _start_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("열기", lambda icon, item: self.root.after(0, self.toggle_main),
                              default=True),
            pystray.MenuItem("최근 기록", lambda icon, item: self.root.after(0, lambda: self._open_to("history"))),
            pystray.MenuItem("Gmail 가져오기", lambda icon, item: self.root.after(0, lambda: self._open_to("gmail"))),
            pystray.MenuItem("데모 시연", lambda icon, item: self.root.after(0, self.run_demo)),
            pystray.MenuItem("종료", lambda icon, item: self.root.after(0, self.quit_app)),
        )
        self.tray_icon = pystray.Icon(APP_TITLE, make_tray_image(), APP_TITLE, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def quit_app(self):
        if self.tray_icon is not None:
            self.tray_icon.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    try:
        app = SpamDetectorApp()
    except SystemExit as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("모델 없음", f"모델이 없습니다. 먼저 학습하세요:\n\npython src/train.py\n\n{e}")
        root.destroy()
        return
    app.run()


if __name__ == "__main__":
    main()
