# blast_worker.py
import subprocess
import threading
import os
import shutil


class BlastWorker(threading.Thread):
    """
    【改修】単一のFASTAファイルのBLASTn実行を担当するクラス
    """

    def __init__(self, filepath_to_process, queue, config):
        """
        Args:
            filepath_to_process (str): 処理対象の単一のファイルパス
            queue (queue.Queue): GUIへ通知を送るためのキュー
            config (configparser.ConfigParser): 設定情報
        """
        super().__init__()
        self.filepath = filepath_to_process
        self.queue = queue
        self.config = config
        self.daemon = True  # メインスレッドが終了したら、このスレッドも終了する

        self.process = None  # 実行中のサブプロセスを保持する
        self.terminated = False  # 外部から強制終了されたかを追跡するフラグ

    def run(self):
        """【改修】単一のファイルに対する処理を実行"""
        filename = os.path.basename(self.filepath)
        try:
            # GUIに進捗状況を通知（処理中 50%）
            self.queue.put(
                {"type": "progress", "value": 50, "message": f"処理中: {filename}"}
            )

            # BLAST実行（本体）
            # (C-4) _execute_blast_popen 内でエラーを捕捉し、
            # 構造化されたエラー辞書を生成する
            blast_command, blast_cwd = self._build_blast_command(self.filepath)

            # (C-4) Popenの実行をtry...exceptで囲む
            self.process = subprocess.Popen(
                blast_command,
                cwd=blast_cwd,  # blastnの実行場所を指定
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                # (C-4) Windowsでサブプロセスを隠す
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            # サブプロセスの完了を待機
            # communicate() はプロセスが終了するまでブロックする
            stdout_data, stderr_data = self.process.communicate()
            return_code = self.process.returncode

            # --- ★追加 (ステップ3) ---
            # 強制終了フラグが立っていたら、ここで処理を中断
            # (キューに完了/エラーメッセージを送らない)
            if self.terminated:
                print(
                    "Workerが外部から停止されたため、キューへの通知をスキップします。"
                )
                return

            # (C-4) エラーチェックを強化
            # CalledProcessErrorを模倣して、BLAST実行エラーを検知
            if return_code != 0:
                # BLAST実行自体が失敗した場合 (DBが見つからない、FASTAが不正など)
                raise subprocess.CalledProcessError(
                    returncode=return_code,
                    cmd=blast_command,
                    stderr=stderr_data,
                    stdout=stdout_data,
                )

            # --- 6. 処理成功時：ファイルを 'processed' フォルダに移動 ---
            self._move_to_processed(self.filepath)

            # 処理成功をGUIに通知
            # 完了した元のファイルパスをGUIに送り返す
            self.queue.put({"type": "file_done", "original_path": self.filepath})

        # (C-4) 具体的な例外を捕捉する
        except FileNotFoundError as e:
            # blastn.exe が見つからなかった場合など
            if not self.terminated:
                self.queue.put(
                    {
                        "type": "error",
                        "error_type": "FileNotFoundError",
                        "message": f"実行エラー: '{e.filename}' が見つかりません。\n"
                        "設定画面でBLAST+ (bin) フォルダのパスが\n"
                        "正しく設定されているか確認してください。",
                        "original_path": self.filepath,
                    }
                )
        except subprocess.CalledProcessError as e:
            # BLAST実行がゼロ以外のリターンコードを返した場合
            if not self.terminated:
                self.queue.put(
                    {
                        "type": "error",
                        "error_type": "CalledProcessError",
                        "message": "BLAST実行エラー:\n"
                        "データベース名が間違っているか、\n"
                        "入力FASTAファイルが破損している可能性があります。",
                        "stderr": e.stderr,  # エラー詳細
                        "original_path": self.filepath,
                    }
                )
        except Exception as e:
            # その他の予期せぬエラー
            if not self.terminated:
                self.queue.put(
                    {
                        "type": "error",
                        "error_type": "GenericError",
                        "message": f"予期せぬエラー: {filename} の処理中に問題が発生しました。\n{e}",
                        "original_path": self.filepath,
                    }
                )

    def _build_blast_command(self, fasta_file):
        """
        【C案 改修】設定を読み込み、BLASTコマンドと実行ディレクトリを構築する。
        - FileNotFoundErrorを早期検知するため、パスの構築と実行を分離
        """
        # --- 1. 設定ファイルからパスと設定を読み込む ---
        try:
            blast_path = self.config.get("PATHS", "blast_path")
            db_path = self.config.get("PATHS", "database_path")
            db_name = self.config.get("BLAST_SETTINGS", "database_name")
            num_threads = self.config.get("BLAST_SETTINGS", "num_threads")
        except Exception as e:
            raise RuntimeError(f"config.iniからの設定読み込みエラー: {e}")

        # 実行パスとDBパスを動的に構築
        # (C-4) FileNotFoundErrorを発生させるため、blastn.exeのフルパスを構築
        blastn_exe = os.path.join(blast_path, "blastn.exe")

        # (C-4) DBパスの構築方法を変更
        # blastnは -db オプションにフルパスを渡すよりも、
        # 実行カレントディレクトリ(cwd)をDBパスに設定し、-db に名前だけ渡す方が
        # .nal/.palエイリアスファイルの解決において堅牢
        full_db_path_name = db_name  # os.path.join(db_path, db_name)

        output_file = f"{fasta_file}_result.csv"

        # --- 3. 実行するコマンドをリストとして構築 ---
        command = [
            blastn_exe,
            "-task",
            "megablast",
            "-query",
            fasta_file,
            "-db",
            full_db_path_name,  # DB名のみ
            "-out",
            output_file,
            "-outfmt",
            "6 pident sacc staxid ssciname stitle",
            "-num_threads",
            num_threads,
        ]

        # (C-4) 実行時のカレントワーキングディレクトリとしてDBパスを渡す
        return command, db_path

    def _move_to_processed(self, fasta_file):
        """【★分離 (ステップ3)】ファイル移動ロジックを分離"""
        # (元々 _execute_blast 内にあったコードをそのまま移動)
        # --- 6. 処理成功時：ファイルを 'processed' フォルダに移動 ---
        # 移動元のファイルが存在するディレクトリ
        try:
            source_directory = os.path.dirname(fasta_file)
            # 移動先の 'processed' フォルダのパス
            processed_folder = os.path.join(source_directory, "processed")
            # 'processed' フォルダが存在しなければ作成する
            os.makedirs(processed_folder, exist_ok=True)
            # 移動元のファイル名
            file_name = os.path.basename(fasta_file)
            # 最終的な移動先のファイルパス
            destination_file = os.path.join(processed_folder, file_name)
            # ファイルを移動する
            shutil.move(fasta_file, destination_file)
        except Exception as e:
            # ファイル移動のエラーはGUIに通知する（ただし解析は完了している）
            self.queue.put(
                {
                    "type": "error",
                    "error_type": "MoveFileError",
                    "message": f"警告: 解析は完了しましたが、処理済みファイルの移動に失敗しました。\n{e}",
                    "original_path": fasta_file,  # エラーだが、完了扱いにする
                }
            )

    def terminate(self):
        """外部 (main.py) から呼び出され、サブプロセスを強制終了する"""
        print(f"Terminate() が {self.filepath} に対して呼ばれました。")
        self.terminated = True  # まずフラグを立てる (キュー通知を抑制)

        if self.process and self.process.poll() is None:
            # プロセスがまだ実行中の場合
            try:
                self.process.terminate()  # SIGTERM を送信
                print(f"プロセス {self.process.pid} に terminate() を送信しました。")
            except Exception as e:
                print(f"プロセス terminate() 中にエラー: {e}")
                try:
                    self.process.kill()  # 強制終了
                    print(f"プロセス {self.process.pid} に kill() を送信しました。")
                except Exception as e_kill:
                    print(f"プロセス kill() 中にエラー: {e_kill}")
        else:
            print("プロセスは既に終了しているか、開始されていません。")
