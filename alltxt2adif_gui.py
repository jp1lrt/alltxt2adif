# alltxt2adif_gui.py
# v1.1 - Start button is placed directly under Step 3 so it never "disappears"

import os
import sys
import json
import ctypes
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "ALLTXT2ADIF"
CORE_SCRIPT = "convert_all_to_adif.py"

STRINGS = {
    "ja": {
        "title": "ALLTXT2ADIF - ログ復旧ツール",
        "subtitle": "WSJT-X / JTDX の ALL.TXT から ADIF を復旧します",
        "help": "ヘルプ",
        "about": "About",
        "language": "言語",
        "lang_auto": "自動",
        "lang_ja": "日本語",
        "lang_en": "English",

        "step1": "1) ALL.TXT を選択（必須）",
        "browse": "参照...",
        "where": "ALL.TXT の場所の例",
        "where_body": "WSJT-X:  %LOCALAPPDATA%\\WSJT-X\\ALL.TXT\nJTDX:    %LOCALAPPDATA%\\JTDX\\ALL.TXT\n※環境により異なります",
        "file_info": "ファイル情報:",
        "not_selected": "未選択",
        "file_ok": "読み取りOK",
        "file_ng": "読み取りNG",

        "step2": "2) あなたのコールサイン（必須）",
        "my_call": "自局コール",
        "mode": "復旧モード",
        "mode_strict": "strict（保守的・推奨）",
        "mode_lenient": "lenient（拾い過ぎ注意）",

        "step3": "3) 出力",
        "out_adif": "出力ADIFファイル",
        "save_as": "保存先...",
        "out_folder": "出力フォルダを開く",

        "advanced": "詳細設定",
        "window_sec": "lookback window（秒）",
        "window_hint": "未指定なら本体デフォルト（現在: 120秒）",
        "merge_window": "merge window（秒）",
        "review_csv": "review CSV",
        "review_on": "作成する（推奨）",
        "review_off": "作成しない（危険）",
        "review_level": "review level",
        "review_low": "lowのみ（デフォルト）",
        "review_medium": "medium+low",
        "confidence_fields": "APP_* フィールド",
        "confidence_on": "出力する（推奨）",
        "confidence_off": "出力しない（--no-confidence）",

        "start": "復旧開始",
        "cancel": "中止",
        "status_ready": "準備完了",
        "status_running": "実行中...",
        "status_done": "完了",
        "status_failed": "失敗",

        "err_core_missing": "変換本体が見つかりません:\nconvert_all_to_adif.py を同じフォルダに置いてください。",
        "err_need_alltxt": "ALL.TXT を選択してください。",
        "err_need_call": "自局コール（必須）を入力してください。",
        "err_bad_call": "コールサイン形式が不正です（英数字と/、数字と英字を含む）。",
        "err_need_output": "出力ADIFファイル（保存先）を指定してください。",
        "warn_overwrite": "既に同名のファイルがあります。\n上書きしてよいですか？",
        "warn_no_review": "review CSV を作らない設定です。\n誤検出が混ざっても気づきにくく危険です。\n本当に続行しますか？",
        "done_msg": "復旧が完了しました。\n出力フォルダを開きますか？",
        "about_msg": "ALLTXT2ADIF GUI\nLog Recovery Tool\nAuthor: JP1LRT (Yoshiharu Tsukuura)\n\n注意: ALL.TXT はデコード履歴であり公式ログではありません。\nreview CSV の確認を推奨します。",
        "help_msg": "手順:\n1) ALL.TXT を選択\n2) 自局コールを入力\n3) 保存先(ADIF)を選択\n4) 復旧開始\n\n推奨:\n・strictモード\n・review CSV 作成\n・APP_* 出力（confidence付き）",
    },
    "en": {
        "title": "ALLTXT2ADIF - Log Recovery Tool",
        "subtitle": "Recover ADIF from WSJT-X / JTDX ALL.TXT",
        "help": "Help",
        "about": "About",
        "language": "Language",
        "lang_auto": "Auto",
        "lang_ja": "日本語",
        "lang_en": "English",

        "step1": "1) Select ALL.TXT (required)",
        "browse": "Browse...",
        "where": "Typical ALL.TXT locations",
        "where_body": "WSJT-X:  %LOCALAPPDATA%\\WSJT-X\\ALL.TXT\nJTDX:    %LOCALAPPDATA%\\JTDX\\ALL.TXT\n(Your path may differ.)",
        "file_info": "File info:",
        "not_selected": "Not selected",
        "file_ok": "Readable",
        "file_ng": "Not readable",

        "step2": "2) Your callsign (required)",
        "my_call": "My Callsign",
        "mode": "Mode",
        "mode_strict": "strict (recommended)",
        "mode_lenient": "lenient (may over-match)",

        "step3": "3) Output",
        "out_adif": "Output ADIF file",
        "save_as": "Save as...",
        "out_folder": "Open output folder",

        "advanced": "Advanced",
        "window_sec": "Lookback window (sec)",
        "window_hint": "If empty, core default is used (currently: 120s)",
        "merge_window": "Merge window (sec)",
        "review_csv": "Review CSV",
        "review_on": "Create (recommended)",
        "review_off": "Do not create (risky)",
        "review_level": "Review level",
        "review_low": "low only (default)",
        "review_medium": "medium + low",
        "confidence_fields": "APP_* fields",
        "confidence_on": "Include (recommended)",
        "confidence_off": "Suppress (--no-confidence)",

        "start": "Start Recovery",
        "cancel": "Cancel",
        "status_ready": "Ready",
        "status_running": "Running...",
        "status_done": "Done",
        "status_failed": "Failed",

        "err_core_missing": "Core script not found:\nPlease place convert_all_to_adif.py in the same folder.",
        "err_need_alltxt": "Please select ALL.TXT.",
        "err_need_call": "Please enter your callsign (required).",
        "err_bad_call": "Invalid callsign format.",
        "err_need_output": "Please choose an output ADIF file path.",
        "warn_overwrite": "File already exists.\nOverwrite it?",
        "warn_no_review": "Review CSV is disabled.\nThis can be risky because false positives may be unnoticed.\nContinue anyway?",
        "done_msg": "Recovery finished.\nOpen output folder now?",
        "about_msg": "ALLTXT2ADIF GUI\nLog Recovery Tool\nAuthor: JP1LRT (Yoshiharu Tsukuura)\n\nNote: ALL.TXT is decode history, not an official log.\nReview CSV is recommended.",
        "help_msg": "Steps:\n1) Select ALL.TXT\n2) Enter callsign\n3) Choose output ADIF file\n4) Start recovery\n\nRecommended:\n- strict mode\n- Create review CSV\n- Include APP_* fields (confidence)",
    }
}

