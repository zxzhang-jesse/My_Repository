import tkinter as tk
from tkinter import messagebox, simpledialog
import random
import os
import re

# optional winsound for Windows beep
try:
    import winsound

    def beep(freq=1000, dur=150):
        try:
            winsound.Beep(freq, dur)
        except Exception:
            root = tk._default_root
            if root:
                root.bell()
except Exception:
    def beep(freq=1000, dur=150):
        try:
            root = tk._default_root
            if root:
                root.bell()
        except Exception:
            pass

# --------------------------- Configuration ---------------------------
INITIAL_COINS = 5
PLAYERS = ["Vincent", "Eric", "Tony", "Bright"]
NUM_QUESTIONS = 20

# question time mapping by difficulty (seconds)
DIFFICULTY_TO_TIME = {1: 60, 2: 90, 3: 120, 4: 150}
BETTING_SECONDS = 20

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

# --------------------------- Question bank: pic1..pic5 for each difficulty ---------------------------
SAMPLE_QUESTIONS = []
for diff in range(1, 5):  # difficulties 1..4
    for i in range(1, 6):  # pic1..pic5
        SAMPLE_QUESTIONS.append({"text": f"pic{i}", "difficulty": diff})

# shuffle to randomize initial order
random.shuffle(SAMPLE_QUESTIONS)

# --------------------------- Player class ---------------------------
class Player:
    def __init__(self, name, coins):
        self.name = name
        self.coins = coins
        self.will_answer = False
        self.will_double = False
        self.invested = 0

