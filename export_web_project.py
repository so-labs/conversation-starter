import os
import datetime

# --- ここを設定してください ---
# メインスクリプトのファイル名を指定します
# MAIN_SCRIPT_NAME = "" # 今回は使用しない

# 例外にするディレクトリのリスト
EXCLUDE_DIRS = ['node_modules', '.git', 'dist']
# -----------------------------

# HTML/JavaScript/CSSファイルのみを対象
EXTENSION_TO_LANG = {
    '.html': 'HTML',
    '.js': 'JavaScript',
    '.css': 'CSS',
}

TARGET_EXTENSIONS = list(EXTENSION_TO_LANG.keys())

def collect_files(root_dir):
    """
    指定されたルートディレクトリとそのサブディレクトリ内の対象ファイルを収集し、
    パスでソートされたパスのジェネレータを返します。
    """
    all_target_files = []
    
    # 全ての対象ファイルを収集
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # 除外ディレクトリをリストから削除
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        
        for file in filenames:
            filepath = os.path.join(dirpath, file)
            if any(filepath.endswith(ext) for ext in TARGET_EXTENSIONS):
                all_target_files.append(filepath)

    # パスでソートして返す
    for f in sorted(all_target_files):
        yield f

def generate_file_tree_map(root_dir, collected_files):
    """
    収集されたファイルリストから、ディレクトリツリーマップの文字列を生成します。
    """
    tree_map = []
    tree_map.append("```tree") # treeコマンド風の表示を想定
    
    # ディレクトリ構造を保持するためのネストされた辞書
    tree_structure = {}

    for filepath in collected_files:
        relative_path = os.path.relpath(filepath, root_dir)
        parts = relative_path.split(os.sep)
        
        current_level = tree_structure
        for i, part in enumerate(parts):
            if i == len(parts) - 1: # ファイル名の場合
                if "__files__" not in current_level:
                    current_level["__files__"] = []
                current_level["__files__"].append(part)
            else: # ディレクトリの場合
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]
    
    def walk_tree(node, prefix=""):
        # ディレクトリとファイルを区別して取得
        dirs = sorted([k for k in node.keys() if k != "__files__"])
        files = sorted(node.get("__files__", []))
        
        all_items = files + dirs # ファイルを先に、次にディレクトリを処理する順

        for i, item in enumerate(all_items):
            is_last_item = (i == len(all_items) - 1)
            
            indent_prefix = ""
            if is_last_item:
                tree_map.append(f"{prefix}└── {item}")
                indent_prefix = prefix + "    " # 最後のアイテムの子はインデントのみ
            else:
                tree_map.append(f"{prefix}├── {item}")
                indent_prefix = prefix + "│   " # 途中のアイテムの子は縦線とインデント

            if item in dirs:
                walk_tree(node[item], indent_prefix)

    walk_tree(tree_structure)
    tree_map.append("```")
    tree_map.append("\n") # 最後に空行を1つ追加
    
    return "\n".join(tree_map)


def export_as_markdown(root_dir):
    """
    指定されたルートディレクトリのコードをMarkdown形式でエクスポートします。
    生成されたMarkdownファイルはルートディレクトリに保存されます。
    """
    project_name = os.path.basename(os.path.abspath(root_dir))
    
    # ファイル名: [export_ディレクトリ名_YYYY-MM-DD.md]
    timestamp_date = datetime.datetime.now().strftime("%Y-%m-%d")
    output_filename = f"export_{project_name}_{timestamp_date}.md"
    output_path = os.path.join(root_dir, output_filename) # 保存先はルートディレクトリ

    # 収集するファイルを事前にリスト化（ツリーマップ生成のため）
    collected_files_list = list(collect_files(root_dir))

    # ファイルが既に存在する場合は上書き
    with open(output_path, 'w', encoding='utf-8') as out_file:
        out_file.write(f"# ❖ Project: {project_name}\n\n")

        # --- ファイルツリーマップの生成と書き込み ---
        file_tree_map_content = generate_file_tree_map(root_dir, collected_files_list)
        out_file.write("--- **Project Structure** ---\n\n")
        out_file.write("## ファイル構成\n\n")
        out_file.write(file_tree_map_content)
        # --------------------------------------------------

        # --- ファイル内容の全体的な見出し ---
        out_file.write("--- **File Contents** ---\n\n")
        out_file.write("## ファイル内容\n\n")
        # -----------------------------------------------------------

        # 各ファイルのコンテンツを書き込み
        for i, filepath in enumerate(collected_files_list):
            relative_path = os.path.relpath(filepath, root_dir)
            _, ext = os.path.splitext(filepath)
            lang = EXTENSION_TO_LANG.get(ext, '')

            out_file.write(f"### File: {relative_path}\n\n")
            out_file.write(f"```{lang}\n")

            try:
                with open(filepath, 'r', encoding='utf-8-sig') as f: # utf-8-sig を試す
                    out_file.write(f.read().rstrip())
            except Exception as e:
                out_file.write(f"--- ファイルの読み込みエラー: {e} ---\n")

            # 最後のファイルでなければ改行を2つ（コードブロック後と次のファイル見出し前）、
            # 最後のファイルであれば改行を1つにする
            if i < len(collected_files_list) - 1:
                out_file.write("\n```\n\n") # 次のファイルの見出しと区切るため2つ
            else:
                out_file.write("\n```\n") # 最後のファイルの後は1つ
            # ------------------------------------------------------------

    print(f"Markdown export completed: {output_path}")

if __name__ == "__main__":
    # スクリプトがあるディレクトリをプロジェクトのルートとする
    project_root = os.path.abspath(os.path.dirname(__file__))
    export_as_markdown(project_root)