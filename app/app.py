"""
Spam Detector - 트레이 상주형 메모장 스타일 데스크탑 앱.

기능:
- 트레이 아이콘으로 상주, 더블클릭/메뉴로 작은 메모창 토글
- 이메일 4필드(제목/발신자/본문/첨부) 입력 -> 3단계 판정(🔴스팸/🟡검토/🟢정상) -> MySQL(messages) 저장
- 🚫 스팸 / ✅ 정상 으로 사용자 직접 등록(user_reports) -> 재학습용 피드백
- 트레이 메뉴 "최근 기록" -> 이력/통계 보조창
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
from PIL import Image, ImageDraw
import pandas as pd

from src.predict import SpamPredictor
from src import database
from config.config import DEMO_PATH, SPAM_THRESHOLD

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

APP_TITLE = "Spam Detector"

FONT = ("Malgun Gothic", 13)
FONT_SMALL = ("Malgun Gothic", 11)
FONT_RESULT = ("Malgun Gothic", 13, "bold")

ACCENT = "#2e86de"
COLOR_SPAM_TEXT, COLOR_SPAM_BG = "#c0392b", "#fdecea"
COLOR_REVIEW_TEXT, COLOR_REVIEW_BG = "#b7791f", "#fef9e7"
COLOR_HAM_TEXT, COLOR_HAM_BG = "#1e8449", "#eafaf1"
COLOR_NEUTRAL_TEXT, COLOR_NEUTRAL_BG = "#7f8c8d", "#f4f6f7"
COLOR_INFO_TEXT = "#2e86de"

# tier('spam'|'review'|'ham') -> (표시 이모지/문구, 글자색, 배경색)  SPEC.md 7장 색 매핑
TIER_DISPLAY = {
    "spam": ("🔴 스팸", COLOR_SPAM_TEXT, COLOR_SPAM_BG),
    "review": ("🟡 검토 필요", COLOR_REVIEW_TEXT, COLOR_REVIEW_BG),
    "ham": ("🟢 정상", COLOR_HAM_TEXT, COLOR_HAM_BG),
}


def make_tray_image():
    """리소스 파일 없이 즉석에서 트레이 아이콘 이미지 생성."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 14, 60, 50), radius=8, fill=(46, 134, 222, 255))
    d.polygon([(8, 18), (32, 36), (56, 18)], outline=(255, 255, 255, 255), width=3)
    return img


class HistoryWindow(ctk.CTkToplevel):
    """트레이 메뉴 "최근 기록"으로 여는 이력/통계 보조창."""

    def __init__(self, master):
        super().__init__(master)
        self.title("최근 판정 결과")
        self.geometry("560x420")

        self.stats_label = ctk.CTkLabel(self, text="", font=FONT_SMALL, anchor="w")
        self.stats_label.pack(fill="x", padx=12, pady=(12, 6))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", rowheight=26, font=FONT_SMALL, borderwidth=0)
        style.configure("Treeview.Heading", font=FONT_SMALL)

        columns = ("time", "label", "prob", "content")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=12)
        headings = {"time": "시각", "label": "판정", "prob": "확률", "content": "내용"}
        widths = {"time": 90, "label": 60, "prob": 60, "content": 320}
        for c in columns:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.refresh()

    def refresh(self):
        try:
            rows = database.fetch_recent(20)
            stats = database.fetch_stats()
            reports = database.count_reports()
            self.stats_label.configure(
                text=f"판정 {stats['total'] or 0}건  |  🚫 스팸 {stats['spam_count'] or 0}  "
                     f"|  ✅ 정상 {stats['ham_count'] or 0}      "
                     f"[사용자 등록 {reports['total'] or 0}건]")
        except Exception as e:
            self.stats_label.configure(text=f"(통계 조회 실패 - MySQL 확인: {e})")
            rows = []
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            content = (r["content"][:45] + "…") if len(r["content"]) > 45 else r["content"]
            self.tree.insert("", "end", values=(
                r["created_at"].strftime("%m-%d %H:%M"), r["predicted_label"],
                f"{r['spam_prob']:.0%}", content))


