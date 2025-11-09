# config_manager.py
import configparser
import os

CONFIG_PATH = "config.ini"


def load_config():
    """設定ファイル (config.ini) を読み込む。なければデフォルトで作成する。"""
    config = configparser.ConfigParser()

    if not os.path.exists(CONFIG_PATH):
        # デフォルト設定の作成
        config["PATHS"] = {
            "blast_path": "C:\\ncbi-blast-2.17.0+\\bin",
            "database_path": "C:\\blast_db",
        }
        config["BLAST_SETTINGS"] = {
            "database_name": "ref_prok_rep_genomes",
            "num_threads": "8",
        }
        save_config(config)
        print(f"'{CONFIG_PATH}' が見つからなかったため、デフォルト設定で作成しました。")

    config.read(CONFIG_PATH, encoding="utf-8")
    return config


def save_config(config_object):
    """設定オブジェクトをconfig.iniファイルに書き込む。"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as configfile:
        config_object.write(configfile)


if __name__ == "__main__":
    # テスト実行
    config = load_config()
    print("--- 設定ファイルの読み込みテスト ---")
    print(f"BLAST Path: {config['PATHS']['blast_path']}")
    print(f"DB Path: {config['PATHS']['database_path']}")

    # 保存テスト
    config.set("BLAST_SETTINGS", "num_threads", "16")
    save_config(config)
    print("\n--- 設定ファイルの保存テスト ---")
    print("num_threadsを16に更新して保存しました。")
