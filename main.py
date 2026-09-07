# -*- coding: utf-8 -*-
"""
学生积分管理程序
- 每个学生一个 json 文件,文件名为学号(如 2026001.json)
- 文件内容为标准 JSON:{"score": 得分, "records": [{"op": "add/less", "points": 分值, "date": "日期"}, ...]}
- 启动时自动 git pull 更新数据;每次修改后自动 git add/commit/push
"""

import json
import os
import subprocess
import sys
from datetime import date

if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(os.path.abspath(sys.executable))
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))


def setup_stdio():
    """输出被重定向(管道/文件)时用 UTF-8 并容错,避免 ✓ 等字符在 GBK 下崩溃;
    正常控制台窗口不受影响"""
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None and not stream.isatty():
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


setup_stdio()
STUDENT_COUNT = 35
TOTAL_STUDENTS = 32
STUDENT_IDS = ["2026%03d" % i for i in range(1, STUDENT_COUNT + 1)]
DATA_FILE = os.path.join(ROOT, "%s.json")

RECORD_FIELDS = ("op", "points", "date")
VALID_OPS = ("add", "less", "cancle")

HELP_TEXT = """\
====================== 学生积分管理 ======================
主菜单可用操作(输入未知操作时也会显示本帮助):

  help                        查看所有操作及使用方法
  control                     对学生进行操作(进入后先询问操作)
  rank                        查看积分排行榜(按得分从高到低)
  score <学号>                查看某位学生的得分与最近记录
  add <学号> <分值>           给某位学生加分(如: add 2026001 2)
  less <学号> <分值>          给某位学生减分(如: less 2026001 1)
  cancle <学号>               撤销该学生上一次的扣分
  exit                        退出程序

control 模式下的操作(进入后先询问):

  add <分值>      加分   (如: add 2)
  less <分值>     减分   (如: less 1)
  cancle          撤销上一次扣分
  help            在 control 中查看说明
  exit            返回主菜单

使用说明:
  1. 学号可带或不带 .json 后缀;共 %d 人,程序先创建了 %d 个占位学号
     文件(2026001~20260%d),后续可直接把文件名改成真实学号。
  2. 每次 add/less 都要输入分值(正整数),记录里会自动保存当天的日期。
  3. cancle 只撤销"最近一次扣分",且只允许撤销"本周"的扣分;
     若该学生本周内没有扣分记录,则无操作;上一周及更早的扣分无法撤销。
  4. 数据文件结构(标准 JSON):
       {"score": 100, "records": [{"op": "add", "points": 2, "date": "2026-09-07"}]}
  5. 每次启动会先执行 git pull 同步最新数据;每次修改后会自动提交并推送。
=========================================================
""" % (TOTAL_STUDENTS, STUDENT_COUNT, STUDENT_COUNT)


# ------------------------- 工具函数 -------------------------

def today_str():
    return date.today().isoformat()


def iso_week(d):
    """返回日期的 ISO 年-周,如 (2026, 37)"""
    c = d.isocalendar()
    return (c[0], c[1])


def is_current_week(d):
    return iso_week(d) == iso_week(date.today())


def norm_sid(sid):
    sid = sid.strip().strip('"').strip("'")
    if sid.lower().endswith(".json"):
        sid = sid[:-5]
    return sid.strip()


def data_path(sid):
    return DATA_FILE % sid


def student_exists(sid):
    return os.path.isfile(data_path(sid))


def load_student(sid):
    """返回 (score, records);文件缺失返回 (None, None)"""
    p = data_path(sid)
    if not os.path.isfile(p):
        return None, None
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print("! 读取 %s 失败: %s" % (os.path.basename(p), e))
        return None, None
    if not isinstance(data, dict):
        return None, None
    score = data.get("score", 0)
    records = data.get("records", [])
    return (score if isinstance(score, int) else 0,
            records if isinstance(records, list) else [])