class SpamDetectorApp:
    def __init__(self):
        self.predictor = SpamPredictor()  # 모델 없으면 SystemExit

        self.root = ctk.CTk()
        self.root.title(APP_TITLE)
        self.root.geometry("380x460")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_main)

        self.history_win = None
        self._build_main_window()
        self.root.withdraw()  # 시작 시 창 없이 트레이만 표시

        self.tray_icon = None
        self._start_tray()

    def _build_main_window(self):
        self.root.grid_columnconfigure(0, weight=1)

        header = ctk.CTkLabel(self.root, text="📧 Spam Detector", font=FONT)
        header.grid(row=0, column=0, sticky="w", padx=14, pady=(14, 4))

        field_row = ctk.CTkFrame(self.root, fg_color="transparent")
        field_row.grid(row=1, column=0, sticky="ew", padx=14, pady=4)
        field_row.grid_columnconfigure((0, 1), weight=1)
        self.subject_entry = ctk.CTkEntry(field_row, placeholder_text="제목", font=FONT_SMALL)
        self.subject_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.sender_entry = ctk.CTkEntry(field_row, placeholder_text="발신자", font=FONT_SMALL)
        self.sender_entry.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.body_box = ctk.CTkTextbox(self.root, height=110, font=FONT_SMALL, corner_radius=10)
        self.body_box.grid(row=2, column=0, sticky="ew", padx=14, pady=4)

        self.attachment_entry = ctk.CTkEntry(
            self.root, placeholder_text="첨부파일명 (선택, 예: invoice.pdf)", font=FONT_SMALL)
        self.attachment_entry.grid(row=3, column=0, sticky="ew", padx=14, pady=4)

        btn_row = ctk.CTkFrame(self.root, fg_color="transparent")
        btn_row.grid(row=4, column=0, sticky="ew", padx=14, pady=4)
        ctk.CTkButton(btn_row, text="🔍 판정", width=100, fg_color=ACCENT,
                      command=self.on_check).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="🚫", width=40, fg_color=COLOR_SPAM_TEXT,
                      hover_color="#a93226",
                      command=lambda: self.on_report("spam")).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="✅", width=40, fg_color=COLOR_HAM_TEXT,
                      hover_color="#186a3b",
                      command=lambda: self.on_report("ham")).pack(side="left", padx=4)

        self.result_label = ctk.CTkLabel(
            self.root, text="제목/본문을 입력하고 판정을 눌러주세요.",
            font=FONT_RESULT, text_color=COLOR_NEUTRAL_TEXT, fg_color=COLOR_NEUTRAL_BG,
            corner_radius=10, height=60, wraplength=340, justify="left")
        self.result_label.grid(row=5, column=0, sticky="ew", padx=14, pady=(8, 14))

    def set_result(self, text, text_color, bg_color):
        self.result_label.configure(text=text, text_color=text_color, fg_color=bg_color)

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
        return "\n".join(parts)

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
        tier, prob = self.predictor.predict_email_tier(
            subject=subject, sender=sender, body=body, attachment=attachment)
        label_text, text_color, bg_color = TIER_DISPLAY[tier]
        self.set_result(f"{label_text}   (스팸 확률 {prob:.1%})", text_color, bg_color)

        content = self._compose_content(subject, sender, body, attachment)
        # messages.predicted_label 은 ENUM('ham','spam') 이라 'review' 저장 불가 -> 이진 임계값으로 매핑
        db_label = "spam" if prob >= SPAM_THRESHOLD else "ham"
        try:
            database.save_prediction(content, db_label, prob, sender=sender or None)
        except Exception as e:
            print(f"(저장 실패: {e})")
        self._clear_fields()
        self._refresh_history_if_open()

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
        self._refresh_history_if_open()

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
            lines.append(f"[정답 {r['label']} / 예측 {r['pred']}] {r['text'][:45]}")
        self._popup_text("\n".join(lines), title="데모 샘플 시연 결과")

    def _popup_text(self, text, title="알림"):
        win = ctk.CTkToplevel(self.root)
        win.title(title)
        win.geometry("420x360")
        box = ctk.CTkTextbox(win, font=FONT_SMALL)
        box.pack(fill="both", expand=True, padx=10, pady=10)
        box.insert("1.0", text)
        box.configure(state="disabled")

    # --- 이력 보조창 ---

    def open_history(self):
        if self.history_win is not None and self.history_win.winfo_exists():
            self.history_win.lift()
            self.history_win.focus()
            return
        self.history_win = HistoryWindow(self.root)

    def _refresh_history_if_open(self):
        if self.history_win is not None and self.history_win.winfo_exists():
            self.history_win.refresh()

    # --- 메인 창 표시/숨김 (트레이 상주) ---

    def show_main(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_main(self):
        self.root.withdraw()

    def toggle_main(self):
        if self.root.state() == "withdrawn":
            self.show_main()
        else:
            self.hide_main()

    # --- 시스템 트레이 ---

    def _start_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("열기", lambda icon, item: self.root.after(0, self.toggle_main),
                              default=True),
            pystray.MenuItem("최근 기록", lambda icon, item: self.root.after(0, self.open_history)),
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