def get_settings_path() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home())
    d = Path(appdata) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d / "settings.json"

def load_settings() -> dict:
    p = get_settings_path()
    if not p.exists():
        return {"language": "auto"}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"language": "auto"}

def save_settings(settings: dict) -> None:
    p = get_settings_path()
    p.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")

def get_windows_ui_language_tag() -> str | None:
    try:
        GetUserDefaultUILanguage = ctypes.windll.kernel32.GetUserDefaultUILanguage
        langid = GetUserDefaultUILanguage()
        LCIDToLocaleName = ctypes.windll.kernel32.LCIDToLocaleName
        buf = ctypes.create_unicode_buffer(85)
        lcid = langid
        if LCIDToLocaleName(lcid, buf, len(buf), 0) != 0:
            return buf.value
    except Exception:
        pass
    return None

def choose_language() -> str:
    settings = load_settings()
    lang = (settings.get("language") or "auto").lower()
    if lang in ("ja", "en"):
        return lang
    tag = get_windows_ui_language_tag()
    if tag and tag.lower().startswith("ja"):
        return "ja"
    return "en"

def looks_like_callsign(s: str) -> bool:
    s = (s or "").strip().upper()
    if not (3 <= len(s) <= 15):
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/")
    if any(ch not in allowed for ch in s):
        return False
    has_letter = any("A" <= ch <= "Z" for ch in s)
    has_digit = any("0" <= ch <= "9" for ch in s)
    return has_letter and has_digit

