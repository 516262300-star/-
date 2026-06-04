from __future__ import annotations

import queue
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import END, LEFT, RIGHT, BOTH, X, Y, BooleanVar, StringVar, Tk, Text, messagebox
from tkinter import ttk


PROJECT_DIR = Path(__file__).resolve().parent
PYTHON_EXE = Path(r"C:\Users\lds\AppData\Local\Programs\Python\Python312\python.exe")
SHANGHAI_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


class PddSyncApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("拼多多广告数据同步")
        self.root.geometry("900x620")
        self.root.minsize(760, 520)

        self.output_queue: queue.Queue[str] = queue.Queue()
        self.process: subprocess.Popen | None = None

        self.date_var = StringVar(value=self._yesterday())
        self.range_start_var = StringVar(value=self._yesterday())
        self.range_end_var = StringVar(value=self._yesterday())
        self.store_var = StringVar(value="all")
        self.dry_run_var = BooleanVar(value=False)

        self._build_ui()
        self.root.after(150, self._drain_output_queue)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=14)
        container.pack(fill=BOTH, expand=True)

        title = ttk.Label(container, text="拼多多广告数据同步", font=("Microsoft YaHei UI", 16, "bold"))
        title.pack(anchor="w")

        subtitle = ttk.Label(
            container,
            text="默认同步一到七店。ERP 登录过期时，点“重新登录并同步”后按弹窗提示扫码/短信登录。",
        )
        subtitle.pack(anchor="w", pady=(4, 12))

        form = ttk.Frame(container)
        form.pack(fill=X, pady=(0, 10))

        ttk.Label(form, text="单日日期").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(form, textvariable=self.date_var, width=18).grid(row=0, column=1, sticky="w", pady=4)
        ttk.Label(form, text="店铺").grid(row=0, column=2, sticky="w", padx=(20, 8), pady=4)
        ttk.Combobox(
            form,
            textvariable=self.store_var,
            width=18,
            values=["all", "22", "222", "223", "224", "225", "226", "227"],
        ).grid(row=0, column=3, sticky="w", pady=4)
        ttk.Checkbutton(form, text="只检查，不写入 Notion", variable=self.dry_run_var).grid(
            row=0, column=4, sticky="w", padx=(20, 0), pady=4
        )

        ttk.Label(form, text="范围开始").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(form, textvariable=self.range_start_var, width=18).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(form, text="范围结束").grid(row=1, column=2, sticky="w", padx=(20, 8), pady=4)
        ttk.Entry(form, textvariable=self.range_end_var, width=18).grid(row=1, column=3, sticky="w", pady=4)

        buttons = ttk.Frame(container)
        buttons.pack(fill=X, pady=(0, 10))

        ttk.Button(buttons, text="同步昨天", command=self.sync_yesterday).pack(side=LEFT, padx=(0, 8))
        ttk.Button(buttons, text="同步单日", command=self.sync_single_date).pack(side=LEFT, padx=(0, 8))
        ttk.Button(buttons, text="同步日期范围", command=self.sync_range).pack(side=LEFT, padx=(0, 8))
        ttk.Button(buttons, text="重新登录并同步", command=self.relogin_and_sync).pack(side=LEFT, padx=(0, 8))
        ttk.Button(buttons, text="打开日志文件夹", command=self.open_logs).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(buttons, text="停止当前运行", command=self.stop_process).pack(side=RIGHT)

        self.status_var = StringVar(value="空闲")
        ttk.Label(container, textvariable=self.status_var).pack(anchor="w", pady=(0, 6))

        output_frame = ttk.Frame(container)
        output_frame.pack(fill=BOTH, expand=True)
        scrollbar = ttk.Scrollbar(output_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.output = Text(output_frame, wrap="word", yscrollcommand=scrollbar.set)
        self.output.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.config(command=self.output.yview)

    def _yesterday(self) -> str:
        return (datetime.now(SHANGHAI_TZ).date() - timedelta(days=1)).isoformat()

    def _base_args(self) -> list[str]:
        args = [str(PYTHON_EXE), str(PROJECT_DIR / "main.py"), "--store", self.store_var.get().strip() or "all"]
        if self.dry_run_var.get():
            args.append("--dry-run")
        return args

    def _run_in_app(self, args: list[str]) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showwarning("正在运行", "当前已有一个同步任务在运行，请先等待或停止。")
            return

        self.output.delete("1.0", END)
        self._append_output("> " + " ".join(args) + "\n\n")
        self.status_var.set("运行中")

        thread = threading.Thread(target=self._worker, args=(args,), daemon=True)
        thread.start()

    def _worker(self, args: list[str]) -> None:
        try:
            self.process = subprocess.Popen(
                args,
                cwd=PROJECT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.output_queue.put(line)
            return_code = self.process.wait()
            self.output_queue.put(f"\n运行结束，退出码：{return_code}\n")
            self.output_queue.put("__STATUS_DONE__" if return_code == 0 else "__STATUS_FAILED__")
        except Exception as exc:
            self.output_queue.put(f"\n运行失败：{exc}\n")
            self.output_queue.put("__STATUS_FAILED__")

    def _drain_output_queue(self) -> None:
        while True:
            try:
                item = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if item == "__STATUS_DONE__":
                self.status_var.set("完成")
            elif item == "__STATUS_FAILED__":
                self.status_var.set("失败")
            else:
                self._append_output(item)
        self.root.after(150, self._drain_output_queue)

    def _append_output(self, text: str) -> None:
        self.output.insert(END, text)
        self.output.see(END)

    def sync_yesterday(self) -> None:
        yesterday = self._yesterday()
        self.date_var.set(yesterday)
        args = self._base_args() + ["--date", yesterday]
        self._run_in_app(args)

    def sync_single_date(self) -> None:
        date_text = self.date_var.get().strip()
        if not date_text:
            messagebox.showwarning("缺少日期", "请填写日期，例如 2026-06-03。")
            return
        args = self._base_args() + ["--date", date_text]
        self._run_in_app(args)

    def sync_range(self) -> None:
        start = self.range_start_var.get().strip()
        end = self.range_end_var.get().strip()
        if not start or not end:
            messagebox.showwarning("缺少日期范围", "请填写开始和结束日期。")
            return
        args = self._base_args() + ["--range", f"{start}~{end}"]
        self._run_in_app(args)

    def relogin_and_sync(self) -> None:
        date_text = self.date_var.get().strip() or self._yesterday()
        store_text = self.store_var.get().strip() or "all"
        command = (
            f"Set-Location '{PROJECT_DIR}'; "
            f"& '{PYTHON_EXE}' main.py --date {date_text} --store {store_text} --relogin; "
            "Read-Host '运行结束，按回车关闭窗口'"
        )
        subprocess.Popen(
            ["powershell.exe", "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=PROJECT_DIR,
        )
        self._append_output(f"已打开重新登录窗口，请在浏览器登录 ERP 后回到新窗口按回车。\n日期：{date_text}，店铺：{store_text}\n")

    def open_logs(self) -> None:
        (PROJECT_DIR / "debug").mkdir(exist_ok=True)
        subprocess.Popen(["explorer.exe", str(PROJECT_DIR / "debug")])

    def stop_process(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.status_var.set("已请求停止")
            self._append_output("\n已请求停止当前运行。\n")
        else:
            self.status_var.set("空闲")


def main() -> None:
    root = Tk()
    app = PddSyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
