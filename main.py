import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import os
import queue

from gui_view import MainView, SettingsWindow
from config_manager import load_config, save_config
from blast_worker import BlastWorker


class Application:
    def __init__(self, master):
        self.master = master
        self.config = load_config()
        self.view = MainView(master)
        self.queue = queue.Queue()

        # --- 状態管理フラグ ---
        self.is_running = False  # 解析実行中か
        self.stop_requested = False  # 停止が要求されたか
        self.running_filepath = None  # 現在実行中のファイルパス

        self.current_worker = None  # 現在実行中のワーカースレッドへの参照

        # --- ボタンとイベントに関数を紐づける ---
        self.view.add_button.config(command=self.add_files)
        self.view.remove_button.config(command=self.remove_selected)
        self.view.clear_button.config(command=self.clear_list)
        self.view.run_button.config(command=self.start_analysis_confirm)
        self.view.stop_button.config(command=self.stop_analysis_confirm)
        self.view.listbox.bind("<Double-Button-1>", self.open_in_notepad)

        # --- メニューを設定 ---
        self.view.file_menu.add_command(
            label="設定...", command=self.open_settings_window
        )
        self.view.file_menu.add_separator()
        self.view.file_menu.add_command(
            label="終了", command=self.on_closing
        )  # ウィンドウを閉じる動作をフック
        self.toggle_buttons_on_run_state(False)  # 初期状態をセット

        # ウィンドウの「×」ボタンが押されたときの動作を定義
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    # --- ファイル管理メソッド ---
    def add_files(self):
        """「ファイル追加」ボタンが押されたときの処理"""
        # is_running中でも追加は許可
        filepaths = filedialog.askopenfilenames(
            title="解析するFASTAファイルを選択",
            filetypes=[("FASTA files", "*.fasta *.fa *.fna"), ("All files", "*.*")],
        )
        if filepaths:
            for path in filepaths:
                self.view.listbox.insert(tk.END, path)
            self.update_status(f"{len(filepaths)}個のファイルを追加しました。")

    def remove_selected(self):
        """【改修】実行中のファイルは削除しないようにする"""
        selected_indices = self.view.listbox.curselection()
        if not selected_indices:
            return

        files_deleted = 0
        running_file_selected = False
        for i in reversed(selected_indices):
            # 実行中のアイテム "(実行中...) ..." かどうかをチェック
            item_text = self.view.listbox.get(i)
            is_currently_running_item = item_text.startswith("(実行中...)")

            if is_currently_running_item:
                running_file_selected = True
                continue  # 実行中のファイルはスキップ

            self.view.listbox.delete(i)
            files_deleted += 1

        if running_file_selected:
            self.update_status("エラー: 実行中のファイルは削除できません。")
        elif files_deleted > 0:
            self.update_status(f"{files_deleted}個のファイルを選択から削除しました。")

    def clear_list(self):
        """【改修】確認ダイアログと、実行中のチェックを追加"""
        if not self.view.listbox.size() > 0:
            return

        # 実行中のファイルを除いたリストを作成して確認
        items_to_clear = []
        for i in range(self.view.listbox.size()):
            item_text = self.view.listbox.get(i)
            if not item_text.startswith("(実行中...)"):
                items_to_clear.append(item_text)

        if not items_to_clear:
            if self.is_running:
                messagebox.showinfo(
                    "情報", "実行中のファイル以外にクリアする項目はありません。"
                )
            return  # クリア対象がない

        if messagebox.askyesno(
            "確認",
            f"{len(items_to_clear)}個のファイルをリストからクリアしますか？\n(実行中のファイルがある場合、それは残ります)",
        ):
            # 実行中のファイル以外の全てを削除
            non_running_indices = []
            for i in range(self.view.listbox.size()):
                if not self.view.listbox.get(i).startswith("(実行中...)"):
                    non_running_indices.append(i)

            for i in reversed(non_running_indices):
                self.view.listbox.delete(i)

            self.update_status("リストをクリアしました。")

    def open_in_notepad(self, event):
        """リストボックスの項目がダブルクリックされたときの処理"""
        selected_indices = self.view.listbox.curselection()
        if not selected_indices:
            return

        filepath_display = self.view.listbox.get(selected_indices[0])
        # 表示されているテキストを取得
        filepath_actual = filepath_display
        # デフォルトは表示通り

        # 実行中の場合、ファイルパスから "(実行中...)" のプレフィックスを取り除く
        if filepath_display.startswith("(実行中...)"):
            filepath_actual = filepath_display.replace("(実行中...) ", "")
        elif filepath_display.startswith("(エラー)"):
            filepath_actual = filepath_display.replace("(エラー) ", "")

        try:
            # 実際のファイルパスで開く
            if os.path.exists(filepath_actual):
                subprocess.Popen(["notepad.exe", filepath_actual])
            else:
                # processedフォルダに移動されている可能性を考慮
                base_dir = os.path.dirname(filepath_actual)
                filename = os.path.basename(filepath_actual)
                processed_path = os.path.join(base_dir, "processed", filename)
                if os.path.exists(processed_path):
                    subprocess.Popen(["notepad.exe", processed_path])
                else:
                    self.update_status(
                        f"エラー: ファイルが見つかりません - {filepath_actual}"
                    )

        except Exception as e:
            self.update_status(f"エラー: ファイルを開けませんでした - {e}")

    # --- (C-2) 事前検証メソッド (新設) ---
    def _validate_settings(self):
        """設定ファイルの内容が実在するかを検証する"""
        try:
            blast_path = self.config.get("PATHS", "blast_path")
            db_path = self.config.get("PATHS", "database_path")
            db_name = self.config.get("BLAST_SETTINGS", "database_name")

            # 1. blastn.exe の存在確認
            blastn_exe_path = os.path.join(blast_path, "blastn.exe")
            if not os.path.exists(blastn_exe_path):
                messagebox.showerror(
                    "設定エラー",
                    f"blastn.exe が見つかりません。\n"
                    f"パス: {blastn_exe_path}\n"
                    "設定画面で [BLAST+ binフォルダ] を確認してください。",
                )
                return False

            # 2. データベースファイル (.nal または .pal) の存在確認
            # .nal (nucleotide) または .pal (protein) がDBの代表ファイル
            db_file_path_nal = os.path.join(db_path, f"{db_name}.nal")
            db_file_path_pal = os.path.join(db_path, f"{db_name}.pal")

            if not os.path.exists(db_file_path_nal) and not os.path.exists(
                db_file_path_pal
            ):
                messagebox.showerror(
                    "設定エラー",
                    f"データベースファイル ({db_name}.nal または .pal) が見つかりません。\n"
                    f"パス: {db_path}\n"
                    "設定画面で [DBフォルダ] と [DB名] を確認してください。",
                )
                return False

            return True  # 全ての検証をパス

        except Exception as e:
            messagebox.showerror(
                "設定エラー", f"設定ファイルの読み込み中にエラーが発生しました。\n{e}"
            )
            return False

    # --- (C-3) 解析実行ロジック (修正) ---
    def start_analysis_confirm(self):
        """「解析実行」ボタンの確認ダイアログ (事前検証を追加)"""

        # (C-3) 事前検証を実行
        if not self._validate_settings():
            self.update_status("設定に不備があります。解析を開始できません。")
            return

        items_to_run = 0
        for i in range(self.view.listbox.size()):
            item_text = self.view.listbox.get(i)
            if not item_text.startswith("(実行中...)") and not item_text.startswith(
                "(エラー)"
            ):
                items_to_run += 1

        if items_to_run == 0:
            messagebox.showwarning("警告", "解析対象のファイルがありません。")
            return

        if messagebox.askyesno(
            "確認", f"{items_to_run}個のファイルの解析を開始しますか？"
        ):
            self.start_analysis_task()

    def start_analysis_task(self):
        """解析タスクの本体（キュー監視の開始）"""
        if self.is_running:
            return
            # 既に実行中なら何もしない

        # 実行中でない最初のファイルを探す
        next_file_index = -1
        for i in range(self.view.listbox.size()):
            # (エラー) で始まるものも除外する
            item_text = self.view.listbox.get(i)
            if not item_text.startswith("(実行中...)") and not item_text.startswith(
                "(エラー)"
            ):
                next_file_index = i
                break

        if next_file_index == -1:
            # 解析待ちのファイルがない
            if not any(
                item.startswith("(実行中...)")
                for item in self.view.listbox.get(0, tk.END)
            ):
                # 実行中のファイルもなければ完了
                self.update_status("全てのファイルが処理されました。")
            return

        self.is_running = True
        self.stop_requested = False
        self.toggle_buttons_on_run_state(True)
        # ボタンの状態を「実行中」モードにする

        # 実行対象のファイルパスを取得
        self.running_filepath = self.view.listbox.get(next_file_index)

        # リストの表示を実行中に更新
        self.view.listbox.delete(next_file_index)
        self.view.listbox.insert(
            next_file_index, f"(実行中...) {self.running_filepath}"
        )
        self.view.listbox.itemconfig(next_file_index, {"fg": "blue"})
        # 色を変更

        # ワーカースレッドを作成して開始
        # worker 変数を self.current_worker に格納
        self.current_worker = BlastWorker(
            self.running_filepath, self.queue, self.config
        )
        self.current_worker.start()

        # 100ミリ秒後にキューの監視を開始
        self.master.after(100, self.process_queue)

    def stop_analysis_confirm(self):
        """「解析中止」ボタンの確認ダイアログ"""
        if not self.is_running:
            self.update_status("現在、解析は実行されていません。")
            return

        if messagebox.askyesno(
            "確認", "現在実行中の処理が完了した後、解析を中止しますか？"
        ):
            self.stop_requested = True
            self.update_status(
                "中止を要求しました。現在の処理が完了次第、停止します..."
            )
            self.view.stop_button.config(state=tk.DISABLED)
            # 中止ボタンを無効化

    # --- (B) リファクタリング済みメソッド ---

    def _update_progress(self, message):
        """(B-2) 進捗メッセージの処理"""
        self.view.progressbar["value"] = message["value"]
        self.update_status(message["message"])

    def _handle_blast_completion(self, message):
        """(B-3) BLAST正常完了メッセージの処理"""
        # 完了したファイル "(実行中...)" をリストから探して削除
        original_path = message["original_path"]
        running_item_index = -1
        for i in range(self.view.listbox.size()):
            item_text = self.view.listbox.get(i)
            if item_text.startswith("(実行中...)") and item_text.endswith(
                original_path
            ):
                running_item_index = i
                break
        if running_item_index != -1:
            self.view.listbox.delete(running_item_index)

        self.running_filepath = None
        self.view.progressbar["value"] = 0
        self.is_running = False
        # 次のファイルに移る前に一旦Falseに
        self.current_worker = None  # ワーカーへの参照をクリア

        if self.stop_requested:
            # 「中止」が要求されていた場合
            self.update_status("解析を中止しました。")
            self.stop_requested = False
            self.toggle_buttons_on_run_state(False)
            # ボタンを通常モードに戻す
            # ★リファクタリング: 'return' を削除
        else:
            # 解析待ちのファイルがあるか確認
            items_to_run = 0
            for i in range(self.view.listbox.size()):
                item_text = self.view.listbox.get(i)
                if not item_text.startswith("(実行中...)") and not item_text.startswith(
                    "(エラー)"
                ):
                    items_to_run += 1

            if items_to_run > 0:
                # 次のタスクを開始
                # (start_analysis_taskが is_running=True と after をセットする)
                self.start_analysis_task()
            else:
                # 全て完了
                self.update_status("全ての解析が完了しました。")
                messagebox.showinfo("成功", "全ての解析が完了しました。")
                self.toggle_buttons_on_run_state(False)
                # (is_running=False になる)
                # ★リファクタリング: 'return' を削除

    # --- (C-5) エラー処理メソッド (改修) ---
    def _handle_blast_error(self, message):
        """(C-5) 構造化エラーを解釈して、分かりやすいメッセージを表示する"""

        # (C-5) エラー種別に応じてメッセージを出し分ける
        error_type = message.get("error_type", "GenericError")

        if error_type == "FileNotFoundError":
            # (C-5) FileNotFoundError の場合は、設定を確認するよう促す
            messagebox.showerror("実行時エラー", message["message"])

        elif error_type == "CalledProcessError":
            # (C-5) BLAST実行エラーの場合は、DB名やFASTAファイルを確認するよう促す
            stderr_details = message.get("stderr", "詳細不明")
            if len(stderr_details) > 300:  # 長すぎるエラー詳細は省略
                stderr_details = stderr_details[:300] + "..."
            messagebox.showerror(
                "BLAST実行エラー", f"{message['message']}\n\n詳細:\n{stderr_details}"
            )

        elif error_type == "MoveFileError":
            # (C-5) ファイル移動エラー (これは完了扱い)
            messagebox.showwarning("警告", message["message"])
            # ★これは完了扱いなので、_handle_blast_completion を呼ぶ
            self._handle_blast_completion(message)
            return  # この後のエラー処理（赤字化）をスキップ

        else:  # GenericError やその他の予期せぬエラー
            messagebox.showerror("エラー", message["message"])

        # エラーが起きたファイル "(実行中...)" をリストから探して削除
        error_path = message.get("original_path", self.running_filepath)
        # Workerからパスが来ればそれを使う
        running_item_index = -1
        for i in range(self.view.listbox.size()):
            item_text = self.view.listbox.get(i)
            if item_text.startswith("(実行中...)") and item_text.endswith(error_path):
                running_item_index = i
                break
        if running_item_index != -1:
            self.view.listbox.delete(running_item_index)
            # エラー表示で再挿入
            self.view.listbox.insert(tk.END, f"(エラー) {error_path}")
            self.view.listbox.itemconfig(tk.END, {"fg": "red"})

        self.running_filepath = None
        self.view.progressbar["value"] = 0
        self.is_running = False  # 次のファイルに移る前に一旦Falseに
        self.current_worker = None  # ワーカーへの参照をクリア

        # エラー発生時も中止要求かリストが空なら停止
        items_to_run = 0
        for i in range(self.view.listbox.size()):
            item_text = self.view.listbox.get(i)
            if not item_text.startswith("(実行中...)") and not item_text.startswith(
                "(エラー)"
            ):
                items_to_run += 1

        if self.stop_requested or items_to_run == 0:
            self.update_status("エラーにより解析を停止しました。")
            self.stop_requested = False
            self.toggle_buttons_on_run_state(False)
            # (is_running=False になる)
            # ★リファクタリング: 'return' を削除
        else:
            # 次のタスクを開始し、監視を継続
            # (start_analysis_taskが is_running=True と after をセットする)
            self.start_analysis_task()

    def process_queue(self):
        """(B-5) キューを監視し、各処理メソッドに振り分ける"""
        try:
            message = self.queue.get_nowait()

            # --- 1. 進捗メッセージ ---
            if message["type"] == "progress":
                self._update_progress(message)

            # --- 2. ファイル完了メッセージ ---
            elif message["type"] == "file_done":
                self._handle_blast_completion(message)

            # --- 3. エラーメッセージ ---
            elif message["type"] == "error":
                self._handle_blast_error(message)

        except queue.Empty:
            pass  # キューが空の場合は何もしない

        # --- ★監視を継続する after はここに集約 ---
        # 状態（is_running）は各ハンドラ(_handle_...)が適切に設定する。
        # ここでは、その状態を見て、監視を継続するかを判断する。
        if self.is_running or not self.queue.empty():
            # start_analysis_task が is_running を True にするので、
            # 次の反復で start_analysis_task が呼ばれない場合にのみ after をセット
            # if文の条件が複雑化するので、シンプルに毎回 after を呼ぶことにする
            self.master.after(100, self.process_queue)

    def toggle_buttons_on_run_state(self, is_running):
        """解析実行中/完了時に実行・中止ボタンの状態のみを切り替える"""
        self.is_running = is_running
        run_state = tk.DISABLED if is_running else tk.NORMAL
        stop_state = tk.NORMAL if is_running else tk.DISABLED

        self.view.run_button.config(state=run_state)
        self.view.stop_button.config(state=stop_state)
        # 他のボタン（追加、削除、クリア）とリスト操作は常に有効にする
        self.view.add_button.config(state=tk.NORMAL)
        self.view.remove_button.config(state=tk.NORMAL)
        self.view.clear_button.config(state=tk.NORMAL)
        self.view.listbox.bind("<Button-1>", self.view.listbox.on_click)
        self.view.listbox.bind("<B1-Motion>", self.view.listbox.on_drag)
        # 解析中止要求中は中止ボタンを無効化
        if self.stop_requested:
            self.view.stop_button.config(state=tk.DISABLED)

    # --- 設定ウィンドウのメソッド ---
    def open_settings_window(self):
        # is_running中でも設定は開けるようにする（ただし保存時の挙動は注意）
        self.settings_window = SettingsWindow(self.master)

        # (C-2) config.get のエラーを捕捉
        try:
            self.settings_window.blast_path_entry.insert(
                0, self.config.get("PATHS", "blast_path")
            )
            self.settings_window.db_path_entry.insert(
                0, self.config.get("PATHS", "database_path")
            )
            self.settings_window.db_name_entry.insert(
                0, self.config.get("BLAST_SETTINGS", "database_name")
            )
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            self.update_status(f"設定ファイルエラー: {e}")
            # エラーがあっても設定画面は開く（デフォルト値で）

        self.settings_window.blast_path_button.config(
            command=lambda: self.browse_folder("blast")
        )
        self.settings_window.db_path_button.config(
            command=lambda: self.browse_folder("db")
        )
        self.settings_window.db_name_button.config(command=self.browse_database_file)
        self.settings_window.save_button.config(command=self.save_settings)
        self.settings_window.cancel_button.config(command=self.settings_window.destroy)

    def browse_folder(self, path_type):
        folder_path = filedialog.askdirectory(title="フォルダを選択")
        if not folder_path:
            return

        entry_widget = None
        if path_type == "blast":
            entry_widget = self.settings_window.blast_path_entry
        elif path_type == "db":
            entry_widget = self.settings_window.db_path_entry

        if entry_widget:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, folder_path)

    def browse_database_file(self):
        db_folder = self.settings_window.db_path_entry.get()
        if not os.path.isdir(db_folder):
            messagebox.showwarning(
                "警告", "先に有効な [DBフォルダ] を指定してください。"
            )
            db_folder = "."  # カレントディレクトリを開く

        filepath = filedialog.askopenfilename(
            title="代表のDBファイルを選択 (.nal または .pal)",
            initialdir=db_folder,
            filetypes=[("BLAST DB files", "*.nal *.pal"), ("All files", "*.*")],
        )
        if not filepath:
            return

        filename = os.path.basename(filepath)
        # .nal や .00.nal などの拡張子を取り除く
        base_name = filename.split(".")[0]

        self.settings_window.db_name_entry.delete(0, tk.END)
        self.settings_window.db_name_entry.insert(0, base_name)

    def save_settings(self):
        # 解析実行中は設定を変更できないようにする（安全のため）
        if self.is_running:
            messagebox.showwarning("警告", "解析実行中は設定を変更できません。")
            return

        # (C-2) セクションが存在しない場合に備える
        if not self.config.has_section("PATHS"):
            self.config.add_section("PATHS")
        if not self.config.has_section("BLAST_SETTINGS"):
            self.config.add_section("BLAST_SETTINGS")

        self.config.set(
            "PATHS", "blast_path", self.settings_window.blast_path_entry.get()
        )
        self.config.set(
            "PATHS", "database_path", self.settings_window.db_path_entry.get()
        )
        self.config.set(
            "BLAST_SETTINGS", "database_name", self.settings_window.db_name_entry.get()
        )

        save_config(self.config)
        self.settings_window.destroy()
        self.update_status("設定を保存しました。")
        messagebox.showinfo("成功", "設定が正常に保存されました。")

    def update_status(self, message):
        """ステータスバーのメッセージを更新する"""
        self.view.status_label.config(text=message)

    def on_closing(self):
        """ウィンドウが閉じられるときの処理"""
        if self.is_running:
            # ★修正: メッセージを「強制終了」に変更
            if messagebox.askyesno(
                "確認",
                "解析が実行中です。本当に終了しますか？\n(実行中のBLASTプロセスは強制終了されます)",
            ):
                # 1. 実行中のワーカースレッドに停止命令を出す
                if self.current_worker:
                    try:
                        # blast_worker.py に追加した terminate() を呼び出す
                        self.current_worker.terminate()
                        print("ワーカースレッドに終了シグナルを送信しました。")
                    except Exception as e:
                        print(f"ワーカー終了処理中にエラー: {e}")

                # 2. メインウィンドウを破棄
                #    (ワーカーは daemon=True なので、メインスレッドが終了すれば道連れで終了する)
                self.master.destroy()
            else:
                return  # 終了をキャンセル
        else:
            self.master.destroy()


if __name__ == "__main__":
    # (C-4) Windowsでのサブプロセス起動時の問題を回避
    # multiprocessing を import していると、PyInstallerで .exe 化した際に
    # サブプロセスが無限に起動する問題が発生することがあるため、
    # main.py では subprocess のみを使用する。
    # (もし将来的に multiprocessing を使う場合は、 freeze_support() が必要)

    root = tk.Tk()
    app = Application(root)
    root.mainloop()