def save_student(sid, score, records):
    data = {"score": score, "records": records}
    with open(data_path(sid), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ask_int(prompt, minimum=1, maximum=10000):
    while True:
        raw = input(prompt).strip()
        try:
            n = int(raw)
        except ValueError:
            print("! 请输入正整数")
            continue
        if minimum <= n <= maximum:
            return n
        print("! 分值需在 %d ~ %d 之间" % (minimum, maximum))


def ask_student(prompt="请输入学号: "):
    while True:
        sid = norm_sid(input(prompt))
        if not sid:
            continue
        if not student_exists(sid):
            print("! 无此学生(%s),请核对学号" % sid)
            continue
        return sid


def describe_op(op):
    return {"add": "加分", "less": "扣分"}.get(op, op)


# ------------------------- 核心操作 -------------------------

def do_add(sid, points):
    score, records = load_student(sid)
    records.append({"op": "add", "points": points, "date": today_str()})
    score += points
    save_student(sid, score, records)
    print("✓ 学生 %s 加分 %d,当前得分: %d" % (sid, points, score))
    git_commit_push("add %d分 %s %s" % (points, sid, today_str()), sid)
    return True


def do_less(sid, points):
    score, records = load_student(sid)
    records.append({"op": "less", "points": points, "date": today_str()})
    score -= points
    save_student(sid, score, records)
    print("✓ 学生 %s 扣分 %d,当前得分: %d" % (sid, points, score))
    git_commit_push("less %d分 %s %s" % (points, sid, today_str()), sid)
    return True


def do_cancle(sid):
    """撤销该学生最近一次扣分;仅限本周内,无则无操作"""
    score, records = load_student(sid)
    for i in range(len(records) - 1, -1, -1):
        rec = records[i]
        if not isinstance(rec, dict) or rec.get("op") != "less":
            continue
        try:
            d = date.fromisoformat(str(rec["date"]))
        except (ValueError, KeyError):
            continue
        if not is_current_week(d):
            print("× 学生 %s 最近一次扣分发生在 %s(本周之前),无法撤销" % (sid, rec["date"]))
            return False
        back = int(rec.get("points", 0))
        del records[i]
        score += back
        save_student(sid, score, records)
        print("✓ 已撤销学生 %s 于 %s 的扣分 %d,当前得分: %d"
              % (sid, rec["date"], back, score))
        git_commit_push("cancle %d分 %s %s" % (back, sid, today_str()), sid)
        return True
    print("× 学生 %s 没有可撤销的扣分记录(本周内无扣分),无操作" % sid)
    return False


# ------------------------- git 同步 -------------------------

def run_git(*args):
    try:
        r = subprocess.run(["git", *args], cwd=ROOT,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except FileNotFoundError:
        return -1, "", "未找到 git 命令"
    except Exception as e:
        return -1, "", str(e)


def git_repo_ready():
    return os.path.isdir(os.path.join(ROOT, ".git"))


def has_origin():
    code, out, _ = run_git("remote")
    return code == 0 and bool(out.strip())


def ensure_git_identity():
    """仓库没有设置 user 时自动设置(仅本仓库生效),保证能提交"""
    code, name, _ = run_git("config", "user.name")
    if code != 0 or not name:
        run_git("config", "user.name", "ScoreBot")
    code, email, _ = run_git("config", "user.email")
    if code != 0 or not email:
        run_git("config", "user.email", "scorebot@local")


def git_status_is_clean():
    code, out, _ = run_git("status", "--porcelain")
    return code == 0 and not out


def read_remote_url_file():
    """安装器/用户可通过 remote_url.txt 提供远程仓库地址"""
    p = os.path.join(ROOT, "remote_url.txt")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def git_commit_failed_noop(err_text):
    """git commit 常见的\"没有可提交内容\"提示不算错误"""
    return ("nothing to commit" in err_text) or ("nothing added to commit" in err_text)


def git_pull_on_startup():
    """确保本地仓库存在 -> 提交本地改动 -> 配置远程 -> 启动时拉取最新数据"""
    if not git_repo_ready():
        print("…首次运行,正在创建本地 git 仓库...")
        code, out, err = run_git("init", "-b", "main")
        if code != 0:
            print("! git init 失败: %s" % (err or out))
            return
        ensure_git_identity()
        run_git("add", "-A")
        code, out, err = run_git("commit", "-m", "初始化本地仓库")
        if code != 0 and not git_commit_failed_noop(err or out):
            print("! 初始化提交失败: %s" % (err or out))
    ensure_git_identity()
    if not git_status_is_clean():
        code, out, err = run_git("commit", "-am", "同步前自动提交")
        if code != 0 and not git_commit_failed_noop(err or out):
            print("! 启动前自动提交失败:\n%s" % (err or out))
    if not has_origin():
        url = read_remote_url_file()
        if url:
            code, out, err = run_git("remote", "add", "origin", url)
            if code == 0:
                print("✓ 已从 remote_url.txt 配置远程仓库: %s" % url)
            else:
                print("! 配置远程仓库失败: %s" % (err or out))
    if not has_origin():
        print("! 未配置远程仓库,跳过 git pull")
        print("  如需多台电脑同步数据,请先执行:\n"
              "    git -C \"%s\" remote add origin <你的远程仓库地址>" % ROOT)
        return
    print("…正在同步远程数据 (git pull)...")
    code, out, err = run_git("pull", "--no-edit")
    if code == 0:
        print("✓ 数据已同步: %s" % (out or "无更新"))
    else:
        print("! git pull 失败: %s" % (err or out))
        print("  请检查网络/仓库权限,或手动解决冲突后重新启动。")


def git_commit_push(msg, sid=None):
    """每次修改后自动提交并推送;推送失败时先 pull 再重试一次。
    指定 sid 时只提交该学生文件,避免把无关改动一起提交。"""
    if not git_repo_ready():
        return
    ensure_git_identity()
    if sid:
        code, out, err = run_git("add", "--", data_path(sid))
    else:
        code, out, err = run_git("add", "-A")
    if code != 0:
        print("! git add 失败: %s" % (err or out))
        return
    code, out, err = run_git("commit", "-m", msg)
    if code != 0 and not git_commit_failed_noop(err or out):
        print("! git commit 失败: %s" % (err or out))
        return
    if not has_origin():
        print("(改动已保存在本地仓库,未配置远程仓库故未推送)")
        return
    code, out, err = run_git("push")
    if code == 0:
        return
    if "rejected" in (err or out):
        print("! 推送被拒绝,正在先拉取远程改动再重试...")
        run_git("pull", "--no-edit")
        code, out, err = run_git("push")
        if code == 0:
            return
    print("! 推送失败(改动已保存在本地): %s" % (err or out))


# ------------------------- 界面 -------------------------

def print_help():
    print(HELP_TEXT)


def cmd_show(sid):
    sid = norm_sid(sid)
    if not student_exists(sid):
        print("! 无此学生(%s)" % sid)
        return
    score, records = load_student(sid)
    print("学生 %s  当前得分: %d" % (sid, score))
    if not records:
        print("  暂无任何加减分记录")
        return
    print("  最近记录:")
    for rec in records[-8:]:
        op = rec.get("op")
        sign = "+" if op == "add" else "-"
        print("    %s  %s%d分  %s" % (rec.get("date"), sign,
                                      int(rec.get("points", 0)),
                                      describe_op(op)))


def cmd_rank():
    rows = []
    for sid in STUDENT_IDS:
        score, _ = load_student(sid)
        if score is None:
            continue
        rows.append((score, sid))
    rows.sort(key=lambda x: (-x[0], x[1]))
    print("======== 积分排行榜 ========")
    for i, (score, sid) in enumerate(rows, 1):
        print("%2d. %s   %d 分" % (i, sid, score))
    print("============================")


def cmd_control():
    """进入学生管理模式:先询问做什么操作"""
    print("已进入学生管理模式,先选择操作:")
    print("  add <分值> 加分 | less <分值> 扣分 | cancle 撤销上次扣分 | help | exit 返回")
    while True:
        raw = input("control> ").strip().lower()
        if raw in ("exit", "quit", "q", "返回"):
            return
        parts = raw.split()
        op = parts[0] if parts else ""
        if op in ("add", "less"):
            sid = ask_student()
            if len(parts) >= 2:
                try:
                    points = int(parts[1])
                except ValueError:
                    points = ask_int("请输入 %s 分值: " % describe_op(op))
            else:
                points = ask_int("请输入 %s 分值: " % describe_op(op))
            if points <= 0:
                print("! 分值必须为正整数")
                continue
            if op == "add":
                do_add(sid, points)
            else:
                do_less(sid, points)
        elif op == "cancle":
            sid = ask_student()
            do_cancle(sid)
        elif op == "help":
            print("  control 中可用: add <分值> / less <分值> / cancle / exit")
        else:
            print("! 未知操作,请使用 add / less / cancle(或 exit 返回主菜单)")


def cmd_add(sid, points):
    sid = norm_sid(sid)
    if not student_exists(sid):
        print("! 无此学生(%s),可用 help 查看用法" % sid)
        return
    do_add(sid, points)


def cmd_less(sid, points):
    sid = norm_sid(sid)
    if not student_exists(sid):
        print("! 无此学生(%s),可用 help 查看用法" % sid)
        return
    do_less(sid, points)


def cmd_cancle(sid):
    sid = norm_sid(sid)
    if not student_exists(sid):
        print("! 无此学生(%s),可用 help 查看用法" % sid)
        return
    do_cancle(sid)


def create_student_files():
    """初始化:为每个学号创建 json 文件(已存在则跳过)"""
    created = 0
    for sid in STUDENT_IDS:
        p = data_path(sid)
        if not os.path.isfile(p):
            save_student(sid, 0, [])
            created += 1
    return created


def main():
    print("==================== 学生积分管理 ====================")
    print("可用操作: help | control | add | less | cancle | rank | score | exit")
    print("输入 help 查看所有操作及使用方法;输入 exit 退出\n")

    git_pull_on_startup()

    n = create_student_files()
    if n:
        print("已初始化 %d 名学生的数据文件(占位学号 2026001~20260%d)"
              % (n, STUDENT_COUNT))
        if git_repo_ready():
            git_commit_push("初始化缺失的学生数据文件")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见")
            return
        if not raw:
            continue
        parts = raw.split()
        cmd = parts[0].lower()

        if cmd in ("help", "h", "?", "menu"):
            print_help()
        elif cmd == "control":
            cmd_control()
        elif cmd == "rank":
            cmd_rank()
        elif cmd == "score" and len(parts) >= 2:
            cmd_show(parts[1])
        elif cmd == "add" and len(parts) >= 3:
            try:
                cmd_add(parts[1], int(parts[2]))
            except ValueError:
                print("! 用法: add <学号> <正整数分值>")
        elif cmd == "less" and len(parts) >= 3:
            try:
                cmd_less(parts[1], int(parts[2]))
            except ValueError:
                print("! 用法: less <学号> <正整数分值>")
        elif cmd == "cancle" and len(parts) >= 2:
            cmd_cancle(parts[1])
        elif cmd in ("exit", "quit", "q", "bye"):
            print("再见")
            return
        else:
            print("! 未知操作: %s\n" % raw)
            print_help()


if __name__ == "__main__":
    try:
        os.makedirs(ROOT, exist_ok=True)
        main()
    except KeyboardInterrupt:
        print("\n再见")
