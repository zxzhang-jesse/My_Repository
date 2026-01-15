import tkinter as tk
from tkinter import messagebox
import random
import math
import sys

# ---------------------------
# 配置区：可调参数
# ---------------------------
INITIAL_COINS = 5
PLAYERS = ["Vincent", "Eric", "Tony", "Bright"]
NUM_QUESTIONS = 20

# 难度对应的答题时间（秒）
DIFFICULTY_TO_TIME = {1: 15, 2: 30, 3: 45, 4: 60}

# 题库示例（20道）。请按需替换为真实题目（或从文件读取）
SAMPLE_QUESTIONS = [
    {"text": f"示例题目 #{i+1}", "difficulty": random.randint(1, 4)}
    for i in range(NUM_QUESTIONS)
]

# 下注阶段持续时间（秒）
BETTING_SECONDS = 20

# 视觉 / 字体 配置
FONT_FAMILY = "Times New Roman"
FONT_TITLE = (FONT_FAMILY, 28, "bold")
FONT_NAME = (FONT_FAMILY, 26, "bold")
FONT_COINS = (FONT_FAMILY, 30, "bold")
FONT_NORMAL = (FONT_FAMILY, 20)
FONT_SMALL = (FONT_FAMILY, 16)

BG_COLOR = "black"
FG_COLOR = "white"
BTN_BG = "gray20"
BTN_ACTIVE_BG = "gray30"

# ---------------------------
# 游戏逻辑类
# ---------------------------
class Player:
    def __init__(self, name, coins):
        self.name = name
        self.coins = coins
        self.will_answer = False
        self.will_double = False
        self.invested = 0