def open_folder(path: str):
    try:
        os.startfile(path)
    except Exception:
        pass

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        # Set window icon (works both from source and PyInstaller bundle)
        try:
            import sys as _sys, os as _os
            from PIL import Image, ImageTk
            _base = getattr(_sys, "_MEIPASS", _os.path.dirname(_os.path.abspath(__file__)))
            _ico_path = _os.path.join(_base, "icon.ico")
            _img = Image.open(_ico_path).resize((32, 32))
            self._icon_img = ImageTk.PhotoImage(_img)
            self.iconphoto(True, self._icon_img)
            self.iconbitmap(_ico_path)
        except Exception:
            pass
        self.settings = load_settings()
        self.lang = choose_language()
        self.S = STRINGS[self.lang]

        self.title(self.S["title"])
        self.geometry("820x620")
        self.minsize(780, 560)

        self.alltxt_path = tk.StringVar(value="")
        self.my_call = tk.StringVar(value="")
        self.mode = tk.StringVar(value="strict")

        self.out_adif_path = tk.StringVar(value="")
        self.review_on = tk.BooleanVar(value=True)
        self.review_level = tk.StringVar(value="low")
        self.window_sec = tk.StringVar(value="")
        self.merge_window = tk.StringVar(value="")
        self.no_confidence = tk.BooleanVar(value=False)

        self.status = tk.StringVar(value=self.S["status_ready"])
        self.proc = None

        self._build_menu()
        self._build_ui()
        self._refresh_texts()

    def _build_menu(self):
        menubar = tk.Menu(self)
        lang_menu = tk.Menu(menubar, tearoff=0)
        lang_menu.add_command(label=self.S["lang_auto"], command=lambda: self.set_language("auto"))
        lang_menu.add_command(label=self.S["lang_ja"], command=lambda: self.set_language("ja"))
        lang_menu.add_command(label=self.S["lang_en"], command=lambda: self.set_language("en"))
        menubar.add_cascade(label=self.S["language"], menu=lang_menu)
        menubar.add_command(label=self.S["help"], command=self.show_help)
        menubar.add_command(label=self.S["about"], command=self.show_about)
        self.config(menu=menubar)

    def set_language(self, lang_value: str):
        self.settings["language"] = lang_value
        save_settings(self.settings)
        self.lang = choose_language() if lang_value == "auto" else lang_value
        self.S = STRINGS[self.lang]
        self._build_menu()
        self._refresh_texts()

    def _build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        self.lbl_title = ttk.Label(root, text="", font=("Segoe UI", 14, "bold"))
        self.lbl_title.pack(anchor="w")
        self.lbl_sub = ttk.Label(root, text="")
        self.lbl_sub.pack(anchor="w", pady=(2, 12))

        # Step 1
        self.step1 = ttk.LabelFrame(root, text="")
        self.step1.pack(fill="x", pady=6)

        r1 = ttk.Frame(self.step1)
        r1.pack(fill="x", padx=10, pady=10)
        self.ent_alltxt = ttk.Entry(r1, textvariable=self.alltxt_path, state="readonly")
        self.ent_alltxt.pack(side="left", fill="x", expand=True)
        self.btn_alltxt = ttk.Button(r1, text="", command=self.browse_alltxt)
        self.btn_alltxt.pack(side="left", padx=(8, 0))

        r1b = ttk.Frame(self.step1)
        r1b.pack(fill="x", padx=10, pady=(0, 10))
        self.lbl_info = ttk.Label(r1b, text="")
        self.lbl_info.pack(side="left", anchor="w")

        self.btn_where = ttk.Button(self.step1, text="", command=self.show_where)
        self.btn_where.pack(anchor="w", padx=10, pady=(0, 10))

        # Step 2
        self.step2 = ttk.LabelFrame(root, text="")
        self.step2.pack(fill="x", pady=6)
        f2 = ttk.Frame(self.step2)
        f2.pack(fill="x", padx=10, pady=10)

        self.lbl_call = ttk.Label(f2, text="")
        self.lbl_call.grid(row=0, column=0, sticky="w")
        self.ent_call = ttk.Entry(f2, textvariable=self.my_call)
        self.ent_call.grid(row=0, column=1, sticky="ew", padx=(10, 0))

        self.lbl_mode = ttk.Label(f2, text="")
        self.lbl_mode.grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.rb_strict = ttk.Radiobutton(f2, text="", variable=self.mode, value="strict")
        self.rb_lenient = ttk.Radiobutton(f2, text="", variable=self.mode, value="lenient")
        self.rb_strict.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(10, 0))
        self.rb_lenient.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(4, 0))

        f2.columnconfigure(1, weight=1)

        # Step 3
        self.step3 = ttk.LabelFrame(root, text="")
        self.step3.pack(fill="x", pady=6)
        f3 = ttk.Frame(self.step3)
        f3.pack(fill="x", padx=10, pady=10)

        self.lbl_out = ttk.Label(f3, text="")
        self.lbl_out.grid(row=0, column=0, sticky="w")
        self.ent_out = ttk.Entry(f3, textvariable=self.out_adif_path)
        self.ent_out.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.btn_out = ttk.Button(f3, text="", command=self.choose_outfile)
        self.btn_out.grid(row=0, column=2, padx=(8, 0))

        self.btn_open_folder = ttk.Button(f3, text="", command=self.open_output_folder)
        self.btn_open_folder.grid(row=1, column=1, sticky="w", pady=(8, 0))

        f3.columnconfigure(1, weight=1)

        # ✅ Execute buttons are placed RIGHT HERE (always visible)
        exec_row = ttk.Frame(self.step3)
        exec_row.pack(fill="x", padx=10, pady=(0, 10))
        self.btn_start = ttk.Button(exec_row, text="", command=self.start)
        self.btn_start.pack(side="left")
        self.btn_cancel = ttk.Button(exec_row, text="", command=self.cancel, state="disabled")
        self.btn_cancel.pack(side="left", padx=(10, 0))
        self.lbl_status = ttk.Label(exec_row, textvariable=self.status)
        self.lbl_status.pack(side="left", padx=(14, 0))

        # Advanced
        self.adv = ttk.LabelFrame(root, text="")
        self.adv.pack(fill="x", pady=10)
        fa = ttk.Frame(self.adv)
        fa.pack(fill="x", padx=10, pady=10)

        self.lbl_win = ttk.Label(fa, text="")
        self.lbl_win.grid(row=0, column=0, sticky="w")
        self.ent_win = ttk.Entry(fa, width=10, textvariable=self.window_sec)
        self.ent_win.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.lbl_win_hint = ttk.Label(fa, text="")
        self.lbl_win_hint.grid(row=0, column=2, sticky="w", padx=(10, 0))

        self.lbl_merge = ttk.Label(fa, text="")
        self.lbl_merge.grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.ent_merge = ttk.Entry(fa, width=10, textvariable=self.merge_window)
        self.ent_merge.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(10, 0))

        self.lbl_review = ttk.Label(fa, text="")
        self.lbl_review.grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.cb_review = ttk.Checkbutton(fa, text="", variable=self.review_on, command=self._refresh_texts)
        self.cb_review.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(10, 0))

        self.lbl_review_level = ttk.Label(fa, text="")
        self.lbl_review_level.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.rb_r_low = ttk.Radiobutton(fa, text="", variable=self.review_level, value="low")
        self.rb_r_med = ttk.Radiobutton(fa, text="", variable=self.review_level, value="medium")
        self.rb_r_low.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=(6, 0))
        self.rb_r_med.grid(row=4, column=1, sticky="w", padx=(10, 0), pady=(4, 0))

        self.lbl_conf = ttk.Label(fa, text="")
        self.lbl_conf.grid(row=5, column=0, sticky="w", pady=(10, 0))
        self.cb_no_conf = ttk.Checkbutton(fa, text="", variable=self.no_confidence, command=self._refresh_texts)
        self.cb_no_conf.grid(row=5, column=1, sticky="w", padx=(10, 0), pady=(10, 0))

        # Log box (optional, but helpful)
        self.prog = ttk.Progressbar(root, mode="indeterminate")
        self.prog.pack(fill="x", pady=(8, 0))

        self.txt_log = tk.Text(root, height=10)
        self.txt_log.pack(fill="both", expand=True, pady=(10, 0))
        self.txt_log.configure(state="disabled")

    def _refresh_texts(self):
        S = self.S
        self.title(S["title"])
        self.lbl_title.config(text=S["title"])
        self.lbl_sub.config(text=S["subtitle"])

        self.step1.config(text=S["step1"])
        self.btn_alltxt.config(text=S["browse"])
        if not self.alltxt_path.get():
            self.lbl_info.config(text=f'{S["file_info"]} {S["not_selected"]}')
        self.btn_where.config(text=S["where"])

        self.step2.config(text=S["step2"])
        self.lbl_call.config(text=S["my_call"])
        self.lbl_mode.config(text=S["mode"])
        self.rb_strict.config(text=S["mode_strict"])
        self.rb_lenient.config(text=S["mode_lenient"])

        self.step3.config(text=S["step3"])
        self.lbl_out.config(text=S["out_adif"])
        self.btn_out.config(text=S["save_as"])
        self.btn_open_folder.config(text=S["out_folder"])

        self.btn_start.config(text=S["start"])
        self.btn_cancel.config(text=S["cancel"])

        self.adv.config(text=S["advanced"])
        self.lbl_win.config(text=S["window_sec"])
        self.lbl_win_hint.config(text=S["window_hint"])
        self.lbl_merge.config(text=S["merge_window"])

        self.lbl_review.config(text=S["review_csv"])
        if self.review_on.get():
            self.cb_review.config(text=S["review_on"])
        else:
            self.cb_review.config(text=S["review_off"])

        self.lbl_review_level.config(text=S["review_level"])
        self.rb_r_low.config(text=S["review_low"])
        self.rb_r_med.config(text=S["review_medium"])

        self.lbl_conf.config(text=S["confidence_fields"])
        if self.no_confidence.get():
            self.cb_no_conf.config(text=S["confidence_off"])
        else:
            self.cb_no_conf.config(text=S["confidence_on"])

    def show_where(self):
        messagebox.showinfo(self.S["where"], self.S["where_body"])

    def show_about(self):
        messagebox.showinfo(self.S["about"], self.S["about_msg"])

    def show_help(self):
        messagebox.showinfo(self.S["help"], self.S["help_msg"])

    def browse_alltxt(self):
        p = filedialog.askopenfilename(
            title=self.S["step1"],
            filetypes=[("ALL.TXT", "ALL.TXT"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not p:
            return
        self.alltxt_path.set(p)
        self._update_file_info(p)

        if not self.out_adif_path.get():
            suggested = str(Path(p).parent / "recovered.adi")
            self.out_adif_path.set(suggested)

    def _update_file_info(self, p: str):
        try:
            st = os.stat(p)
            size_mb = st.st_size / (1024 * 1024)
            msg = f'{self.S["file_info"]} {self.S["file_ok"]} / {size_mb:.1f} MB'
            self.lbl_info.config(text=msg)
        except Exception:
            msg = f'{self.S["file_info"]} {self.S["file_ng"]}'
            self.lbl_info.config(text=msg)

    def choose_outfile(self):
        initial = self.out_adif_path.get().strip() or "recovered.adi"
        p = filedialog.asksaveasfilename(
            title=self.S["out_adif"],
            defaultextension=".adi",
            initialfile=Path(initial).name,
            filetypes=[("ADIF files", "*.adi"), ("All files", "*.*")]
        )
        if p:
            self.out_adif_path.set(p)

    def open_output_folder(self):
        p = self.out_adif_path.get().strip()
        if p:
            open_folder(str(Path(p).parent))

    def log(self, line: str):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", line + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def validate(self) -> bool:
        core = Path(__file__).with_name(CORE_SCRIPT)
        if not core.exists():
            messagebox.showerror(self.S["title"], self.S["err_core_missing"])
            return False
        if not self.alltxt_path.get():
            messagebox.showerror(self.S["title"], self.S["err_need_alltxt"])
            return False
        call = self.my_call.get().strip().upper()
        if not call:
            messagebox.showerror(self.S["title"], self.S["err_need_call"])
            return False
        if not looks_like_callsign(call):
            messagebox.showerror(self.S["title"], self.S["err_bad_call"])
            return False

        outp = self.out_adif_path.get().strip()
        if not outp:
            messagebox.showerror(self.S["title"], self.S["err_need_output"])
            return False
        if Path(outp).exists():
            if not messagebox.askyesno(self.S["title"], self.S["warn_overwrite"]):
                return False

        if not self.review_on.get():
            if not messagebox.askyesno(self.S["title"], self.S["warn_no_review"]):
                return False
        return True

    def build_command(self):
        core = str(Path(__file__).with_name(CORE_SCRIPT))
        alltxt = self.alltxt_path.get()
        call = self.my_call.get().strip().upper()
        out_adif = self.out_adif_path.get().strip()
        out_dir = str(Path(out_adif).parent)

        cmd = [sys.executable, core, alltxt, "-o", out_adif]
        cmd += ["--station-call", call]
        cmd += ["--mode", self.mode.get()]

        w = self.window_sec.get().strip()
        if w:
            cmd += ["--window-sec", w]

        mw = self.merge_window.get().strip()
        if mw:
            cmd += ["--merge-window", mw]

        if self.review_on.get():
            stamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
            review_path = str(Path(out_dir) / f"review_{stamp}.csv")
            cmd += ["--review-csv", review_path]
            cmd += ["--review-level", self.review_level.get()]

        if self.no_confidence.get():
            cmd += ["--no-confidence"]

        return cmd, out_dir

    def _set_running(self, running: bool):
        if running:
            self.btn_start.config(state="disabled")
            self.btn_cancel.config(state="normal")
            self.prog.start(15)
            self.status.set(self.S["status_running"])
        else:
            self.btn_start.config(state="normal")
            self.btn_cancel.config(state="disabled")
            self.prog.stop()

    def start(self):
        if not self.validate():
            return

        cmd, out_dir = self.build_command()

        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")

        self.log("[GUI] Command:")
        self.log(" ".join(cmd))
        self.log("")

        self._set_running(True)

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(Path(__file__).parent),
            )
        except Exception as e:
            self._set_running(False)
            self.status.set(self.S["status_failed"])
            messagebox.showerror(self.S["title"], str(e))
            return

        self.after(100, lambda: self._poll_process(out_dir))

    def cancel(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.log("[GUI] Cancel requested.")
            except Exception:
                pass

    def _poll_process(self, out_dir: str):
        if not self.proc:
            self._set_running(False)
            return

        try:
            while True:
                line = self.proc.stdout.readline()
                if not line:
                    break
                self.log(line.rstrip("\n"))
        except Exception:
            pass

        code = self.proc.poll()
        if code is None:
            self.after(150, lambda: self._poll_process(out_dir))
            return

        self._set_running(False)
        if code == 0:
            self.status.set(self.S["status_done"])
            if messagebox.askyesno(self.S["title"], self.S["done_msg"]):
                open_folder(out_dir)
        else:
            self.status.set(self.S["status_failed"])
            messagebox.showerror(self.S["title"], f"{self.S['status_failed']} (code={code})")

if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = App()
    app.mainloop()