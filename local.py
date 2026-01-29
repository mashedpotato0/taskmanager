import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import datetime
from datetime import timedelta
import math

# --- CONFIG & THEME ---
DATA_FILE = "focus_grid_data.json"
CURR_YEAR = datetime.date.today().year
DEFAULT_START = f"{CURR_YEAR}-01-01"
DEFAULT_END = f"{CURR_YEAR}-12-31"

# Colors (Dark Ocean Theme)
COLORS = {
    "bg": "#050b14",
    "card": "#0f172a",
    "hover": "#1e293b",
    "text": "#e2e8f0",
    "muted": "#94a3b8",
    "cyan": "#06b6d4",
    "green": "#10b981",
    "purple": "#8b5cf6",
    "yellow": "#facc15",
    "red": "#f43f5e",
    "border": "#1e293b"
}

# Default Configuration
DEFAULT_CONFIG = [
    {"name": "Wake up", "type": "time", "weight": 20, "target": "06:00", "condition": "before", "days": "Mon,Tue,Wed,Thu,Fri,Sat,Sun", "startDate": DEFAULT_START, "endDate": DEFAULT_END},
    {"name": "Work", "type": "bool", "weight": 20, "days": "Mon,Tue,Wed,Thu,Fri", "startDate": DEFAULT_START, "endDate": DEFAULT_END}
]

class FocusGridApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FocusGrid - Local App")
        self.root.geometry("1400x900")
        self.root.configure(bg=COLORS["bg"])

        # State
        self.current_monday = self.get_monday(datetime.date.today())
        self.app_data = {}
        self.app_config = []
        
        self.load_data()

        # Styles
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TCombobox", fieldbackground=COLORS["card"], background=COLORS["bg"], foreground="white", arrowcolor=COLORS["cyan"])
        self.style.map("TCombobox", fieldbackground=[("readonly", COLORS["card"])], selectbackground=[("readonly", COLORS["card"])], selectforeground=[("readonly", "white")])

        # Layout
        self.build_ui()
        self.render_view()

    # --- DATA HANDLING ---
    def get_monday(self, d):
        return d - timedelta(days=d.weekday())

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    payload = json.load(f)
                    self.app_data = payload.get("data", {})
                    self.app_config = payload.get("config", DEFAULT_CONFIG)
            except:
                self.app_config = DEFAULT_CONFIG
        else:
            self.app_config = DEFAULT_CONFIG

    def save_data(self):
        payload = {"data": self.app_data, "config": self.app_config}
        with open(DATA_FILE, 'w') as f:
            json.dump(payload, f, indent=4)
        self.render_view() # Refresh charts/scores

    def update_record(self, date_key, task_name, value):
        if date_key not in self.app_data:
            self.app_data[date_key] = {}
        self.app_data[date_key][task_name] = value
        self.save_data()

    # --- UI BUILDING ---
    def build_ui(self):
        # 1. Header
        header_frame = tk.Frame(self.root, bg=COLORS["card"], padx=20, pady=15, highlightthickness=1, highlightbackground=COLORS["border"])
        header_frame.pack(fill="x", padx=20, pady=20)

        tk.Label(header_frame, text="FOCUS GRID", font=("Helvetica", 18, "bold"), fg=COLORS["cyan"], bg=COLORS["card"]).pack(side="left")

        nav_frame = tk.Frame(header_frame, bg=COLORS["card"])
        nav_frame.pack(side="right")

        self.btn_prev = self.create_btn(nav_frame, "< Prev", lambda: self.change_week(-7))
        self.lbl_week = tk.Label(nav_frame, text="", width=25, fg=COLORS["text"], bg=COLORS["card"], font=("Helvetica", 10, "bold"))
        self.lbl_week.pack(side="left", padx=10)
        self.btn_next = self.create_btn(nav_frame, "Next >", lambda: self.change_week(7))
        
        tk.Frame(nav_frame, width=20, bg=COLORS["card"]).pack(side="left") # Spacer
        self.create_btn(nav_frame, "⚙ Manage Tasks", self.open_manager, primary=True)

        # 2. Main Scrollable Area
        self.main_canvas = tk.Canvas(self.root, bg=COLORS["bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = tk.Frame(self.main_canvas, bg=COLORS["bg"])

        self.scrollable_frame.bind("<Configure>", lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))
        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.main_canvas.pack(side="left", fill="both", expand=True, padx=20)
        self.scrollbar.pack(side="right", fill="y")

        # 3. Grid Container
        self.grid_container = tk.Frame(self.scrollable_frame, bg=COLORS["card"], highlightthickness=1, highlightbackground=COLORS["border"])
        self.grid_container.pack(fill="x", pady=(0, 20))

        # 4. Charts Container
        self.charts_container = tk.Frame(self.scrollable_frame, bg=COLORS["bg"])
        self.charts_container.pack(fill="x", pady=(0, 50))

    def create_btn(self, parent, text, command, primary=False):
        fg = COLORS["bg"] if primary else COLORS["muted"]
        bg = COLORS["cyan"] if primary else COLORS["hover"]
        btn = tk.Button(parent, text=text, command=command, fg=fg, bg=bg, 
                        activebackground=COLORS["cyan"], activeforeground=COLORS["bg"],
                        relief="flat", padx=10, pady=5, font=("Helvetica", 9, "bold"))
        btn.pack(side="left", padx=2)
        return btn

    def change_week(self, days):
        self.current_monday += timedelta(days=days)
        self.render_view()

    # --- RENDERING ---
    def render_view(self):
        # Update Week Label
        end_date = self.current_monday + timedelta(days=6)
        self.lbl_week.config(text=f"{self.current_monday.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}")

        # Clear Grid
        for widget in self.grid_container.winfo_children():
            widget.destroy()

        # Rebuild Headers
        headers = ["Day", "Date"] + [f"{t['name']}\n({t['weight']}pts)" for t in self.app_config] + ["Score"]
        for i, h in enumerate(headers):
            lbl = tk.Label(self.grid_container, text=h, bg=COLORS["card"], fg=COLORS["cyan"], 
                           font=("Helvetica", 9, "bold"), pady=10, padx=5, borderwidth=1, relief="solid")
            lbl.grid(row=0, column=i, sticky="nsew")
        
        # Build Rows (Days)
        week_dates = [self.current_monday + timedelta(days=i) for i in range(7)]
        
        for r, date_obj in enumerate(week_dates):
            row_idx = r + 1
            date_key = date_obj.strftime("%Y-%m-%d")
            day_short = date_obj.strftime("%a")
            day_fmt = date_obj.strftime("%d/%m")

            # Day/Date Cells
            tk.Label(self.grid_container, text=day_short, bg=COLORS["bg"], fg=COLORS["cyan"], font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="nsew", padx=1, pady=1)
            tk.Label(self.grid_container, text=day_fmt, bg=COLORS["bg"], fg=COLORS["text"]).grid(row=row_idx, column=1, sticky="nsew", padx=1, pady=1)

            # Task Cells
            for c, task in enumerate(self.app_config):
                col_idx = c + 2
                
                # Check Validity
                is_active_day = day_short in task['days']
                is_active_date = task['startDate'] <= date_key <= task['endDate']

                frame = tk.Frame(self.grid_container, bg=COLORS["bg"], padx=5, pady=5)
                frame.grid(row=row_idx, column=col_idx, sticky="nsew", padx=1, pady=1)

                if not (is_active_day and is_active_date):
                    tk.Label(frame, text="--", bg=COLORS["bg"], fg=COLORS["muted"]).pack()
                    continue

                saved_val = self.app_data.get(date_key, {}).get(task['name'], "")

                if task['type'] == 'bool':
                    var = tk.BooleanVar(value=bool(saved_val))
                    cb = tk.Checkbutton(frame, variable=var, bg=COLORS["bg"], activebackground=COLORS["bg"], selectcolor=COLORS["card"],
                                        command=lambda k=date_key, t=task['name'], v=var: self.update_record(k, t, v.get()))
                    cb.pack()
                
                elif task['type'] == 'score':
                    sv = tk.StringVar(value=str(saved_val) if saved_val else "")
                    entry = tk.Entry(frame, textvariable=sv, width=5, bg=COLORS["card"], fg="white", justify="center", insertbackground="white")
                    entry.pack()
                    # Validate and save on focus out
                    entry.bind("<FocusOut>", lambda e, k=date_key, t=task['name'], s=sv: self.update_record(k, t, s.get()))

                elif task['type'] == 'time':
                    # DROPDOWN SELECTORS FOR TIME (Requested Feature)
                    h_val, m_val = "00", "00"
                    if saved_val and ":" in str(saved_val):
                        h_val, m_val = str(saved_val).split(":")
                    
                    time_frame = tk.Frame(frame, bg=COLORS["bg"])
                    time_frame.pack()

                    h_cb = ttk.Combobox(time_frame, values=[f"{i:02d}" for i in range(24)], width=3, state="readonly")
                    h_cb.set(h_val)
                    h_cb.pack(side="left")

                    tk.Label(time_frame, text=":", bg=COLORS["bg"], fg="white").pack(side="left")

                    m_cb = ttk.Combobox(time_frame, values=[f"{i:02d}" for i in range(60)], width=3, state="readonly")
                    m_cb.set(m_val)
                    m_cb.pack(side="left")

                    def save_time(e, k=date_key, t=task['name'], h=h_cb, m=m_cb):
                        self.update_record(k, t, f"{h.get()}:{m.get()}")
                    
                    h_cb.bind("<<ComboboxSelected>>", save_time)
                    m_cb.bind("<<ComboboxSelected>>", save_time)

            # Score Cell
            stats = self.calculate_stats(date_key)
            score_color = COLORS["red"]
            if stats['pct'] >= 80: score_color = COLORS["green"]
            elif stats['pct'] >= 50: score_color = COLORS["yellow"]
            
            tk.Label(self.grid_container, text=f"{int(stats['pct'])}%", bg=COLORS["bg"], fg=score_color, font=("Helvetica", 9, "bold")).grid(row=row_idx, column=len(headers)-1, sticky="nsew", padx=1, pady=1)

        # Configure Grid Weights
        for i in range(len(headers)):
            self.grid_container.grid_columnconfigure(i, weight=1)

        self.render_charts()

    # --- LOGIC ---
    def parse_time(self, val):
        if not val or ":" not in str(val): return None
        try:
            parts = str(val).split(":")
            return float(parts[0]) + float(parts[1])/60.0
        except: return None

    def calculate_stats(self, date_key):
        if date_key not in self.app_data: return {'pct': 0, 'wake': None, 'sleep': None}
        
        total_pts = 0
        earned_pts = 0
        wake_val = None
        sleep_val = None

        y, m, d = map(int, date_key.split("-"))
        dt = datetime.date(y, m, d)
        day_short = dt.strftime("%a")

        for task in self.app_config:
            # Filters
            if not (task['startDate'] <= date_key <= task['endDate']): continue
            if day_short not in task['days']: continue

            total_pts += task['weight']
            val = self.app_data[date_key].get(task['name'])

            if not val: continue

            if task['type'] == 'bool':
                if val: earned_pts += task['weight']
            
            elif task['type'] == 'score':
                try:
                    score = float(val)
                    earned_pts += (min(100, max(0, score)) / 100) * task['weight']
                except: pass
            
            elif task['type'] == 'time':
                curr = self.parse_time(val)
                target = self.parse_time(task.get('target', "00:00"))
                
                # For charts
                if "wake" in task['name'].lower(): wake_val = curr
                if "sleep" in task['name'].lower(): 
                    sleep_val = curr + 24 if curr < 12 else curr

                if curr is not None and target is not None:
                    diff_mins = (curr * 60) - (target * 60)
                    if task.get('condition') == 'before':
                        if diff_mins <= 0: earned_pts += task['weight']
                        else:
                            penalty = (diff_mins / 30) * 0.2
                            earned_pts += max(0, task['weight'] * (1 - penalty))
                    else:
                        if diff_mins >= 0: earned_pts += task['weight']

        pct = (earned_pts / total_pts * 100) if total_pts > 0 else 0
        return {'pct': pct, 'wake': wake_val, 'sleep': sleep_val}

    # --- CHARTS (Custom Canvas Drawing) ---
    def render_charts(self):
        for w in self.charts_container.winfo_children(): w.destroy()
        
        # Data Prep
        dates = [self.current_monday + timedelta(days=i) for i in range(7)]
        scores = []
        wakes = []
        sleeps = []

        for d in dates:
            stats = self.calculate_stats(d.strftime("%Y-%m-%d"))
            scores.append(stats['pct'])
            wakes.append(stats['wake'])
            sleeps.append(stats['sleep'])

        # Draw Charts
        self.draw_chart("Efficiency (%)", scores, 0, 100, COLORS["green"], 0)
        self.draw_chart("Wake (Cyan) & Sleep (Purple)", None, 0, 30, None, 1, extra_lines=[(wakes, COLORS["cyan"]), (sleeps, COLORS["purple"])])

    def draw_chart(self, title, data, min_y, max_y, color, col_idx, extra_lines=None):
        frame = tk.Frame(self.charts_container, bg=COLORS["card"], bd=1, relief="solid")
        frame.pack(side="left", fill="both", expand=True, padx=10)

        tk.Label(frame, text=title, bg=COLORS["card"], fg=COLORS["text"], font=("Helvetica", 10, "bold")).pack(pady=5)
        
        cv = tk.Canvas(frame, bg=COLORS["card"], height=200, highlightthickness=0)
        cv.pack(fill="both", expand=True, padx=10, pady=5)
        
        w = 600 # Approx width
        h = 180
        margin = 20
        
        # Grid lines
        cv.create_line(margin, h, w, h, fill=COLORS["muted"]) # X axis
        cv.create_line(margin, 0, margin, h, fill=COLORS["muted"]) # Y axis

        # Plot Logic
        def plot_line(line_data, line_color):
            points = []
            valid_indices = []
            for i, val in enumerate(line_data):
                if val is None: continue
                x = margin + (i * ((w-margin)/6))
                # Normalize Y
                normalized = (val - min_y) / (max_y - min_y)
                y = h - (normalized * h)
                points.append((x, y))
                valid_indices.append(i)
                
                # Draw point
                cv.create_oval(x-3, y-3, x+3, y+3, fill=line_color, outline=line_color)

            # Connect lines
            for i in range(len(points)-1):
                # Only connect if consecutive days (logic simplified)
                if valid_indices[i+1] == valid_indices[i] + 1:
                    cv.create_line(points[i][0], points[i][1], points[i+1][0], points[i+1][1], fill=line_color, width=2)

        if data: plot_line(data, color)
        if extra_lines:
            for l_data, l_color in extra_lines:
                plot_line(l_data, l_color)

    # --- TASK MANAGER POPUP ---
    def open_manager(self):
        top = tk.Toplevel(self.root)
        top.title("Manage Tasks")
        top.geometry("600x600")
        top.configure(bg=COLORS["bg"])

        # List Area
        list_frame = tk.Frame(top, bg=COLORS["card"])
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)

        def refresh_list():
            for w in list_frame.winfo_children(): w.destroy()
            for i, task in enumerate(self.app_config):
                f = tk.Frame(list_frame, bg=COLORS["bg"], pady=5, padx=5, bd=1, relief="solid")
                f.pack(fill="x", pady=2)
                
                tk.Label(f, text=task['name'], font=("Helvetica", 10, "bold"), fg=COLORS["cyan"], bg=COLORS["bg"]).pack(side="left")
                tk.Label(f, text=f"({task['type']})", fg=COLORS["muted"], bg=COLORS["bg"]).pack(side="left", padx=5)
                
                tk.Button(f, text="X", fg=COLORS["red"], bg=COLORS["bg"], command=lambda idx=i: delete_task(idx)).pack(side="right")
                tk.Button(f, text="Edit", fg=COLORS["text"], bg=COLORS["hover"], command=lambda idx=i: edit_task(idx)).pack(side="right", padx=5)

        def delete_task(idx):
            if messagebox.askyesno("Confirm", "Delete task?"):
                self.app_config.pop(idx)
                self.save_data()
                refresh_list()

        # Add/Edit Area
        editor_frame = tk.Frame(top, bg=COLORS["bg"], pady=10)
        editor_frame.pack(fill="x", padx=10)

        # Inputs
        tk.Label(editor_frame, text="Name", bg=COLORS["bg"], fg="white").grid(row=0, column=0)
        e_name = tk.Entry(editor_frame, bg=COLORS["card"], fg="white")
        e_name.grid(row=0, column=1, sticky="ew")

        tk.Label(editor_frame, text="Weight", bg=COLORS["bg"], fg="white").grid(row=0, column=2)
        e_weight = tk.Spinbox(editor_frame, from_=1, to=100, bg=COLORS["card"], fg="white")
        e_weight.grid(row=0, column=3, sticky="ew")

        tk.Label(editor_frame, text="Type", bg=COLORS["bg"], fg="white").grid(row=1, column=0)
        type_cb = ttk.Combobox(editor_frame, values=["bool", "time", "score"], state="readonly")
        type_cb.set("bool")
        type_cb.grid(row=1, column=1, sticky="ew")

        # Time Target Input (Dropdowns)
        tk.Label(editor_frame, text="Target (HH:MM)", bg=COLORS["bg"], fg="white").grid(row=2, column=0)
        time_f = tk.Frame(editor_frame, bg=COLORS["bg"])
        time_f.grid(row=2, column=1, sticky="w")
        target_h = ttk.Combobox(time_f, values=[f"{i:02d}" for i in range(24)], width=3); target_h.set("00")
        target_h.pack(side="left")
        target_m = ttk.Combobox(time_f, values=[f"{i:02d}" for i in range(60)], width=3); target_m.set("00")
        target_m.pack(side="left")

        current_edit_idx = [-1] # Mutable closure hack

        def edit_task(idx):
            t = self.app_config[idx]
            current_edit_idx[0] = idx
            e_name.delete(0, tk.END); e_name.insert(0, t['name'])
            # Reset Spinbox manually
            e_weight.delete(0, tk.END); e_weight.insert(0, t['weight'])
            type_cb.set(t['type'])
            
            if "target" in t:
                try:
                    th, tm = t['target'].split(":")
                    target_h.set(th); target_m.set(tm)
                except: pass

        def save_task():
            name = e_name.get()
            if not name: return
            
            new_t = {
                "name": name,
                "weight": int(e_weight.get()),
                "type": type_cb.get(),
                "target": f"{target_h.get()}:{target_m.get()}",
                "condition": "before", # Simplified
                "days": "Mon,Tue,Wed,Thu,Fri,Sat,Sun", # Simplified default
                "startDate": DEFAULT_START,
                "endDate": DEFAULT_END
            }

            if current_edit_idx[0] == -1:
                self.app_config.append(new_t)
            else:
                self.app_config[current_edit_idx[0]] = new_t
            
            self.save_data()
            refresh_list()
            current_edit_idx[0] = -1
            e_name.delete(0, tk.END)

        tk.Button(editor_frame, text="Save / Update", command=save_task, bg=COLORS["cyan"], fg=COLORS["bg"]).grid(row=3, column=0, columnspan=4, pady=10)

        refresh_list()

if __name__ == "__main__":
    root = tk.Tk()
    app = FocusGridApp(root)
    root.mainloop()