class QuizGame:
    def __init__(self, master):
        self.master = master
        master.title("物理课堂答题小游戏")
        # 全屏并设置背景
        master.attributes("-fullscreen", True)
        master.configure(bg=BG_COLOR)
        master.bind("<Escape>", lambda e: master.attributes("-fullscreen", False))

        # 初始化声音函数（优先 winsound，在非 Windows 时退回 bell）
        try:
            import winsound
            self._winsound = winsound
            self.beep = lambda freq=1000, dur=150: self._winsound.Beep(freq, dur)
        except Exception:
            self._winsound = None
            self.beep = lambda freq=1000, dur=150: master.bell()

        self.players = {name: Player(name, INITIAL_COINS) for name in PLAYERS}
        self.questions = SAMPLE_QUESTIONS.copy()
        random.shuffle(self.questions)
        self.current_q_idx = -1
        self.asked_count = 0
        self.current_question = None

        # 倒计时控制（下注与题目各自独立）
        self.bet_seconds_left = 0
        self.bet_timer_id = None
        self.question_seconds_left = 0
        self.question_timer_id = None

        # UI 构建
        self.build_ui()

        self.update_player_labels()
        self.log("游戏就绪。初始硬币：每人 %d。" % INITIAL_COINS)

    def build_ui(self):
        # 顶部玩家区
        self.top_frame = tk.Frame(self.master, bg=BG_COLOR)
        self.top_frame.pack(padx=12, pady=12, anchor="n")

        self.player_frames = {}
        self.player_name_labels = {}
        self.player_coin_labels = {}
        self.answer_vars = {}
        self.double_vars = {}

        for i, name in enumerate(PLAYERS):
            frame = tk.Frame(self.top_frame, relief=tk.RIDGE, bd=2, padx=12, pady=12, bg=BG_COLOR)
            frame.grid(row=0, column=i, padx=12)

            lbl_name = tk.Label(frame, text=name, font=FONT_NAME, bg=BG_COLOR, fg=FG_COLOR)
            lbl_name.pack()
            lbl_coins = tk.Label(frame, text=f"{INITIAL_COINS}", font=FONT_COINS, bg=BG_COLOR, fg=FG_COLOR)
            lbl_coins.pack(pady=(8,0))

            ans_var = tk.IntVar(value=0)
            dbl_var = tk.IntVar(value=0)
            chk_ans = tk.Checkbutton(frame, text="回答", variable=ans_var, font=FONT_SMALL,
                                     bg=BG_COLOR, fg=FG_COLOR, selectcolor=BG_COLOR,
                                     activebackground=BG_COLOR, activeforeground=FG_COLOR)
            chk_dbl = tk.Checkbutton(frame, text="加倍", variable=dbl_var, font=FONT_SMALL,
                                     bg=BG_COLOR, fg=FG_COLOR, selectcolor=BG_COLOR,
                                     activebackground=BG_COLOR, activeforeground=FG_COLOR)
            chk_ans.pack()
            chk_dbl.pack()

            self.player_frames[name] = frame
            self.player_name_labels[name] = lbl_name
            self.player_coin_labels[name] = lbl_coins
            self.answer_vars[name] = ans_var
            self.double_vars[name] = dbl_var

        # 问题显示区
        self.q_frame = tk.Frame(self.master, bg=BG_COLOR, pady=10)
        self.q_frame.pack(fill=tk.X, padx=12)

        # 注意：题目文本在抽题后默认隐藏，在下注阶段不显示题目
        self.q_label = tk.Label(self.q_frame, text="点击“抽取题目”开始", wraplength=1200, justify=tk.LEFT,
                                font=FONT_TITLE, bg=BG_COLOR, fg=FG_COLOR)
        self.q_label.pack(anchor="w")

        self.q_info_label = tk.Label(self.q_frame, text="", font=FONT_NORMAL, bg=BG_COLOR, fg=FG_COLOR)
        self.q_info_label.pack(anchor="w")

        # 倒计时显示（用于显示下注倒计时或题目答题倒计时）
        self.timer_label = tk.Label(self.q_frame, text="", font=(FONT_FAMILY, 40, "bold"),
                                    bg=BG_COLOR, fg=FG_COLOR)
        self.timer_label.pack(anchor="w", pady=(6,0))

        # 控制按钮
        self.controls = tk.Frame(self.master, pady=12, bg=BG_COLOR)
        self.controls.pack()

        self.draw_btn = tk.Button(self.controls, text="抽取题目", font=FONT_NORMAL, bg=BTN_BG, fg=FG_COLOR,
                                  activebackground=BTN_ACTIVE_BG, command=self.draw_question, width=14)
        self.draw_btn.grid(row=0, column=0, padx=10)

        self.confirm_btn = tk.Button(self.controls, text="确认回答选择（投入）", font=FONT_NORMAL, bg=BTN_BG, fg=FG_COLOR,
                                     activebackground=BTN_ACTIVE_BG, state=tk.DISABLED, command=lambda: self.confirm_answers(reveal_question=True, auto=False), width=20)
        self.confirm_btn.grid(row=0, column=1, padx=10)

        self.judge_btn = tk.Button(self.controls, text="判定正确/错误", font=FONT_NORMAL, bg=BTN_BG, fg=FG_COLOR,
                                   activebackground=BTN_ACTIVE_BG, state=tk.DISABLED, command=self.judge_answers, width=14)
        self.judge_btn.grid(row=0, column=2, padx=10)

        self.next_btn = tk.Button(self.controls, text="下一题", font=FONT_NORMAL, bg=BTN_BG, fg=FG_COLOR,
                                  activebackground=BTN_ACTIVE_BG, state=tk.DISABLED, command=self.next_question, width=14)
        self.next_btn.grid(row=0, column=3, padx=10)

        # 日志区
        self.log_text = tk.Text(self.master, width=120, height=12, state=tk.DISABLED,
                                bg=BG_COLOR, fg=FG_COLOR, font=FONT_SMALL)
        self.log_text.pack(padx=12, pady=12)

    # ---------- UI 辅助 ----------
    def log(self, msg):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def update_player_labels(self):
        for name, p in self.players.items():
            lbl = self.player_coin_labels[name]
            lbl.config(text=str(p.coins))
            if p.coins < 0:
                lbl.config(fg="red")
            else:
                lbl.config(fg=FG_COLOR)

    # ---------- 抽题 / 下注阶段 ----------
    def draw_question(self):
        if self.asked_count >= NUM_QUESTIONS:
            messagebox.showinfo("提示", "所有题目已结束。")
            return

        # 取消任何残留的题目计时器
        if self.question_timer_id:
            self.master.after_cancel(self.question_timer_id)
            self.question_timer_id = None

        self.current_q_idx += 1
        self.current_question = self.questions[self.current_q_idx]
        self.asked_count += 1

        # 在抽题时不显示题目，进入下注阶段
        self.q_label.config(text=f"第 {self.asked_count} 题：题目已隐藏，进入下注阶段（{BETTING_SECONDS} 秒）")
        self.q_info_label.config(text="请在倒计时内选择 是否回答 / 是否加倍 。")
        self.log(f"抽题（题目暂时隐藏） — 本题将保留直到下注锁定后显示。")
        # 启用确认按钮（下注用），禁用抽题
        self.confirm_btn.config(state=tk.NORMAL)
        self.draw_btn.config(state=tk.DISABLED)
        self.judge_btn.config(state=tk.DISABLED)
        self.next_btn.config(state=tk.DISABLED)

        # 重置选择框与临时状态
        for name in self.players:
            self.answer_vars[name].set(0)
            self.double_vars[name].set(0)
            self.players[name].will_answer = False
            self.players[name].will_double = False
            self.players[name].invested = 0

        # 启动下注计时器
        self.start_betting_timer(BETTING_SECONDS)

    def start_betting_timer(self, seconds):
        self.bet_seconds_left = seconds
        # 立即显示一次
        self.update_betting_timer_display()
        # 开始 tick
        self._tick_betting_timer()

    def _tick_betting_timer(self):
        # 最后五秒给短促提示
        if self.bet_seconds_left <= 5 and self.bet_seconds_left > 0:
            try:
                self.beep(1000, 80)
            except:
                pass

        if self.bet_seconds_left <= 0:
            self.timer_label.config(text="下注锁定，题目显示中...")
            try:
                self.beep(800, 300)
            except:
                pass
            self.bet_timer_id = None
            # 自动锁定下注并显示题目（如果还未手动确认）
            self.confirm_answers(reveal_question=True, auto=True)
            return
        else:
            self.update_betting_timer_display()
            self.bet_seconds_left -= 1
            self.bet_timer_id = self.master.after(1000, self._tick_betting_timer)

    def update_betting_timer_display(self):
        sec = self.bet_seconds_left
        mins = sec // 60
        s = sec % 60
        self.timer_label.config(text=f"下注倒计时：{mins:02d}:{s:02d}")

    # ---------- 确认下注（可能来自手动或下注倒计时到） ----------
    def confirm_answers(self, reveal_question=False, auto=False):
        # 如果有下注计时器在运行，取消它（因为下注要被锁定）
        if self.bet_timer_id:
            try:
                self.master.after_cancel(self.bet_timer_id)
            except:
                pass
            self.bet_timer_id = None

        q = self.current_question
        diff = q['difficulty']

        any_answer = False
        for name, p in self.players.items():
            p.will_answer = bool(self.answer_vars[name].get())
            p.will_double = bool(self.double_vars[name].get())
            p.invested = 0

        # 新逻辑：允许贷款（即不再强制余额检查），直接扣除所需硬币
        for name, p in self.players.items():
            if p.will_answer:
                stake = diff
                double_stake = diff if p.will_double else 0
                total_needed = stake + double_stake
                p.coins -= total_needed  # 允许负数（贷款）
                p.invested = total_needed
                any_answer = True
                if p.coins < 0:
                    loan_amount = abs(p.coins)
                    self.log(f"{name} 使用贷款 {loan_amount} 硬币进行作答（投入 {total_needed}）。")
                else:
                    self.log(f"{name} 投入了 {total_needed}（难度 {diff}{'，加倍' if p.will_double else ''}）。")
            else:
                p.will_double = False
                p.invested = 0

        if not any_answer:
            self.log("本题无人作答。")
        else:
            if auto:
                self.log("系统已自动锁定下注（下注阶段倒计时结束）。")
            else:
                self.log("已手动锁定下注。")

        self.update_player_labels()
        # 锁定下注按钮
        self.confirm_btn.config(state=tk.DISABLED)
        # 启用判定按钮（等待老师判定）
        self.judge_btn.config(state=tk.NORMAL)

        # 如果需要展示题目并进入题目倒计时（通常在下注锁定后），进行题目显示与计时
        if reveal_question:
            # 显示题目与难度信息
            qtext = q['text']
            self.q_label.config(text=f"第 {self.asked_count} 题：{qtext}")
            t = DIFFICULTY_TO_TIME.get(diff, 20)
            self.q_info_label.config(text=f"难度：{diff}    建议答题时间：{t} 秒")
            # 开始题目倒计时
            self.start_question_timer(t)

    # ---------- 题目计时 ----------
    def start_question_timer(self, seconds):
        # 取消任何残留题目计时器
        if self.question_timer_id:
            try:
                self.master.after_cancel(self.question_timer_id)
            except:
                pass
            self.question_timer_id = None

        self.question_seconds_left = seconds
        self.update_question_timer_display()
        self._tick_question_timer()

    def _tick_question_timer(self):
        # 在最后 5s 给短促提示
        if self.question_seconds_left <= 5 and self.question_seconds_left > 0:
            try:
                self.beep(1000, 80)
            except:
                pass

        if self.question_seconds_left <= 0:
            self.timer_label.config(text="答题时间到！请判定正确/错误。")
            try:
                self.beep(800, 350)
            except:
                pass
            self.question_timer_id = None
            # 倒计时到达后不自动判定（由老师或出题者点击 判定正确/错误）
            return
        else:
            self.update_question_timer_display()
            self.question_seconds_left -= 1
            self.question_timer_id = self.master.after(1000, self._tick_question_timer)

    def update_question_timer_display(self):
        sec = self.question_seconds_left
        mins = sec // 60
        s = sec % 60
        self.timer_label.config(text=f"答题倒计时：{mins:02d}:{s:02d}")

    # ---------- 判定与结算（不变） ----------
    def judge_answers(self):
        answered_players = [name for name,p in self.players.items() if p.invested > 0]
        if not answered_players:
            messagebox.showinfo("提示", "本题无人作答。可以点击 下一题。")
            return

        judge_win = tk.Toplevel(self.master)
        judge_win.title("判定正确/错误")
        judge_win.configure(bg=BG_COLOR)
        tk.Label(judge_win, text="勾选回答正确的同学，然后点击 确认 判定。", bg=BG_COLOR, fg=FG_COLOR, font=FONT_NORMAL).pack(pady=6)

        chk_vars = {}
        for name in answered_players:
            var = tk.IntVar(value=0)
            chk = tk.Checkbutton(judge_win, text=name + f"（投入 {self.players[name].invested}）", variable=var,
                                 bg=BG_COLOR, fg=FG_COLOR, selectcolor=BG_COLOR,
                                 activebackground=BG_COLOR, activeforeground=FG_COLOR, font=FONT_SMALL)
            chk.pack(anchor="w")
            chk_vars[name] = var

        def do_judge():
            corrects = [n for n,v in chk_vars.items() if v.get()==1]
            incorrects = [n for n in answered_players if n not in corrects]
            judge_win.destroy()
            self.resolve_round(corrects, incorrects)

        btn = tk.Button(judge_win, text="确认判定", font=FONT_NORMAL, bg=BTN_BG, fg=FG_COLOR,
                        activebackground=BTN_ACTIVE_BG, command=do_judge)
        btn.pack(pady=8)

    def resolve_round(self, corrects, incorrects):
        q = self.current_question
        diff = q['difficulty']

        total_losses_by_incorrect = sum(self.players[name].invested for name in incorrects)
        num_incorrect = len(incorrects)

        # 平均损失（向下取整）
        if num_incorrect > 0:
            avg_loss = total_losses_by_incorrect // num_incorrect
        else:
            avg_loss = 0

        # 给每个正确玩家结算：返还投入 + 奖励(diff) + 加倍奖励(if any) + avg_loss（来自错误者）
        for name in corrects:
            p = self.players[name]
            # 返还投入
            p.coins += p.invested
            # 奖励难度
            p.coins += diff
            # 加倍奖励
            if p.will_double:
                p.coins += diff
            # 来自错误者平均损失
            p.coins += avg_loss
            self.log(f"{name} 回答正确：返还投入 {p.invested}，奖励 {diff}{' + 加倍 '+str(diff) if p.will_double else ''}，外加错误者平均损失 {avg_loss}。")
            # 清理临时状态
            p.invested = 0
            p.will_answer = False
            p.will_double = False

        # 错误玩家：其投入已被扣除（贷款逻辑使余额可能为负）
        for name in incorrects:
            p = self.players[name]
            self.log(f"{name} 回答错误：损失 {p.invested}。")
            p.invested = 0
            p.will_answer = False
            p.will_double = False

        # 更新显示
        self.update_player_labels()
        self.judge_btn.config(state=tk.DISABLED)

        # 播放短促提示音
        try:
            self.beep(1200, 120)
        except:
            pass

        # 准备下一题或结束
        if self.asked_count < NUM_QUESTIONS:
            self.next_btn.config(state=tk.NORMAL)
        else:
            self.end_game()

    def next_question(self):
        # 重置选择与定时器
        for name in self.players:
            self.answer_vars[name].set(0)
            self.double_vars[name].set(0)

        # 取消任何残留计时器
        if self.bet_timer_id:
            try:
                self.master.after_cancel(self.bet_timer_id)
            except:
                pass
            self.bet_timer_id = None
        if self.question_timer_id:
            try:
                self.master.after_cancel(self.question_timer_id)
            except:
                pass
            self.question_timer_id = None

        self.next_btn.config(state=tk.DISABLED)
        self.draw_btn.config(state=tk.NORMAL)
        self.q_label.config(text="点击“抽取题目”继续")
        self.q_info_label.config(text="")
        self.timer_label.config(text="")

        # 如果已达到题数上限，直接结束
        if self.asked_count >= NUM_QUESTIONS:
            self.end_game()

    def end_game(self):
        ranking = sorted(self.players.values(), key=lambda p: p.coins, reverse=True)
        self.log("\n=== 游戏结束：最终排名 ===")
        for i,p in enumerate(ranking, start=1):
            self.log(f"{i}. {p.name} — {p.coins} 硬币")
        self.log("GAME OVER")
        final_text = "\n".join(f"{i}. {p.name} — {p.coins}" for i,p in enumerate(ranking, start=1))
        messagebox.showinfo("游戏结束", final_text + "\n\nGAME OVER")

        # 播放结束提示
        try:
            self.beep(700, 300)
            self.beep(900, 300)
        except:
            pass

        # 禁用所有按钮
        self.draw_btn.config(state=tk.DISABLED)
        self.confirm_btn.config(state=tk.DISABLED)
        self.judge_btn.config(state=tk.DISABLED)
        self.next_btn.config(state=tk.DISABLED)

# ---------------------------
# 启动
# ---------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = QuizGame(root)
    root.mainloop()