# --------------------------- Main Game Class ---------------------------
class QuizGame:
    def __init__(self, master):
        self.master = master
        master.title("Physics Classroom Quiz Game")
        # removed fullscreen per request; just set background
        master.configure(bg=BG_COLOR)

        self.players = {name: Player(name, INITIAL_COINS) for name in PLAYERS}
        # copy the SAMPLE_QUESTIONS to instance questions
        self.questions = SAMPLE_QUESTIONS.copy()
        random.shuffle(self.questions)
        self.current_q_idx = -1
        self.asked_count = 0
        self.current_question = None

        # timers
        self.bet_seconds_left = 0
        self.bet_timer_id = None
        self.question_seconds_left = 0
        self.question_timer_id = None

        self.build_ui()
        self.update_player_labels()
        self.log("Ready. Initial coins per player: %d." % INITIAL_COINS)

    # ----------------- UI build -----------------
    def build_ui(self):
        # top players area
        self.top_frame = tk.Frame(self.master, bg=BG_COLOR)
        self.top_frame.pack(padx=12, pady=6, anchor="n")

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
            lbl_coins = tk.Label(frame, text=str(INITIAL_COINS), font=FONT_COINS, bg=BG_COLOR, fg=FG_COLOR)
            lbl_coins.pack(pady=(8,0))

            ans_var = tk.IntVar(value=0)
            dbl_var = tk.IntVar(value=0)
            chk_ans = tk.Checkbutton(frame, text="Answer", variable=ans_var, font=FONT_SMALL,
                                     bg=BG_COLOR, fg=FG_COLOR, selectcolor=BG_COLOR,
                                     activebackground=BG_COLOR, activeforeground=FG_COLOR)
            chk_dbl = tk.Checkbutton(frame, text="Double", variable=dbl_var, font=FONT_SMALL,
                                     bg=BG_COLOR, fg=FG_COLOR, selectcolor=BG_COLOR,
                                     activebackground=BG_COLOR, activeforeground=FG_COLOR)
            chk_ans.pack()
            chk_dbl.pack()

            self.player_frames[name] = frame
            self.player_name_labels[name] = lbl_name
            self.player_coin_labels[name] = lbl_coins
            self.answer_vars[name] = ans_var
            self.double_vars[name] = dbl_var

        # question frame (now only text)
        self.q_frame = tk.Frame(self.master, bg=BG_COLOR, pady=10)
        self.q_frame.pack(fill=tk.X, padx=12)

        self.q_label = tk.Label(self.q_frame, text='Click "Draw Question" to start', wraplength=1100, justify=tk.LEFT,
                                font=FONT_TITLE, bg=BG_COLOR, fg=FG_COLOR)
        self.q_label.pack(anchor="w")
        self.q_info_label = tk.Label(self.q_frame, text="", font=FONT_NORMAL, bg=BG_COLOR, fg=FG_COLOR)
        self.q_info_label.pack(anchor="w", pady=(6,0))

        # timer
        self.timer_label = tk.Label(self.q_frame, text="", font=(FONT_FAMILY, 40, "bold"),
                                    bg=BG_COLOR, fg=FG_COLOR)
        self.timer_label.pack(anchor="w", pady=(6,0))

        # controls row
        self.controls = tk.Frame(self.master, pady=12, bg=BG_COLOR)
        self.controls.pack()

        self.draw_btn = tk.Button(self.controls, text="Draw Question", font=FONT_NORMAL, bg=BTN_BG, fg=FG_COLOR,
                                  activebackground=BTN_ACTIVE_BG, command=self.draw_question, width=16)
        self.draw_btn.grid(row=0, column=0, padx=8)

        self.confirm_btn = tk.Button(self.controls, text="Confirm Bets (Lock In)", font=FONT_NORMAL, bg=BTN_BG, fg=FG_COLOR,
                                     activebackground=BTN_ACTIVE_BG, state=tk.DISABLED,
                                     command=lambda: self.confirm_answers(reveal_question=True, auto=False), width=22)
        self.confirm_btn.grid(row=0, column=1, padx=8)

        self.judge_btn = tk.Button(self.controls, text="Judge Correct/Incorrect", font=FONT_NORMAL, bg=BTN_BG, fg=FG_COLOR,
                                   activebackground=BTN_ACTIVE_BG, state=tk.DISABLED, command=self.judge_answers, width=20)
        self.judge_btn.grid(row=0, column=2, padx=8)

        self.next_btn = tk.Button(self.controls, text="Next Question", font=FONT_NORMAL, bg=BTN_BG, fg=FG_COLOR,
                                  activebackground=BTN_ACTIVE_BG, state=tk.DISABLED, command=self.next_question, width=16)
        self.next_btn.grid(row=0, column=3, padx=8)

        # log
        self.log_text = tk.Text(self.master, width=120, height=10, state=tk.DISABLED,
                                bg=BG_COLOR, fg=FG_COLOR, font=FONT_SMALL)
        self.log_text.pack(padx=12, pady=10)

    # ----------------- logging & helpers -----------------
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

    # ----------------- draw question & betting -----------------
    def draw_question(self):
        if self.asked_count >= NUM_QUESTIONS:
            messagebox.showinfo("Info", "All questions have been completed.")
            return

        # cancel any question timer to be safe
        if self.question_timer_id:
            try:
                self.master.after_cancel(self.question_timer_id)
            except Exception:
                pass
            self.question_timer_id = None

        self.current_q_idx += 1
        # loop if questions exhausted
        if self.current_q_idx >= len(self.questions):
            self.current_q_idx = 0
            self.log("Question bank cycled (not enough questions).")

        self.current_question = self.questions[self.current_q_idx]
        self.asked_count += 1

        # Show hidden state and start betting
        self.q_label.config(text=f"Question {self.asked_count}: Question is hidden — enter betting phase ({BETTING_SECONDS} s)")
        self.q_info_label.config(text="Please decide whether to Answer / Double during the countdown.")
        # The actual revealed text will be the image-filename-style name (e.g., pic1-d2)
        self.log("Question drawn (text hidden). If nobody bets, you may proceed to the next question.")
        self.confirm_btn.config(state=tk.NORMAL)
        self.draw_btn.config(state=tk.DISABLED)
        self.judge_btn.config(state=tk.DISABLED)
        self.next_btn.config(state=tk.DISABLED)

        # reset player selections for this round
        for name in self.players:
            # reset UI checkboxes
            self.answer_vars[name].set(0)
            self.double_vars[name].set(0)
            # reset internal state
            self.players[name].will_answer = False
            self.players[name].will_double = False
            self.players[name].invested = 0

        # start betting timer
        self.start_betting_timer(BETTING_SECONDS)

    def start_betting_timer(self, seconds):
        self.bet_seconds_left = seconds
        self.update_betting_timer_display()
        self._tick_betting_timer()

    def _tick_betting_timer(self):
        if self.bet_seconds_left <= 5 and self.bet_seconds_left > 0:
            try:
                beep(1000, 80)
            except Exception:
                pass

        if self.bet_seconds_left <= 0:
            self.timer_label.config(text="Bets locked — revealing question...")
            try:
                beep(800, 300)
            except Exception:
                pass
            self.bet_timer_id = None
            # auto lock & reveal
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
        self.timer_label.config(text=f"Betting timer: {mins:02d}:{s:02d}")

    # ----------------- confirm answers / reveal question -----------------
    def confirm_answers(self, reveal_question=False, auto=False):
        # cancel betting timer if active
        if self.bet_timer_id:
            try:
                self.master.after_cancel(self.bet_timer_id)
            except Exception:
                pass
            self.bet_timer_id = None

        q = self.current_question or {}
        diff = q.get('difficulty', 1)

        any_answer = False
        for name, p in self.players.items():
            p.will_answer = bool(self.answer_vars[name].get())
            p.will_double = bool(self.double_vars[name].get())
            p.invested = 0

        # allow loans: deduct even if not enough coins
        for name, p in self.players.items():
            if p.will_answer:
                stake = diff
                double_stake = diff if p.will_double else 0
                total_needed = stake + double_stake
                p.coins -= total_needed
                p.invested = total_needed
                any_answer = True
                if p.coins < 0:
                    self.log(f"{name} loaned {abs(p.coins)} coins to place the bet (invested {total_needed}).")
                else:
                    self.log(f"{name} invested {total_needed} (difficulty {diff}{', doubled' if p.will_double else ''}).")
            else:
                p.will_double = False
                p.invested = 0

        if not any_answer:
            self.log("No one bet on this question.")
            # If reveal_question requested, show question identifier (name)
            if reveal_question:
                self._show_question_text()
            # Allow proceeding to next question
            self.next_btn.config(state=tk.NORMAL)
            self.confirm_btn.config(state=tk.DISABLED)
            self.judge_btn.config(state=tk.DISABLED)
            self.update_player_labels()
            return
        else:
            if auto:
                self.log("System automatically locked bets (betting timer ended).")
            else:
                self.log("Bets manually locked.")

        self.update_player_labels()
        self.confirm_btn.config(state=tk.DISABLED)
        self.judge_btn.config(state=tk.NORMAL)

        # If reveal_question requested, show it and start question timer
        if reveal_question:
            self._show_question_text()
            t = DIFFICULTY_TO_TIME.get(diff, 20)
            self.start_question_timer(t)

    def _show_question_text(self):
        """
        Show the identifier: picX-dY
        """
        q = self.current_question or {}
        diff = q.get('difficulty', 1)
        base = q.get('text', '') or f"question{self.current_q_idx+1}"
        display_name = f"{base}-d{diff}"
        self.q_label.config(text=f"Question {self.asked_count}: {display_name}")
        self.q_info_label.config(text=f"Difficulty: {diff}    Suggested time: {DIFFICULTY_TO_TIME.get(diff, '?')} s")
        self.log(f"Revealed: {display_name}")

    # ----------------- question timer -----------------
    def start_question_timer(self, seconds):
        # cancel existing
        if self.question_timer_id:
            try:
                self.master.after_cancel(self.question_timer_id)
            except Exception:
                pass
            self.question_timer_id = None

        self.question_seconds_left = seconds
        self.update_question_timer_display()
        self._tick_question_timer()

    def _tick_question_timer(self):
        if self.question_seconds_left <= 5 and self.question_seconds_left > 0:
            try:
                beep(1000, 80)
            except Exception:
                pass

        if self.question_seconds_left <= 0:
            self.timer_label.config(text="Time's up! Please judge correct/incorrect.")
            try:
                beep(800, 350)
            except Exception:
                pass
            self.question_timer_id = None
            return
        else:
            self.update_question_timer_display()
            self.question_seconds_left -= 1
            self.question_timer_id = self.master.after(1000, self._tick_question_timer)

    def update_question_timer_display(self):
        sec = self.question_seconds_left
        mins = sec // 60
        s = sec % 60
        self.timer_label.config(text=f"Answer timer: {mins:02d}:{s:02d}")

    # ----------------- judge & settle -----------------
    def judge_answers(self):
        answered_players = [name for name,p in self.players.items() if p.invested > 0]
        if not answered_players:
            messagebox.showinfo("Info", "No one answered this question. You may click Next Question.")
            self.next_btn.config(state=tk.NORMAL)
            return

        judge_win = tk.Toplevel(self.master)
        judge_win.title("Judge Correct / Incorrect")
        judge_win.configure(bg=BG_COLOR)
        tk.Label(judge_win, text="Tick players who answered correctly, then click Confirm.",
                 bg=BG_COLOR, fg=FG_COLOR, font=FONT_NORMAL).pack(pady=6)

        chk_vars = {}
        for name in answered_players:
            var = tk.IntVar(value=0)
            chk = tk.Checkbutton(judge_win, text=name + f" (invested {self.players[name].invested})", variable=var,
                                 bg=BG_COLOR, fg=FG_COLOR, selectcolor=BG_COLOR,
                                 activebackground=BG_COLOR, activeforeground=FG_COLOR, font=FONT_SMALL)
            chk.pack(anchor="w")
            chk_vars[name] = var

        def do_judge():
            corrects = [n for n,v in chk_vars.items() if v.get()==1]
            incorrects = [n for n in answered_players if n not in corrects]
            judge_win.destroy()
            self.resolve_round(corrects, incorrects)

        btn = tk.Button(judge_win, text="Confirm Judgment", font=FONT_NORMAL, bg=BTN_BG, fg=FG_COLOR,
                        activebackground=BTN_ACTIVE_BG, command=do_judge)
        btn.pack(pady=8)

    def resolve_round(self, corrects, incorrects):
        q = self.current_question or {}
        diff = q.get('difficulty', 1)

        total_losses_by_incorrect = sum(self.players[name].invested for name in incorrects)
        num_incorrect = len(incorrects)

        if num_incorrect > 0:
            avg_loss = total_losses_by_incorrect // num_incorrect
        else:
            avg_loss = 0

        for name in corrects:
            p = self.players[name]
            p.coins += p.invested  # return principal
            p.coins += diff
            if p.will_double:
                p.coins += diff
            p.coins += avg_loss
            self.log(f"{name} answered correctly: returned {p.invested}, reward {diff}{' + doubled '+str(diff) if p.will_double else ''}, plus avg loss {avg_loss}.")
            p.invested = 0
            p.will_answer = False
            p.will_double = False

        for name in incorrects:
            p = self.players[name]
            self.log(f"{name} answered incorrectly: lost {p.invested}.")
            p.invested = 0
            p.will_answer = False
            p.will_double = False

        self.update_player_labels()
        self.judge_btn.config(state=tk.DISABLED)
        try:
            beep(1200, 120)
        except Exception:
            pass

        if self.asked_count < NUM_QUESTIONS:
            self.next_btn.config(state=tk.NORMAL)
        else:
            self.end_game()

    def next_question(self):
        # reset checkboxes
        for name in self.players:
            self.answer_vars[name].set(0)
            self.double_vars[name].set(0)

        # cancel any timers
        if self.bet_timer_id:
            try:
                self.master.after_cancel(self.bet_timer_id)
            except Exception:
                pass
            self.bet_timer_id = None
        if self.question_timer_id:
            try:
                self.master.after_cancel(self.question_timer_id)
            except Exception:
                pass
            self.question_timer_id = None

        self.next_btn.config(state=tk.DISABLED)
        self.draw_btn.config(state=tk.NORMAL)
        self.q_label.config(text='Click "Draw Question" to continue')
        self.q_info_label.config(text="")
        self.timer_label.config(text="")

        if self.asked_count >= NUM_QUESTIONS:
            self.end_game()

    def end_game(self):
        ranking = sorted(self.players.values(), key=lambda p: p.coins, reverse=True)
        self.log("\n=== Game Over: Final Ranking ===")
        for i,p in enumerate(ranking, start=1):
            self.log(f"{i}. {p.name} — {p.coins} coins")
        self.log("GAME OVER")
        final_text = "\n".join(f"{i}. {p.name} — {p.coins}" for i,p in enumerate(ranking, start=1))
        messagebox.showinfo("Game Over", final_text + "\n\nGAME OVER")
        try:
            beep(700,300); beep(900,300)
        except Exception:
            pass
        # disable buttons
        self.draw_btn.config(state=tk.DISABLED)
        self.confirm_btn.config(state=tk.DISABLED)
        self.judge_btn.config(state=tk.DISABLED)
        self.next_btn.config(state=tk.DISABLED)

# --------------------------- Start ---------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = QuizGame(root)
    root.mainloop()
    