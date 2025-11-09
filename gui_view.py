# gui_view.py
import tkinter as tk
from tkinter import ttk
from draggable_listbox import DraggableListbox


class MainView(tk.Frame):
    """
    メインウィンドウの見た目を定義するクラス
    """

    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.master.title("BLASTn 自動解析ツール v0.4.2")
        self.master.geometry("600x450")

        # --- メニューバーの作成 ---
        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)
        self.file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="ファイル", menu=self.file_menu)

        # --- 1. 上部フレーム（ボタン配置用） ---
        top_frame = tk.Frame(self.master)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.add_button = tk.Button(top_frame, text="ファイル追加")
        self.remove_button = tk.Button(top_frame, text="選択を削除")
        self.clear_button = tk.Button(top_frame, text="リストをクリア")

        self.add_button.pack(side=tk.LEFT, padx=2)
        self.remove_button.pack(side=tk.LEFT, padx=2)
        self.clear_button.pack(side=tk.LEFT, padx=2)

        # --- 解析実行/中止ボタンを右側に配置 ---
        self.stop_button = tk.Button(top_frame, text="解析中止", bg="pink")
        self.run_button = tk.Button(top_frame, text="解析実行", bg="lightblue")

        self.run_button.pack(side=tk.RIGHT, padx=2)
        self.stop_button.pack(side=tk.RIGHT, padx=2)

        # --- 2. 中央フレーム（リストボックス配置用） ---
        middle_frame = tk.Frame(self.master)
        middle_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.listbox = DraggableListbox(middle_frame, selectmode=tk.EXTENDED)

        scrollbar = tk.Scrollbar(
            middle_frame, orient=tk.VERTICAL, command=self.listbox.yview
        )
        self.listbox.config(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- 3. 下部フレーム（ステータス表示用） ---
        bottom_frame = tk.Frame(self.master)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        self.status_label = tk.Label(bottom_frame, text="準備完了", anchor=tk.W)
        self.progressbar = ttk.Progressbar(
            bottom_frame, orient=tk.HORIZONTAL, mode="determinate"
        )

        self.status_label.pack(fill=tk.X)
        self.progressbar.pack(fill=tk.X)


class SettingsWindow(tk.Toplevel):
    """
    設定画面の見た目を定義するクラス
    (このクラスのコードは前回のものから変更ありません)
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("設定")
        self.geometry("500x180")  # DB名入力欄のため高さを調整

        main_frame = tk.Frame(self)
        main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # BLAST Path
        blast_path_label = tk.Label(main_frame, text="BLAST+ binフォルダ:")
        self.blast_path_entry = tk.Entry(main_frame, width=50)
        self.blast_path_button = tk.Button(main_frame, text="参照...")
        blast_path_label.grid(row=0, column=0, sticky=tk.W, pady=2)
        self.blast_path_entry.grid(row=0, column=1, sticky=tk.EW, pady=2)
        self.blast_path_button.grid(row=0, column=2, padx=5, pady=2)

        # Database Path
        db_path_label = tk.Label(main_frame, text="DBフォルダ:")
        self.db_path_entry = tk.Entry(main_frame, width=50)
        self.db_path_button = tk.Button(main_frame, text="参照...")
        db_path_label.grid(row=1, column=0, sticky=tk.W, pady=2)
        self.db_path_entry.grid(row=1, column=1, sticky=tk.EW, pady=2)
        self.db_path_button.grid(row=1, column=2, padx=5, pady=2)

        # Database Name
        db_name_label = tk.Label(main_frame, text="DB名:")
        self.db_name_entry = tk.Entry(main_frame, width=50)
        self.db_name_button = tk.Button(main_frame, text="DBファイルを選択...")
        db_name_label.grid(row=2, column=0, sticky=tk.W, pady=2)
        self.db_name_entry.grid(row=2, column=1, sticky=tk.EW, pady=2)
        self.db_name_button.grid(row=2, column=2, padx=5, pady=2)

        main_frame.grid_columnconfigure(1, weight=1)

        # Bottom buttons
        button_frame = tk.Frame(self)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))

        self.save_button = tk.Button(button_frame, text="保存")
        self.cancel_button = tk.Button(button_frame, text="キャンセル")

        self.save_button.pack(side=tk.RIGHT, padx=5)
        self.cancel_button.pack(side=tk.RIGHT)
