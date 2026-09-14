"""
OpenBCI 脑电采集与分析平台 — 统一入口。

用法：
    python main.py           启动图形界面（默认）
    python main.py --cli     启动命令行控制面板（REPL）
    python main.py --help    查看帮助

图形界面：状态栏 + 采集控制 + 模型结果网格 + 日志面板
命令行：  help / status / start / stop / config / model / record ...

首次运行请先把 config/default.example.yaml 复制为 config/default.yaml 并按自己的串口修改。
"""
from __future__ import annotations

import sys

USAGE = """OpenBCI 脑电采集与分析平台

用法:
    python main.py           启动图形界面（默认）
    python main.py --cli     启动命令行控制面板
    python main.py --help    显示本帮助

准备:
    1. pip install -r requirements.txt
    2. 复制 config/default.example.yaml -> config/default.yaml，修改串口等参数
    3. 无硬件时可把配置里的「使用合成板」设为 true 先跑通链路
"""


def run_gui() -> None:
    """启动轻量图形界面。"""
    from eeg_control_ui import main as gui_main

    gui_main()


def run_cli() -> None:
    """启动命令行控制面板。"""
    from eeg_control_panel import main as cli_main

    cli_main()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if not args or args[0] in {"gui", "--gui", "-g"}:
        run_gui()
        return 0
    if args[0] in {"cli", "--cli", "-c"}:
        run_cli()
        return 0
    if args[0] in {"-h", "--help", "help"}:
        print(USAGE)
        return 0

    print(f"未知参数: {args[0]}\n")
    print(USAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
