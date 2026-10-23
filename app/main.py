"""Study Notes JP - デスクトップの画面（tkinter）。"""
import os, queue, subprocess, threading, traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from . import config, llm
from .pipeline import process, AUDIO_VIDEO, IMAGES
from .watcher import Watcher

APP = "Study Notes JP"
FONT = "Meiryo UI"
BG, PANEL, FG, MUTED, ACCENT = "#0F1B2D", "#1B2E45", "#E6EDF5", "#9AA8B8", "#6FB1FF"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP)
        self.geometry("920x660")
        self.configure(bg=BG)
        self.cfg = config.load()
        self.logq = queue.Queue()
        self.jobs = queue.Queue()
        self._style()
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_make = ttk.Frame(nb); nb.add(self.tab_make, text="  作成  ")
        self.tab_watch = ttk.Frame(nb); nb.add(self.tab_watch, text="  監視フォルダ  ")
        self.tab_set = ttk.Frame(nb); nb.add(self.tab_set, text="  設定  ")
        self._make_tab(); self._watch_tab(); self._settings_tab()
        self.watcher = Watcher(lambda: self.cfg, self.submit, self.log)
        threading.Thread(target=self._worker, daemon=True).start()
        self.after(200, self._drain_log)
        if self.cfg.get("watch_on_start") and self.cfg.get("watch"):
            self.watcher.start(); self._watch_state()
        if not self.cfg.get("setup_done"):
            nb.select(self.tab_set)
            self.log("まず「設定」タブで、使う AI と保存先のフォルダを選んでください。")

    # ------------------------------------------------------------ 見た目
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, font=(FONT, 10))
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(12, 6))
        s.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", BG)])
        s.configure("TButton", background=PANEL, foreground=FG, padding=(10, 6), borderwidth=0)
        s.map("TButton", background=[("active", "#2B5BA8")])
        s.configure("Accent.TButton", background=ACCENT, foreground=BG)
        s.configure("TEntry", foreground=FG, insertcolor=FG)
        s.configure("TCombobox", foreground=FG, fieldbackground=PANEL, background=PANEL)
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=26)
        s.configure("Treeview.Heading", background=BG, foreground=MUTED)
        s.configure("Muted.TLabel", foreground=MUTED)
        s.configure("TCheckbutton", background=BG, foreground=FG)
        s.configure("TRadiobutton", background=BG, foreground=FG)

    # ------------------------------------------------------------ 作成タブ
    def _make_tab(self):
        f = self.tab_make
        ttk.Label(f, text="録画、文字起こし、または授業資料のスクリーンショットから、学習ノート（日本語）と英語のプレゼンを作ります。",
                  style="Muted.TLabel").pack(anchor="w", padx=12, pady=(12, 6))
        row = ttk.Frame(f); row.pack(fill="x", padx=12)
        ttk.Label(row, text="科目").pack(side="left")
        self.subject = ttk.Combobox(row, width=30, values=self._subjects())
        self.subject.pack(side="left", padx=8)
        row2 = ttk.Frame(f); row2.pack(fill="x", padx=12, pady=10)
        ttk.Button(row2, text="録画・文字起こしを選ぶ", style="Accent.TButton",
                   command=self.pick_recording).pack(side="left")
        ttk.Button(row2, text="スクリーンショットを選ぶ", style="Accent.TButton",
                   command=self.pick_screens).pack(side="left", padx=8)
        ttk.Button(row2, text="保存先のフォルダを開く", command=lambda: self._open(self.cfg["output_dir"])).pack(side="right")
        self.logbox = tk.Text(f, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", wrap="word", font=(FONT, 9))
        self.logbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _subjects(self):
        return sorted({w.get("subject", "") for w in self.cfg.get("watch", []) if w.get("subject")})

    def pick_recording(self):
        exts = " ".join("*" + e for e in sorted(AUDIO_VIDEO | {".txt"}))
        p = filedialog.askopenfilename(title="録画・文字起こしを選ぶ",
                                       filetypes=[("録画・音声・テキスト", exts)])
        if p:
            self.submit("recording", [p], self.subject.get().strip())

    def pick_screens(self):
        exts = " ".join("*" + e for e in sorted(IMAGES))
        ps = filedialog.askopenfilenames(title="スクリーンショットを選ぶ（複数選べます）", filetypes=[("画像", exts)])
        if ps:
            self.submit("screenshots", list(ps), self.subject.get().strip())

    # ------------------------------------------------------------ 作業の順番待ち
    def submit(self, kind, paths, subject, done=None):
        self.jobs.put((kind, paths, subject, done))
        more = f" ほか {len(paths) - 1} 件" if len(paths) > 1 else ""
        self.log(f"順番待ちに追加: {os.path.basename(paths[0])}{more}")

    def _worker(self):
        while True:
            kind, paths, subject, done = self.jobs.get()
            ok = False
            try:
                for s in process(kind, paths, subject, self.cfg, self.log):
                    self.log("  保存: " + s)
                ok = True
            except Exception as e:
                self.log(f"失敗しました: {e}")
                os.makedirs(config.DIR, exist_ok=True)
                with open(os.path.join(config.DIR, "error.log"), "a", encoding="utf-8") as fh:
                    fh.write(traceback.format_exc() + "\n")
            if done:
                done(ok)

    def log(self, msg):
        self.logq.put(msg)

    def _drain_log(self):
        while not self.logq.empty():
            self.logbox.insert("end", self.logq.get() + "\n"); self.logbox.see("end")
        self.after(200, self._drain_log)

    # ------------------------------------------------------------ 監視フォルダのタブ
    def _watch_tab(self):
        f = self.tab_watch
        ttk.Label(f, text="これらのフォルダに新しい録画やスクリーンショットが入ると、自動でノートとプレゼンを作ります。"
                          "スクリーンショットは、最後の1枚が入ってから数分後にまとめて処理します。",
                  style="Muted.TLabel", wraplength=820).pack(anchor="w", padx=12, pady=(12, 6))
        self.tree = ttk.Treeview(f, columns=("kind", "subject", "path"), show="headings", height=10)
        for c, t, w in (("kind", "種類", 120), ("subject", "科目", 160), ("path", "フォルダ", 560)):
            self.tree.heading(c, text=t); self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=12)
        row = ttk.Frame(f); row.pack(fill="x", padx=12, pady=10)
        ttk.Button(row, text="録画のフォルダを追加", command=lambda: self.add_watch("recording")).pack(side="left")
        ttk.Button(row, text="スクリーンショットのフォルダを追加",
                   command=lambda: self.add_watch("screenshots")).pack(side="left", padx=8)
        ttk.Button(row, text="削除", command=self.remove_watch).pack(side="left")
        self.watch_btn = ttk.Button(row, text="監視を始める", style="Accent.TButton", command=self.toggle_watch)
        self.watch_btn.pack(side="right")
        self.watch_on_start = tk.BooleanVar(value=self.cfg.get("watch_on_start", True))
        ttk.Checkbutton(f, text="アプリを開いたら監視を始める", variable=self.watch_on_start,
                        command=self._save_watch_flag).pack(anchor="w", padx=12, pady=(0, 12))
        self._fill_tree()

    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        for w in self.cfg["watch"]:
            kind = "スクリーンショット" if w["kind"] == "screenshots" else "録画"
            self.tree.insert("", "end", values=(kind, w.get("subject", ""), w["path"]))
        self.subject.configure(values=self._subjects())

    def add_watch(self, kind):
        p = filedialog.askdirectory(title="監視するフォルダ")
        if not p:
            return
        subject = SubjectDialog(self, os.path.basename(p)).result
        if subject is None:
            return
        self.cfg["watch"].append({"path": os.path.normpath(p), "subject": subject, "kind": kind})
        config.save(self.cfg); self._fill_tree()

    def remove_watch(self):
        sel = self.tree.selection()
        if not sel:
            return
        del self.cfg["watch"][self.tree.index(sel[0])]
        config.save(self.cfg); self._fill_tree()

    def toggle_watch(self):
        if self.watcher.running:
            self.watcher.stop()
        else:
            if not self.cfg["watch"]:
                messagebox.showinfo(APP, "先に監視するフォルダを追加してください。"); return
            self.watcher.start()
        self._watch_state()

    def _watch_state(self):
        self.watch_btn.configure(text="監視を止める" if self.watcher.running else "監視を始める")

    def _save_watch_flag(self):
        self.cfg["watch_on_start"] = self.watch_on_start.get(); config.save(self.cfg)

    # ------------------------------------------------------------ 設定タブ
    def _settings_tab(self):
        f = self.tab_set
        g = ttk.Frame(f); g.pack(fill="x", padx=12, pady=12)
        ttk.Label(g, text="AI").grid(row=0, column=0, sticky="nw", pady=4)
        self.provider = tk.StringVar(value=self.cfg["provider"])
        pf = ttk.Frame(g); pf.grid(row=0, column=1, sticky="w")
        for key, (label, _, _) in llm.PROVIDERS.items():
            ttk.Radiobutton(pf, text=label, value=key, variable=self.provider,
                            command=self._provider_changed).pack(anchor="w")
        self.model = tk.StringVar(); self.key = tk.StringVar(); self.host = tk.StringVar(value=self.cfg["ollama_host"])
        rows = [("モデル", ttk.Combobox(g, textvariable=self.model, width=40)),
                ("API キー", ttk.Entry(g, textvariable=self.key, show="•", width=50)),
                ("Ollama のアドレス", ttk.Entry(g, textvariable=self.host, width=40))]
        for i, (t, w) in enumerate(rows, 1):
            ttk.Label(g, text=t).grid(row=i, column=0, sticky="w", pady=4)
            w.grid(row=i, column=1, sticky="w", pady=4)
        self.model_box = rows[0][1]
        self.out_dir = tk.StringVar(value=self.cfg["output_dir"])
        self.deck_dir = tk.StringVar(value=self.cfg["deck_dir"])
        for i, (t, var) in enumerate((("ノートの保存先", self.out_dir),
                                      ("プレゼンの保存先\n（空ならノートと同じ）", self.deck_dir)), 4):
            ttk.Label(g, text=t).grid(row=i, column=0, sticky="w", pady=4)
            r = ttk.Frame(g); r.grid(row=i, column=1, sticky="w")
            ttk.Entry(r, textvariable=var, width=60).pack(side="left")
            ttk.Button(r, text="参照", command=lambda v=var: v.set(filedialog.askdirectory() or v.get())).pack(side="left", padx=4)
        ttk.Label(g, text="文字起こしの精度").grid(row=6, column=0, sticky="w", pady=4)
        self.wsize = ttk.Combobox(g, values=["base", "small", "medium", "large-v3"], width=12, state="readonly")
        self.wsize.set(self.cfg["whisper_size"]); self.wsize.grid(row=6, column=1, sticky="w")
        ttk.Label(g, text="作るもの").grid(row=7, column=0, sticky="nw", pady=4)
        of = ttk.Frame(g); of.grid(row=7, column=1, sticky="w")
        self.outs = {}
        for k, t in (("notes", "4分割の学習ノート（日本語）"), ("deck", "読み上げ原稿つきのプレゼン（英語）"),
                     ("pdf", "PDF も作る（PowerPoint が必要）")):
            self.outs[k] = tk.BooleanVar(value=self.cfg["outputs"].get(k, True))
            ttk.Checkbutton(of, text=t, variable=self.outs[k]).pack(anchor="w")
        ttk.Button(f, text="保存", style="Accent.TButton", command=self.save_settings).pack(anchor="e", padx=12)
        self.key_help = ttk.Label(f, style="Muted.TLabel", wraplength=820)
        self.key_help.pack(anchor="w", padx=12, pady=8)
        self._provider_changed()

    HELP = {
        "gemini": "API キーは https://aistudio.google.com/apikey で無料で取得できます（無料枠では、送った内容が Google の製品改善に使われることがあります）。",
        "claude": "API キーは https://console.anthropic.com で取得できます（使った分だけ課金）。",
        "openai": "API キーは https://platform.openai.com/api-keys で取得できます（使った分だけ課金）。",
        "ollama": "https://ollama.com からインストールし、画像を読めるモデルを追加します（例: ollama pull gemma3:12b）。API キーは不要で、データはこの PC の外に出ません。",
    }

    def _provider_changed(self):
        p = self.provider.get()
        self.model.set(self.cfg["models"].get(p) or llm.PROVIDERS[p][1])
        self.key.set(self.cfg["api_keys"].get(p, ""))
        self.model_box.configure(values=llm.ollama_models(self.host.get()) if p == "ollama" else llm.MODEL_CHOICES.get(p, [llm.PROVIDERS[p][1]]))
        self.key_help.configure(text=self.HELP[p])

    def save_settings(self):
        p = self.provider.get()
        self.cfg["provider"] = p
        self.cfg["models"][p] = self.model.get().strip()
        if self.key.get().strip():
            self.cfg["api_keys"][p] = self.key.get().strip()
        self.cfg["ollama_host"] = self.host.get().strip()
        self.cfg["output_dir"] = self.out_dir.get().strip()
        self.cfg["deck_dir"] = self.deck_dir.get().strip()
        self.cfg["whisper_size"] = self.wsize.get()
        self.cfg["outputs"] = {k: v.get() for k, v in self.outs.items()}
        self.cfg["setup_done"] = True
        config.save(self.cfg)
        messagebox.showinfo(APP, "保存しました。")

    @staticmethod
    def _open(path):
        os.makedirs(path, exist_ok=True)
        subprocess.Popen(["explorer", path])


class SubjectDialog(tk.Toplevel):
    def __init__(self, parent, default):
        super().__init__(parent)
        self.title("科目"); self.configure(bg=BG); self.result = None
        ttk.Label(self, text="このフォルダの科目（保存先のフォルダ名に使います）").pack(padx=16, pady=(16, 6))
        self.var = tk.StringVar(value=default)
        e = ttk.Entry(self, textvariable=self.var, width=40); e.pack(padx=16); e.focus_set()
        ttk.Button(self, text="OK", style="Accent.TButton", command=self._ok).pack(pady=12)
        self.bind("<Return>", lambda _: self._ok())
        self.transient(parent); self.grab_set(); self.wait_window()

    def _ok(self):
        self.result = self.var.get().strip(); self.destroy()


def run():
    App().mainloop()


if __name__ == "__main__":
    run()
