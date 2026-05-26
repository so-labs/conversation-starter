# devtools/ai_dev_assistant.py

import os
import re
import datetime
import difflib
import tkinter as tk
from tkinter import ttk, messagebox
import ctypes

# Windowsで実行時にコンソールウィンドウを非表示にする
if os.name == "nt":
    try:
        hWnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hWnd:
            ctypes.windll.user32.ShowWindow(hWnd, 0)
    except Exception:
        pass

# --- 設定 ---
MAIN_FILE_NAME = "index.html"  # 基準のファイル名
EXCLUDE_DIRS = [
    "node_modules",
    ".git",
    "__pycache__",
    ".vscode",
    ".vercel",
]  # 除外するディレクトリ
EXCLUDE_FILES = [
    ".env.development",
    ".env.production",
    "package-lock.json",
]  # 除外するファイル
INCLUDE_SPECIFIC_FILES = [".gitignore", "ai_dev_assistant.py"]  # 含めるファイル

# パッチ用マーカー（自己言及的なパースエラーを防ぐため、文字を組み立てて定義）
MARK_SEARCH = "<" * 4 + " SEARCH"
MARK_SEP = "=" * 4 + "PATCH_SEPARATOR" + "=" * 4
MARK_REPLACE = ">" * 4 + " REPLACE"

EXTENSION_TO_LANG = {
    ".js": "javascript",
    ".json": "json",
    ".html": "html",
    ".css": "css",
    ".md": "markdown",
}
TARGET_EXTENSIONS = list(EXTENSION_TO_LANG.keys())

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# --- 共通ユーティリティ ---
def normalize_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


# ファイル収集
def collect_files(root_dir, include_excluded_dirs=True):
    all_files = []
    main_script_path = os.path.join(root_dir, MAIN_FILE_NAME)

    for dirpath, dirnames, filenames in os.walk(root_dir):
        if not include_excluded_dirs:
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

        for file in filenames:
            filepath = os.path.join(dirpath, file)
            has_target_ext = any(filepath.endswith(ext) for ext in TARGET_EXTENSIONS)
            is_specific_file = file in INCLUDE_SPECIFIC_FILES

            if has_target_ext or is_specific_file:
                is_export_file = file.startswith("export_") and file.endswith(".md")
                is_excluded_file = file in EXCLUDE_FILES

                if not is_export_file and not is_excluded_file:
                    all_files.append(filepath)

    sorted_files = []
    if main_script_path in all_files:
        sorted_files.append(main_script_path)
        all_files.remove(main_script_path)

    all_files.sort()
    sorted_files.extend(all_files)

    for f in sorted_files:
        yield f


# ディレクトリ構成マップ作成
def generate_file_tree_map(root_dir, collected_files):
    tree_map = []
    tree_map.append("```tree")

    tree_structure = {}
    excluded_set = set(EXCLUDE_DIRS)

    for filepath in collected_files:
        relative_path = os.path.relpath(filepath, root_dir)
        parts = relative_path.split(os.sep)

        # 除外ディレクトリはトップレベルだけ記録して中身は展開しない
        if parts[0] in excluded_set:
            if parts[0] not in tree_structure:
                tree_structure[parts[0]] = {"__excluded__": True}
            continue

        current_level = tree_structure
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                if "__files__" not in current_level:
                    current_level["__files__"] = []
                current_level["__files__"].append(part)
            else:
                # 深さ制限: ルート直下の1階層まで展開
                if i >= 1:
                    if "__collapsed__" not in current_level:
                        current_level["__collapsed__"] = True
                    break
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]

    # ディレクトリツリーを再帰的に取得
    def walk_tree(node, prefix="", depth=0):
        dirs = sorted(
            [
                k
                for k in node.keys()
                if k not in ("__files__", "__excluded__", "__collapsed__")
            ]
        )
        files = sorted(node.get("__files__", []))
        excluded_dirs = sorted(
            [
                k
                for k, v in node.items()
                if isinstance(v, dict) and v.get("__excluded__")
            ]
        )

        all_items = files + dirs + excluded_dirs

        if prefix == "":
            if MAIN_FILE_NAME in files:
                files.remove(MAIN_FILE_NAME)
                files.insert(0, MAIN_FILE_NAME)
            all_items = files + dirs + excluded_dirs

        for i, item in enumerate(all_items):
            is_last_item = i == len(all_items) - 1
            indent_prefix = prefix + (" " if is_last_item else "│ ")

            if item in excluded_dirs:
                # 除外ディレクトリは件数だけ表示
                excluded_path = os.path.join(root_dir, item)
                try:
                    count = sum(1 for _ in os.scandir(excluded_path))
                    tree_map.append(
                        f"{prefix}{'└── ' if is_last_item else '├── '}{item}/ … (ignored, {count} items)"
                    )
                except:
                    tree_map.append(
                        f"{prefix}{'└── ' if is_last_item else '├── '}{item}/ … (ignored)"
                    )
                continue

            tree_map.append(f"{prefix}{'└── ' if is_last_item else '├── '}{item}")

            if item in dirs:
                child = node[item]
                if depth < 1:
                    walk_tree(child, indent_prefix, depth + 1)
                elif child.get("__collapsed__") or child.get("__files__"):
                    tree_map.append(f"{indent_prefix}└── …")

    walk_tree(tree_structure)
    tree_map.append("```")
    return "\n".join(tree_map)


