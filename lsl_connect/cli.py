"""
第 8 课：命令行控制面板（REPL）。
主线程解析命令，调用 ServiceManager。
"""

from __future__ import annotations

from lsl_connect.service_manager import ServiceManager
from lsl_connect.state import ServiceState

HELP_TEXT = """
命令:
  help              显示本帮助
  status            服务 / 采集状态
  start             启动采集 + LSL（仅 IDLE）
  stop              停止采集（RUNNING / ERROR）
  reset             ERROR 恢复为 IDLE
  config port COMx  设置串口（仅 IDLE）
  config filter on|off  开关滤波（仅 RUNNING）
  gui hint          OpenBCI GUI / LSL 连接提示
  quit / exit       退出（会先 stop）
""".strip()

GUI_HINT_TEXT = """
[GUI / LSL 提示]
1. 先在本面板输入 start，等到 status 显示 RUNNING
2. 本脚本已占用串口，OpenBCI GUI 不要再选 Serial/Cyton 直连
3. 订阅本机 LSL 流（任选其一）:
   - OpenBCI GUI: Networking → LSL → 选择 OpenBCI_EEG
   - LabRecorder: 添加 OpenBCI_EEG / OpenBCI_Accel
4. 流名: OpenBCI_EEG (8ch, 250Hz, µV)
   加速度: OpenBCI_Accel
5. 若 GUI 无 LSL 入口，可用 LabRecorder 录 .xdf 或用自写 Inlet 脚本查看
""".strip()

class ControlPanel:
    """交互式控制面板。"""

    def __init__(self,manager: ServiceManager)->None:
        self._mgr = manager
        self._alive=True

    def run(self)->None:
        print("=" * 50)
        print("OpenBCI EEG 控制面板 — 第 8 课")
        print("输入 help 查看命令")
        print("=" * 50)

        while self._alive:
            try:
                line =input(">").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                self._cmd_quit([])
                break

            if not line:
                continue
            self.dispath(line)

    def dispath(self,line:str)->None:
        parts = line.split()
        cmd = parts[0].lower()
        args=parts[1:]

        handlers ={
            "help": self._cmd_help,
            "?": self._cmd_help,
            "status": self._cmd_status,
            "start": self._cmd_start,
            "stop": self._cmd_stop,
            "reset": self._cmd_reset,
            "config": self._cmd_config,
            "gui": self._cmd_gui,
            "quit": self._cmd_quit,
            "exit": self._cmd_quit,
        }

        #输入命令对应取出方法
        handler = handlers.get(cmd)
        if handler is None:
           print(f"未知命令：{cmd}，输入help")
           return
        handler(args)

    def _cmd_help(self,_args: list[str])->None:
        print(HELP_TEXT)

    def _cmd_status(self,_args: list[str])->None:
        print(self._mgr.format_status())
        st=self._mgr.get_status()
        if st["state"] == ServiceState.RUNNING.value:
            print ("[LSL] OpenBCI_EEG (Outlet 活跃) | OpenBCI_Accel (ON)")

    def _cmd_start(self,_args: list[str])->None:
        if self._mgr.get_state() == ServiceState.ERROR:
            print("当前 ERROR，请先 reset 或 stop")
            return

        if self._mgr.start_acquisition():
            print("[OK] 采集已启动 → RUNNING")
            print("可输入 status 查看；gui hint 查看 GUI 连接说明")

        else:
            print(f"[失败] 无法 start（当前 {self._mgr.get_state().value}）")
            err = self._mgr.get_status().get("last_error")
            if err:
                print(f"  原因: {err}")

    def _cmd_stop(self,_args: list[str])->None:
        if self._mgr.stop_acquisition():
            print("[OK] 采集已停止 → IDLE")
        else:
            print(f"[失败] 无法 stop（当前 {self._mgr.get_state().value}）")

    def _cmd_reset(self, _args: list[str]) -> None:
        if self._mgr.reset():
            print("[OK] 已 reset → IDLE")
        else:
            print(f"[失败] 无法 reset（当前 {self._mgr.get_state().value}）")

    def _cmd_config(self,args: list[str]) -> None:
        if len(args) < 2:
            print("用法: config port COM10  或  config filter on|off")
            return

        sub =args[0].lower()
        value=args[1]

        if sub == "port":
            ok,msg=self._mgr.set_serial_port(value)
            print(f"{'[OK]' if ok else '[失败]'}{msg}")
        elif sub == "filter":
            v=value.lower()
            if v in("on","1","true"):
               ok,msg=self._mgr.set_filter_enabled(True)
            elif v in("off","0","false"):
                ok,msg=self._mgr.set_filter_enabled(False)

            else:
                print("用法：config filter on|off")
                return
            print(f"{'[OK]' if ok else '[失败]'} {msg}")
        else:
            print("未知 config 子命令，支持：port，filter")

    def _cmd_gui(self,args: list[str]) -> None:
        if args and args[0].lower() !="hint":
            print("用法： gui hint")
            return
        print(GUI_HINT_TEXT)

    def _cmd_quit(self,args: list[str]) -> None:
        print("正在退出...")
        self._mgr.shutdown()
        self._alive=False
        print("再见。")

    