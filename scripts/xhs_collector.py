"""启动、查看状态或停止本应用的小红书采集组件。"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core import config
from app.modules.experiences import launcher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "stop"], nargs="?", default="start")
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    if args.data_dir:
        config.DATA_DIR = args.data_dir.resolve()
    if args.action == "status":
        state = launcher.read_status()
        print(json.dumps({"status": state["status"], "message": state["message"]}, ensure_ascii=False))
        return
    if args.action == "stop":
        launcher.stop()
        print("已请求停止本应用管理的采集服务，登录文件保留。")
        return
    try:
        launcher.start()
    except Exception as error:
        message = str(error) if isinstance(error, RuntimeError) else "下载或启动采集服务失败，请检查网络后重试"
        launcher.write_status("failed", message)
        print(message)
        raise SystemExit(1) from None
    print(launcher.read_status()["message"])


if __name__ == "__main__":
    main()