# --- GUI コンポーネント ---
class ToolTip:
    """
    ボタンなどにマウスカーソルを乗せると、ツールチップを表示する。
    """

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.enter)
        widget.bind("<Leave>", self.leave)

    # マウスカーソルが乗ったときの処理
    def enter(self, event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("", "9", "normal"),
            padx=5,
            pady=2,
        )
        label.pack()

    # マウスカーソルが離れたときの処理
    def leave(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# --- メインアプリケーション ---
class DevAssistantApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI Dev Assistant (Export & Patch)")
        self.geometry("1000x600")

        if os.name == "nt":
            style = ttk.Style()
            try:
                style.theme_use("vista")
            except tk.TclError:
                pass

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_export = ttk.Frame(self.notebook)
        self.tab_patch = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_export, text="エクスポート (Export)")
        self.notebook.add(self.tab_patch, text="パッチ適用 (Apply Patch)")

        self.setup_export_tab()
        self.setup_patch_tab()

    # ====== Export Tab ======
    def setup_export_tab(self):
        ctrl_frame = ttk.Frame(self.tab_export)
        ctrl_frame.pack(fill="x", pady=5)

        ttk.Button(ctrl_frame, text="全選択", command=self.select_all_export).pack(
            side="left", padx=5
        )
        ttk.Button(ctrl_frame, text="全解除", command=self.deselect_all_export).pack(
            side="left", padx=5
        )
        ttk.Button(ctrl_frame, text="再読み込み", command=self.load_project_files).pack(
            side="left", padx=5
        )
        ttk.Button(ctrl_frame, text="ファイルへ保存", command=self.export_to_file).pack(
            side="right", padx=5
        )
        ttk.Button(
            ctrl_frame, text="クリップボードへコピー", command=self.export_to_clipboard
        ).pack(side="right", padx=5)

        ttk.Label(
            self.tab_export, text="AIに読み込ませるファイルを選択してください。"
        ).pack(anchor="w", padx=5)

        self.export_scroll_frame = ScrollableFrame(self.tab_export)
        self.export_scroll_frame.pack(fill="both", expand=True, pady=5)

        self.export_vars = {}
        self.load_project_files()

    # プロジェクトファイル読み込み
    def load_project_files(self):
        for widget in self.export_scroll_frame.scrollable_frame.winfo_children():
            widget.destroy()

        self.export_scroll_frame.canvas.yview_moveto(0)
        self.export_vars.clear()
        self.dir_vars = {}

        all_project_files = list(
            collect_files(PROJECT_ROOT, include_excluded_dirs=False)
        )

        # ディレクトリ構造の解析
        dir_to_immediate_files = {}
        all_dirs = set()
        all_dirs.add("")  # Root用

        for f in all_project_files:
            rel_path = os.path.relpath(f, PROJECT_ROOT).replace("\\", "/")
            d = os.path.dirname(rel_path)
            if d not in dir_to_immediate_files:
                dir_to_immediate_files[d] = []
            dir_to_immediate_files[d].append(f)

            # 中間ディレクトリをすべてセットに追加
            parts = d.split("/")
            for i in range(len(parts)):
                parent_dir = "/".join(parts[: i + 1])
                if parent_dir:
                    all_dirs.add(parent_dir)

        # ディレクトリをソートして描画
        for dir_path in sorted(list(all_dirs)):
            # 階層に応じたインデント計算
            depth = 0 if not dir_path else dir_path.count("/") + 1
            indent_folder = 5 + (depth * 20)
            indent_file = 25 + (depth * 20)

            display_name = (
                "📁 (Root)" if not dir_path else f"📁 {os.path.basename(dir_path)}"
            )

            dir_var = tk.BooleanVar(value=True)
            self.dir_vars[dir_path] = dir_var

            def make_toggle_dir(path, var):
                def _toggle():
                    state = var.get()
                    prefix = (path + "/") if path else ""
                    # 配下の全ファイルをトグル
                    for f_path, f_var in self.export_vars.items():
                        f_rel = os.path.relpath(f_path, PROJECT_ROOT).replace("\\", "/")
                        if not path or f_rel.startswith(prefix):
                            f_var.set(state)

                    # 配下の全サブディレクトリもトグル
                    for d_path, d_var in self.dir_vars.items():
                        if d_path == path:
                            continue
                        if not path or d_path.startswith(prefix):
                            d_var.set(state)

                return _toggle

            dir_cb = ttk.Checkbutton(
                self.export_scroll_frame.scrollable_frame,
                text=display_name,
                variable=dir_var,
                command=make_toggle_dir(dir_path, dir_var),
            )
            dir_cb.pack(anchor="w", padx=indent_folder, pady=(5, 2))

            # このディレクトリ直下のファイルを表示
            if dir_path in dir_to_immediate_files:
                for f in dir_to_immediate_files[dir_path]:
                    rel_path = os.path.relpath(f, PROJECT_ROOT).replace("\\", "/")
                    filename = os.path.basename(rel_path)
                    var = tk.BooleanVar(value=True)
                    self.export_vars[f] = var

                    cb = ttk.Checkbutton(
                        self.export_scroll_frame.scrollable_frame,
                        text=filename,
                        variable=var,
                    )
                    cb.pack(anchor="w", padx=indent_file, pady=1)

    # 全選択
    def select_all_export(self):
        for var in self.export_vars.values():
            var.set(True)
        if hasattr(self, "dir_vars"):
            for var in self.dir_vars.values():
                var.set(True)

    # 選択解除
    def deselect_all_export(self):
        for var in self.export_vars.values():
            var.set(False)
        if hasattr(self, "dir_vars"):
            for var in self.dir_vars.values():
                var.set(False)

    # エクスポート用マークダウン生成
    def get_export_markdown(self):
        project_name = os.path.basename(PROJECT_ROOT)
        all_files_for_tree = list(
            collect_files(PROJECT_ROOT, include_excluded_dirs=True)
        )

        # 選択されたファイルのみ抽出、順序は維持
        all_content_files_ordered = list(
            collect_files(PROJECT_ROOT, include_excluded_dirs=False)
        )
        files_for_content = [
            f
            for f in all_content_files_ordered
            if self.export_vars.get(f) and self.export_vars[f].get()
        ]

        # 自己言及による解析ミスを防ぐため、キーワードを分割して組み立てる
        f_header = "### " + "File: "
        op_edit = "[" + "EDIT" + "]"
        op_add = "[" + "ADD" + "]"
        op_move = "[" + "MOVE" + "]"
        op_delete = "[" + "DELETE" + "]"

        output = []
        ai_instructions = f"""---
# 🤖 AI Assistant Instructions
- When proposing or modifying code, **NEVER output the entire file**.
- Output ONLY the changes using the "**Search & Replace**" format.
- **IMPORTANT**: The `{MARK_SEARCH}` block MUST include **at least 3-5 lines of unchanged context before and after the modified code** so that the exact location can be uniquely identified.
- **NEVER delete or modify existing comments**.
- **CRITICAL**: You MUST wrap ALL file operations, INCLUDING the `{f_header}` lines, inside a SINGLE Markdown code block (` ``````searchandreplace `).

# File Operation Instructions
You MUST specify the operation type ({op_edit}, {op_add}, {op_move}, {op_delete}) in the `{f_header}` header.
**The `{f_header}` MUST be INSIDE the code block, NOT outside.**

``````searchandreplace
{f_header}{op_edit} path/to/existing_file.ext
{MARK_SEARCH}
A few lines before the change (unchanged context)
The old code to be deleted or modified
A few lines after the change (unchanged context)
{MARK_SEP}
A few lines before the change (unchanged context)
The newly added or modified code
A few lines after the change (unchanged context)
{MARK_REPLACE}

{f_header}{op_edit} path/to/another_file.ext
{MARK_SEARCH}
...
{MARK_REPLACE}

{f_header}{op_add} path/to/new_file.ext
{MARK_SEARCH}
{MARK_SEP}
Content of the new file
{MARK_REPLACE}

{f_header}{op_move} old_path.ext -> new_path.ext
(Use this for both moving files to different directories and **renaming files**)
(If you need to edit the file as well, create a separate {op_edit} block for `new_path.ext`)

{f_header}{op_delete} path/to/file.ext
``````

# ❌ Common Mistakes (NEVER do these)
- **Putting the `{f_header}` outside the ` ``````searchandreplace ` code block.** (The header MUST be inside so the user can copy it together).
- **Creating multiple code blocks.** (Put ALL files and ALL changes into ONE SINGLE ` ``````searchandreplace ` code block).
- Forgetting the `{MARK_SEP}` delimiter and writing the old and new code consecutively.
- Including the "new modified code" inside the `{MARK_SEARCH}` block.
- Omitting the context (unchanged lines before and after).
- Grouping multiple changes into a single `{MARK_SEARCH}` block. (If you need to change multiple locations, create multiple `{MARK_SEARCH}` `{MARK_SEP}` `{MARK_REPLACE}` blocks even within the same file.)
- Changing code without specifying the `[EDIT]` tag in the file header.
- Modifying `{MARK_SEARCH}`, `{MARK_SEP}`, or `{MARK_REPLACE}` delimiters (do not use shorter versions like `<<<<` alone).
---

"""
        output.append(ai_instructions)
        output.append(f"# ❖ Project: {project_name}\n\n")

        file_tree_map_content = generate_file_tree_map(PROJECT_ROOT, all_files_for_tree)
        output.append("--- **Project Structure** ---\n\n")
        output.append("## ファイル構成\n\n")
        output.append(file_tree_map_content)
        output.append("\n\n")

        output.append("--- **File Contents** ---\n\n")
        output.append("## ファイル内容\n\n")

        for filepath in files_for_content:
            relative_path = os.path.relpath(filepath, PROJECT_ROOT).replace("\\", "/")
            _, ext = os.path.splitext(filepath)
            lang = EXTENSION_TO_LANG.get(ext, "")

            try:
                with open(filepath, "r", encoding="utf-8-sig") as f:
                    content = f.read().rstrip()

                ticks_matches = re.findall(r"^[ \t]{0,3}(`+)", content, re.MULTILINE)
                max_ticks = max([len(m) for m in ticks_matches]) if ticks_matches else 0
                fence_count = max(3, max_ticks + 1)
                code_fence = "`" * fence_count

                output.append("---\n\n")
                output.append(f"### File: {relative_path}\n\n")
                output.append(f"{code_fence}{lang}\n")
                output.append(content)
                output.append(f"\n{code_fence}\n\n")

            except Exception as e:
                output.append(f"### File: {relative_path}\n\n")
                output.append(f"--- ファイルの読み込みエラー: {e} ---\n\n")

        return "".join(output)

    # クリップボードへコピー
    def export_to_clipboard(self):
        text = self.get_export_markdown()
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Export", "クリップボードにコピーしました。")

    # ファイルへ保存
    def export_to_file(self):
        text = self.get_export_markdown()
        project_name = os.path.basename(PROJECT_ROOT)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"export_{project_name}_{timestamp}.md"
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo("Export", f"ファイルに保存しました:\n{out_path}")
        except Exception as e:
            messagebox.showerror("エラー", f"ファイルの保存に失敗しました:\n{e}")

    # ====== Patch Tab ======
    def setup_patch_tab(self):
        paned_main = ttk.PanedWindow(self.tab_patch, orient=tk.VERTICAL)
        paned_main.pack(fill="both", expand=True, pady=5)

        # パッチ入力エリア
        top_frame = ttk.Frame(paned_main)
        paned_main.add(top_frame, weight=1)

        lbl_frame = ttk.Frame(top_frame)
        lbl_frame.pack(fill="x")
        ttk.Label(
            lbl_frame, text="AIが出力した Search & Replace の内容を貼り付けてください："
        ).pack(side="left")
        ttk.Button(lbl_frame, text="リセット", command=self.clear_patch_tab).pack(
            side="right", padx=5
        )
        ttk.Button(lbl_frame, text="パッチを解析", command=self.parse_patch).pack(
            side="right", padx=5
        )
        ttk.Button(
            lbl_frame, text="クリップボードからPaste", command=self.paste_patch
        ).pack(side="right")

        self.patch_text_input = tk.Text(top_frame, height=10)
        self.patch_text_input.pack(fill="both", expand=True, pady=5)

        # 解析結果エリア
        bottom_frame = ttk.Frame(paned_main)
        paned_main.add(bottom_frame, weight=3)

        paned_bottom = ttk.PanedWindow(bottom_frame, orient=tk.HORIZONTAL)
        paned_bottom.pack(fill="both", expand=True)

        # 左側: パッチリスト
        left_frame = ttk.Frame(paned_bottom)
        paned_bottom.add(left_frame, weight=1)

        ttk.Label(
            left_frame, text="適用するパッチ: (項目クリックでプレビュー表示)"
        ).pack(anchor="w")
        self.patch_list_frame = ScrollableFrame(left_frame)
        self.patch_list_frame.pack(fill="both", expand=True)

        apply_btn_frame = ttk.Frame(left_frame)
        apply_btn_frame.pack(fill="x", pady=5)
        ttk.Button(
            apply_btn_frame,
            text="✔ 選択したパッチを適用",
            command=self.apply_selected_patches,
        ).pack(fill="x", pady=(0, 5))
        ttk.Button(
            apply_btn_frame,
            text="📋 エラーのパッチをコピー",
            command=self.copy_error_patches,
        ).pack(fill="x")

        # 右側: 差分表示
        right_frame = ttk.Frame(paned_bottom)
        paned_bottom.add(right_frame, weight=2)
        ttk.Label(right_frame, text="差分プレビュー:").pack(anchor="w")

        self.diff_text = tk.Text(right_frame, state="disabled", background="#f5f5f5")
        self.diff_text.pack(fill="both", expand=True)

        self.diff_text.tag_config("add", foreground="#008000")
        self.diff_text.tag_config("remove", foreground="#d00000")
        self.diff_text.tag_config("info", foreground="#0000a0")

        self.parsed_patches = []

    # クリップボードからPaste
    def paste_patch(self):
        try:
            text = self.clipboard_get()
            self.patch_text_input.delete("1.0", "end")
            self.patch_text_input.insert("1.0", text)
        except tk.TclError:
            messagebox.showwarning("警告", "クリップボードにテキストがありません。")

    # パッチタブをクリア
    def clear_patch_tab(self):
        self.patch_text_input.delete("1.0", "end")
        self.parsed_patches = []
        self.evaluate_patches()

    # パッチ解析
    def parse_patch(self):
        text = self.patch_text_input.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showwarning("警告", "パッチテキストが入力されていません。")
            return

        text = normalize_newlines(text)
        # 正規表現自体が自分自身にマッチしないように分割して定義
        file_pattern = r"##" + r"#\s*File:\s*\[(ADD|DELETE|MOVE|EDIT)\]\s*([^\n]+)"

        lines = text.split("\n")
        i = 0
        current_file = None
        current_op = "EDIT"
        current_old_file = None

        self.parsed_patches = []

        while i < len(lines):
            line = lines[i]
            file_match = re.search(file_pattern, line, re.IGNORECASE)
            if file_match:
                op_str = file_match.group(1).upper()
                file_info = file_match.group(2).strip().strip("`").strip()
                current_op = op_str

                if current_op == "MOVE":
                    if "->" in file_info:
                        old_f, new_f = file_info.split("->", 1)
                        current_file = new_f.strip()
                        current_old_file = old_f.strip()
                    else:
                        current_file = file_info
                        current_old_file = None
                else:
                    current_file = file_info
                    current_old_file = None

                if current_op == "DELETE":
                    self.parsed_patches.append(
                        {
                            "file": current_file,
                            "op": "DELETE",
                            "search": "",
                            "replace": "",
                            "format_error": False,
                        }
                    )
                    i += 1
                    continue
                elif current_op == "MOVE":
                    self.parsed_patches.append(
                        {
                            "file": current_file,
                            "old_file": current_old_file,
                            "op": "MOVE",
                            "search": "",
                            "replace": "",
                            "format_error": False,
                        }
                    )
                    i += 1
                    continue
                elif current_op in ("ADD", "EDIT"):
                    i += 1
                    continue

            if line.startswith(MARK_SEARCH):
                if not current_file:
                    i += 1
                    continue

                start_i = i + 1
                end_i = start_i

                # 次の File: または MARK_SEARCH までを一つのブロックとする
                while end_i < len(lines):
                    if re.search(file_pattern, lines[end_i], re.IGNORECASE) or lines[
                        end_i
                    ].startswith(MARK_SEARCH):
                        break
                    end_i += 1

                # ブロック内で最後の MARK_REPLACE を探す
                replace_end_idx = -1
                for j in range(end_i - 1, start_i - 1, -1):
                    if lines[j].startswith(MARK_REPLACE):
                        replace_end_idx = j
                        break

                if replace_end_idx == -1:
                    replace_end_idx = end_i

                # MARK_SEP を探す
                sep_idx = -1
                for j in range(start_i, replace_end_idx):
                    if lines[j].startswith(MARK_SEP):
                        sep_idx = j
                        break

                has_separator = sep_idx != -1

                if has_separator:
                    search_lines = lines[start_i:sep_idx]
                    replace_lines = lines[sep_idx + 1 : replace_end_idx]
                else:
                    search_lines = lines[start_i:replace_end_idx]
                    replace_lines = []
                    # ADDでセパレータがない場合の救済
                    if current_op == "ADD":
                        replace_lines = search_lines
                        search_lines = []
                        has_separator = True

                search_text = "\n".join(search_lines)
                replace_text = "\n".join(replace_lines)

                op_to_register = current_op if current_op in ("ADD", "EDIT") else "EDIT"

                self.parsed_patches.append(
                    {
                        "file": current_file,
                        "op": op_to_register,
                        "search": search_text,
                        "replace": replace_text,
                        "format_error": not has_separator,
                    }
                )

                if current_op == "ADD":
                    current_op = "EDIT"

                i = end_i
                continue
            i += 1

        self.evaluate_patches()

    # パッチターゲット検索
    def find_patch_target(self, search_text, content):
        # 1. 完全一致
        if search_text in content:
            return search_text, "Exact match"

        # 2. 改行strip一致
        s_strip = search_text.strip("\n")
        if s_strip and s_strip in content:
            return s_strip, "Exact match (newline adjusted)"

        # 3. 曖昧検索 (インデント・空白無視)
        search_lines = search_text.strip("\n").split("\n")
        content_lines = content.split("\n")

        if not search_lines:
            return None, "Search text is empty"

        search_stripped = [line.strip() for line in search_lines]

        # 3-1. インデント無視
        for i in range(len(content_lines) - len(search_lines) + 1):
            match = True
            for j in range(len(search_lines)):
                if content_lines[i + j].strip() != search_stripped[j]:
                    match = False
                    break
            if match:
                matched_content = "\n".join(content_lines[i : i + len(search_lines)])
                return (
                    matched_content,
                    f"Fuzzy match (ignoring indentation: lines {i+1} - {i+len(search_lines)})",
                )

        # 3-2. 行内の空白をすべて無視 (Gemini等の表記揺れを吸収)
        search_no_spaces = [
            line.replace(" ", "").replace("\t", "") for line in search_stripped
        ]
        for i in range(len(content_lines) - len(search_lines) + 1):
            match = True
            for j in range(len(search_lines)):
                if (
                    content_lines[i + j].replace(" ", "").replace("\t", "")
                    != search_no_spaces[j]
                ):
                    match = False
                    break
            if match:
                matched_content = "\n".join(content_lines[i : i + len(search_lines)])
                return (
                    matched_content,
                    f"Fuzzy match (ignoring all spaces: lines {i+1} - {i+len(search_lines)})",
                )

        # 4. 見つからなかった場合、類似箇所を探してエラー報告用に情報を付与
        best_ratio = 0
        best_line_idx = -1

        search_str_for_diff = "\n".join(search_stripped)

        check_lines = len(search_lines)
        if check_lines > 0:
            for i in range(len(content_lines) - check_lines + 1):
                block = "\n".join(
                    [l.strip() for l in content_lines[i : i + check_lines]]
                )

                matcher = difflib.SequenceMatcher(None, search_str_for_diff, block)
                if matcher.quick_ratio() > best_ratio:
                    ratio = matcher.ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_line_idx = i

        if best_ratio > 0.6:
            return (
                None,
                f"Search target not found (Similar location: lines {best_line_idx+1} - {best_line_idx+check_lines}, Match: {best_ratio:.0%})",
            )

        return None, "Search target not found"

    # パッチ判定
    def evaluate_patches(self):
        for widget in self.patch_list_frame.scrollable_frame.winfo_children():
            widget.destroy()

        if not self.parsed_patches:
            label = ttk.Label(
                self.patch_list_frame.scrollable_frame,
                text=f"パッチ形式 ({MARK_SEARCH} {MARK_SEP} {MARK_REPLACE}) またはファイル操作が見つかりませんでした。",
                wraplength=400,
                justify="left",
            )
            label.pack(anchor="w", fill="x", padx=2)

            def _update_wrap(e):
                label.configure(wraplength=max(100, e.width - 10))

            self.patch_list_frame.scrollable_frame.bind("<Configure>", _update_wrap)
            self.diff_text.config(state="normal")
            self.diff_text.delete("1.0", "end")
            self.diff_text.config(state="disabled")
            return

        vfs = {}

        def get_vfs_content(fpath):  # VFS＝仮想ファイルシステム
            if fpath in vfs:
                return vfs[fpath]
            abs_path = os.path.join(PROJECT_ROOT, fpath)
            if os.path.exists(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8-sig") as f:
                        return normalize_newlines(f.read())
                except:
                    return None
            return None

        def set_vfs_content(fpath, content):
            vfs[fpath] = content

        for idx, patch in enumerate(self.parsed_patches):
            filepath = patch["file"]
            patch["var"] = tk.BooleanVar(value=False)
            patch["diff"] = ""
            patch["status"] = "Error"
            patch["msg"] = "Unknown Error"

            op = patch.get("op", "EDIT")

            if patch.get("format_error"):
                patch["status"] = "Format Error"
                patch["msg"] = f"Delimiter ({MARK_SEP}) is missing"
            elif op == "DELETE":
                content = get_vfs_content(filepath)
                if content is not None:
                    patch["status"] = "OK"
                    patch["msg"] = "Ready to delete"
                    patch["var"].set(True)
                    set_vfs_content(filepath, None)  # 削除シミュレート
                else:
                    patch["status"] = "Error"
                    patch["msg"] = "File not found"
            elif op == "MOVE":
                old_filepath = patch.get("old_file", "")
                content = get_vfs_content(old_filepath)
                target_content = get_vfs_content(filepath)

                if content is None:
                    patch["status"] = "Error"
                    patch["msg"] = f"Source file not found: {old_filepath}"
                elif target_content is not None:
                    patch["status"] = "Error"
                    patch["msg"] = f"Destination file already exists: {filepath}"
                else:
                    patch["status"] = "OK"
                    patch["msg"] = f"Ready to move from {old_filepath}"
                    patch["var"].set(True)
                    set_vfs_content(filepath, content)
                    set_vfs_content(old_filepath, None)
            elif op == "ADD":
                target_content = get_vfs_content(filepath)
                if target_content is not None:
                    patch["status"] = "Error"
                    patch["msg"] = f"File already exists: {filepath}"
                else:
                    patch["status"] = "OK"
                    patch["msg"] = "Ready to create"
                    patch["var"].set(True)
                    patch["diff"] = "+ " + patch["replace"].replace("\n", "\n+ ")
                    set_vfs_content(filepath, patch["replace"])
            else:  # EDIT
                content = get_vfs_content(filepath)
                if content is not None:
                    actual_search, msg = self.find_patch_target(
                        patch["search"], content
                    )

                    if actual_search is not None:
                        patch["status"] = "OK"
                        patch["msg"] = msg
                        patch["var"].set(True)
                        patch["actual_search"] = actual_search

                        if "Exact match (newline adjusted)" in msg:
                            patch["replace"] = patch["replace"].strip("\n")

                        self.generate_diff(patch, content)
                        content_after = content.replace(
                            actual_search, patch["replace"], 1
                        )
                        set_vfs_content(filepath, content_after)
                    else:
                        patch["msg"] = msg
                        patch["actual_search"] = patch["search"]
                else:
                    patch["status"] = "Error"
                    patch["msg"] = "File not found"

            item_frame = ttk.Frame(self.patch_list_frame.scrollable_frame)
            item_frame.pack(fill="x", pady=2)

            cb = ttk.Checkbutton(item_frame, variable=patch["var"])
            cb.pack(side="left")

            if op == "DELETE":
                op_prefix = "[DELETE] "
            elif op == "MOVE":
                op_prefix = f"[MOVE] {patch.get('old_file', '')} -> "
            elif op == "ADD":
                op_prefix = "[ADD] "
            else:
                op_prefix = "[EDIT] "

            # ファイル名だけでなく相対パスを表示するように変更
            status_text = f"[{patch['status']}] {op_prefix}{patch['file']}"
            btn = ttk.Button(
                item_frame, text=status_text, command=lambda p=patch: self.show_diff(p)
            )
            btn.pack(side="left", fill="x", expand=True)
            ToolTip(btn, status_text)

            if patch["status"] != "OK":
                cb.configure(state="disabled")

    # 差分生成
    def generate_diff(self, patch, content):
        lines_before = content.splitlines(keepends=True)
        search_target = patch.get("actual_search", patch["search"])
        content_after = content.replace(search_target, patch["replace"], 1)
        lines_after = content_after.splitlines(keepends=True)

        diff = list(
            difflib.unified_diff(
                lines_before,
                lines_after,
                fromfile=patch["file"] + " (Original)",
                tofile=patch["file"] + " (Modified)",
                n=3,
            )
        )
        patch["diff"] = "".join(diff)

    # 差分表示
    def show_diff(self, patch):
        self.diff_text.config(state="normal")
        self.diff_text.delete("1.0", "end")

        op = patch.get("op", "EDIT")

        if not patch["diff"] and op not in ("DELETE", "MOVE"):
            search_target = patch.get("actual_search", patch["search"])
            self.diff_text.insert(
                "end",
                f"No diff or not applicable ({patch['msg']})\n\n--- [Searched text] ---\n{search_target}\n------------------------",
            )
        elif op in ("DELETE", "MOVE") and not patch["diff"]:
            self.diff_text.insert("end", f"{op} operation.\nMessage: {patch['msg']}")
        else:
            diff_lines = patch["diff"].splitlines(keepends=True)
            for line in diff_lines:
                if line.startswith("+") and not line.startswith("+++"):
                    self.diff_text.insert("end", line, "add")
                elif line.startswith("-") and not line.startswith("---"):
                    self.diff_text.insert("end", line, "remove")
                elif line.startswith("@@"):
                    self.diff_text.insert("end", line, "info")
                else:
                    self.diff_text.insert("end", line)

        self.diff_text.config(state="disabled")

    # 選択パッチ適用
    def apply_selected_patches(self):
        to_apply = [
            p for p in self.parsed_patches if p["var"].get() and p["status"] == "OK"
        ]
        if not to_apply:
            messagebox.showinfo("情報", "適用するパッチが選択されていません。")
            return

        # 確認リストを作成
        summary = []
        for p in to_apply:
            op = p.get("op", "EDIT")
            if op == "ADD":
                summary.append(f"[NEW] {p['file']}")
            elif op == "MOVE":
                summary.append(f"[MOVE] {p['old_file']} -> {p['file']}")
            elif op == "DELETE":
                summary.append(f"[DELETE] {p['file']}")
            else:
                summary.append(f"[EDIT] {p['file']}")

        # EDIT 以外の操作（ADD/DELETE/MOVE）がある場合のみ確認ダイアログを表示
        has_file_ops = any(p.get("op", "EDIT") != "EDIT" for p in to_apply)
        result = [not has_file_ops]

        if has_file_ops:
            # 確認ダイアログ
            dlg = tk.Toplevel(self)
            dlg.title("パッチ適用の確認")
            dlg.geometry("500x300")
            dlg.transient(self)
            dlg.grab_set()

            ttk.Label(
                dlg, text="以下のファイル操作を実行しますか？", font=("", 10, "bold")
            ).pack(pady=10)

            list_frame = ttk.Frame(dlg)
            list_frame.pack(fill="both", expand=True, padx=10)

            listbox = tk.Listbox(list_frame)
            listbox.pack(side="left", fill="both", expand=True)
            scrollbar = ttk.Scrollbar(
                list_frame, orient="vertical", command=listbox.yview
            )
            scrollbar.pack(side="right", fill="y")
            listbox.config(yscrollcommand=scrollbar.set)

            for item in summary:
                listbox.insert("end", item)

            btn_frame = ttk.Frame(dlg)
            btn_frame.pack(fill="x", pady=10)

            def on_ok():
                result[0] = True
                dlg.destroy()

            def on_cancel():
                dlg.destroy()

            ttk.Button(btn_frame, text="実行", command=on_ok).pack(
                side="left", expand=True, padx=10
            )
            ttk.Button(btn_frame, text="キャンセル", command=on_cancel).pack(
                side="right", expand=True, padx=10
            )

            self.wait_window(dlg)

        if not result[0]:
            return

        applied_count = 0
        failed_count = 0

        for patch in to_apply:
            filepath = os.path.join(PROJECT_ROOT, patch["file"])
            op = patch.get("op", "EDIT")

            try:
                if op == "DELETE":
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    applied_count += 1
                elif op == "MOVE":
                    old_filepath = os.path.join(PROJECT_ROOT, patch["old_file"])
                    dirname = os.path.dirname(filepath)
                    if dirname:
                        os.makedirs(dirname, exist_ok=True)
                    os.rename(old_filepath, filepath)
                    applied_count += 1
                elif op == "ADD":
                    dirname = os.path.dirname(filepath)
                    if dirname:
                        os.makedirs(dirname, exist_ok=True)
                    with open(filepath, "w", encoding="utf-8-sig") as f:
                        f.write(patch["replace"])
                    applied_count += 1
                else:  # EDIT
                    with open(filepath, "r", encoding="utf-8-sig") as f:
                        content = normalize_newlines(f.read())
                    search_target = patch.get("actual_search", patch["search"])
                    if search_target in content:
                        content = content.replace(search_target, patch["replace"], 1)
                        with open(filepath, "w", encoding="utf-8-sig") as f:
                            f.write(content)
                        applied_count += 1
                    else:
                        failed_count += 1
                        patch["msg"] = "Search target not found at apply time"
                        patch["status"] = "Error"
                        continue

                patch["status"] = "Applied"
                patch["msg"] = "Applied successfully"
                patch["var"].set(False)
                patch["diff"] = ""
            except Exception as e:
                failed_count += 1
                patch["msg"] = f"Error: {str(e)}"
                patch["status"] = "Error"

        msg = f"{applied_count} 件のパッチを適用しました。"
        if failed_count > 0:
            msg += f"\n{failed_count} 件のパッチ適用に失敗しました。"

        messagebox.showinfo("適用結果", msg)
        self.evaluate_patches()

    # エラーパッチコピー
    def copy_error_patches(self):
        error_patches = [
            p for p in self.parsed_patches if p["status"] not in ("OK", "Applied")
        ]

        if not error_patches:
            messagebox.showinfo("情報", "コピーするエラーパッチはありません。")
            return

        output = []
        output.append("## ⚠️ Patch Application Error Report\n")
        output.append("To the AI Assistant:")
        output.append(
            "- The following patches failed to apply. Please check the reasons, correct them, and output again."
        )
        output.append("- [Common Causes and Solutions]")
        output.append(
            f"  1. Format Error: You must include the `{MARK_SEP}` delimiter between `{MARK_SEARCH}` and `{MARK_REPLACE}`."
        )
        output.append(
            "  2. Search Target Error: The search block must exactly match the latest state of the target file character by character, including spaces, indentation, and blank lines."
        )
        output.append(
            "  3. File Operation Error: For `[ADD]`, make sure the file doesn't already exist. For `[DELETE]` or `[MOVE]`, ensure the target file exists.\n"
        )
        output.append("``````searchandreplace")

        for patch in error_patches:
            output.append(f"### File: {patch['file']}")
            output.append(f"// Error Reason: {patch['status']} ({patch['msg']})")
            if "Similar location" in patch["msg"]:
                output.append(
                    "// Hint: Check the actual code near the indicated line numbers and ensure the indentation and spacing match exactly."
                )
            elif patch.get("format_error"):
                output.append(
                    f"// Hint: The {MARK_SEP} delimiter is missing. Please separate the before and after code with {MARK_SEP}."
                )

            output.append(MARK_SEARCH)
            output.append(patch["search"])
            if not patch.get("format_error"):
                output.append(MARK_SEP)
                output.append(patch["replace"])
            output.append(MARK_REPLACE)
            output.append("")

        output.append("``````\n")

        text = "\n".join(output)
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo(
            "コピー完了",
            f"{len(error_patches)} 件のエラー情報をクリップボードにコピーしました。",
        )


if __name__ == "__main__":
    app = DevAssistantApp()
    app.mainloop()
