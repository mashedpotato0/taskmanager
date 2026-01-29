import sys
import json
import os
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget,
                             QHeaderView, QLabel, QHBoxLayout, QPushButton,
                             QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

# --- MATPLOTLIB INTEGRATION ---
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter # <--- ADD THIS IMPORT

# --- CONSTANTS ---
DATA_FILE = "task_data.json"
CONFIG_FILE = "tasks_config.json"

# Matches your original request to ensure data is visible
DEFAULT_CONFIG = [
    {"name": "Wake up time", "type": "time", "weight": 20, "target": "06:00", "condition": "before", "days": "Daily"},
    {"name": "Jog", "type": "bool", "weight": 15, "days": "Daily"},
    {"name": "Breakfast", "type": "bool", "weight": 5, "days": "Daily"},
    {"name": "Bath", "type": "bool", "weight": 5, "days": "Daily"},
    {"name": "Classes", "type": "bool", "weight": 25, "days": "Mon,Tue,Wed,Thu,Fri,Sat"},
    {"name": "Lunch", "type": "bool", "weight": 5, "days": "Daily"},
    {"name": "Study (Afternoon)", "type": "bool", "weight": 25, "days": "Daily"},
    {"name": "Gym", "type": "bool", "weight": 20, "days": "Daily"},
    {"name": "Study (Evening)", "type": "bool", "weight": 25, "days": "Daily"},
    {"name": "Sleep at 10.30", "type": "time", "weight": 20, "target": "22:45", "condition": "before", "days": "Daily"}
]

# --- UTILS ---
def minutes_from_midnight(time_str):
    """Converts HH:MM string to minutes (int)"""
    if not time_str: return None
    try:
        t = datetime.strptime(time_str, "%H:%M")
        return t.hour * 60 + t.minute
    except ValueError:
        return None

def time_to_float_hours(time_str):
    """Converts HH:MM to float hours (e.g., 06:30 -> 6.5) for plotting"""
    mins = minutes_from_midnight(time_str)
    if mins is None: return None
    return mins / 60.0

# --- GRAPH WIDGET ---
class AnalyticsCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.subplots_adjust(bottom=0.2, hspace=0.6, left=0.1, right=0.95)
        super(AnalyticsCanvas, self).__init__(self.fig)

        self.ax_score = self.fig.add_subplot(211)
        self.ax_time = self.fig.add_subplot(212)
    def format_y_axis_time(self, x, pos):
        """Turn 25.5 back into '01:30', 23.0 into '23:00'"""
        hours = int(x)
        if hours >= 24:
            hours -= 24
        return f"{hours:02d}:00"

    def plot_data(self, dates, scores, wake_data, sleep_data):
        self.ax_score.clear()
        self.ax_time.clear()

        # If no dates, just clear and redraw (fixes "stopped updating" on empty weeks)
        if not dates:
            self.draw()
            return

        # 1. SCORE PLOT
        self.ax_score.plot(dates, scores, 'o-', color='#2ecc71', linewidth=2, label='Daily Score')
        self.ax_score.set_title("Performance Trend")
        self.ax_score.set_ylabel("Score (%)")
        self.ax_score.set_ylim(0, 105)
        self.ax_score.grid(True, linestyle='--', alpha=0.6)
        self.ax_score.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        self.ax_score.legend(loc='lower left')

        # 2. TIME PLOT (Wake/Sleep)
        has_time_data = False # Flag to track if we actually plotted anything

        # Handle Wake Data
        valid_wake = [(d, v) for d, v in zip(dates, wake_data) if v is not None]
        if valid_wake:
            wd, wv = zip(*valid_wake)
            self.ax_time.plot(wd, wv, 'o--', color='#3498db', label='Wake Up')
            has_time_data = True

        # Handle Sleep Data
        valid_sleep = [(d, v) for d, v in zip(dates, sleep_data) if v is not None]
        if valid_sleep:
            sd, sv = zip(*valid_sleep)
            self.ax_time.plot(sd, sv, 'x--', color='#9b59b6', label='Sleep Time')
            has_time_data = True

        self.ax_time.set_title("Sleep Schedule")
        self.ax_time.set_ylabel("Hour")
        self.ax_time.set_ylim(0, 30)

        # Apply custom formatter to show 25.0 as 01:00
        self.ax_time.yaxis.set_major_formatter(FuncFormatter(self.format_y_axis_time))
        self.ax_time.set_yticks(range(0, 31, 4))
        self.ax_time.grid(True, linestyle='--', alpha=0.6)
        self.ax_time.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))

        # --- THE FIX: Only show legend if data exists ---
        if has_time_data:
            self.ax_time.legend(loc='lower left')

        self.draw() # Force update

# --- MAIN APP ---
class TaskManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FocusGrid - Analytics Dashboard")
        self.resize(1400, 900) # Taller window for graphs

        # Config & Data
        self.tasks_config = self.load_config()
        self.data = self.load_data()
        self.current_week_start = self.get_monday(datetime.now())

        # Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # 1. Navigation
        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("<< Prev Week")
        self.btn_prev.clicked.connect(self.prev_week)
        self.lbl_week = QLabel()
        self.lbl_week.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.lbl_week.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_next = QPushButton("Next Week >>")
        self.btn_next.clicked.connect(self.next_week)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.lbl_week)
        nav_layout.addWidget(self.btn_next)
        self.layout.addLayout(nav_layout)

        # 2. Table
        self.table = QTableWidget()
        self.render_table_structure()
        self.table.itemChanged.connect(self.on_item_changed)
        self.layout.addWidget(self.table, stretch=1) # Stretch 1 means take available space

        # 3. Graphs (Bottom Section)
        self.graph_canvas = AnalyticsCanvas(self, width=5, height=4)
        self.layout.addWidget(self.graph_canvas, stretch=1)

        # Initial Render
        self.render_week_data()
        self.update_graphs()

    # --- CORE LOGIC ---
    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'w') as f: json.dump(DEFAULT_CONFIG, f, indent=4)
            return DEFAULT_CONFIG
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: return DEFAULT_CONFIG

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f: return json.load(f)
            except: return {}
        return {}

    def get_monday(self, d): return d - timedelta(days=d.weekday())

    def calculate_day_stats(self, date_key, day_name):
        """Calculates Score, Wake Time, and Sleep Time for a specific date"""
        if date_key not in self.data: return 0, None, None

        day_data = self.data[date_key]
        total_weight = 0
        earned_score = 0
        wake_val = None
        sleep_val = None

        short_day = day_name[:3]

        for task in self.tasks_config:
            # Check availability
            allowed_days = task.get("days", "Daily")
            if allowed_days != "Daily" and short_day not in allowed_days:
                continue

            name = task['name']
            weight = task['weight']
            total_weight += weight
            val = day_data.get(name)

            # Extract specific metrics for graphing
            if "wake" in name.lower() and task['type'] == 'time':
                wake_val = time_to_float_hours(val)
            if "sleep" in name.lower() and task['type'] == 'time':
                sleep_val = time_to_float_hours(val)

            # Score Logic
            if task['type'] == 'bool' and val is True:
                earned_score += weight
            elif task['type'] == 'time' and val:
                target_mins = minutes_from_midnight(task['target'])
                user_mins = minutes_from_midnight(val)
                condition = task.get('condition', 'before')

                if target_mins is not None and user_mins is not None:
                    diff = user_mins - target_mins
                    if condition == 'before':
                        if diff <= 0: earned_score += weight
                        else:
                            penalty = (diff / 30) * 0.2
                            earned_score += max(0, weight * (1 - penalty))

        pct = (earned_score / total_weight * 100) if total_weight > 0 else 0
        return pct, wake_val, sleep_val

    def update_graphs(self):
        """Gather all historical data and plot it"""
        sorted_keys = sorted(self.data.keys())
        if not sorted_keys: return

        dates = []
        scores = []
        wake_times = []
        sleep_times = []

        for date_str in sorted_keys:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                day_name = dt.strftime("%A")

                pct, wake, sleep = self.calculate_day_stats(date_str, day_name)

                # --- FIX: MIDNIGHT CROSSOVER LOGIC ---
                # If sleep is early morning (e.g., < 12:00 PM), add 24 hours.
                # This treats 1:30 AM as 25.5 hours, keeping the line high.
                if sleep is not None and sleep < 12:
                    sleep += 24
                # -------------------------------------

                dates.append(dt)
                scores.append(pct)
                wake_times.append(wake)
                sleep_times.append(sleep)
            except: continue

        self.graph_canvas.plot_data(dates, scores, wake_times, sleep_times)

    # --- UI UPDATES ---
    def render_table_structure(self):
        headers = ["Day", "Date"] + [t['name'] for t in self.tasks_config] + ["Score"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def render_week_data(self):
        self.table.blockSignals(True)
        self.table.setRowCount(7)
        end = self.current_week_start + timedelta(days=6)
        self.lbl_week.setText(f"{self.current_week_start.strftime('%b %d')} - {end.strftime('%b %d')}")

        for row in range(7):
            curr = self.current_week_start + timedelta(days=row)
            date_key = curr.strftime("%Y-%m-%d")
            day_name = curr.strftime("%A")
            short_day = curr.strftime("%a")

            self.table.setItem(row, 0, QTableWidgetItem(day_name))
            self.table.setItem(row, 1, QTableWidgetItem(curr.strftime("%d/%m")))

            for col, task in enumerate(self.tasks_config, start=2):
                allowed = task.get("days", "Daily")
                if allowed != "Daily" and short_day not in allowed:
                    item = QTableWidgetItem("N/A")
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                    item.setBackground(QColor("#e0e0e0"))
                    self.table.setItem(row, col, item)
                    continue

                item = QTableWidgetItem()
                saved_val = self.data.get(date_key, {}).get(task['name'])

                if task['type'] == 'bool':
                    item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                    item.setCheckState(Qt.CheckState.Checked if saved_val else Qt.CheckState.Unchecked)
                else:
                    item.setFlags(Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsEnabled)
                    item.setText(str(saved_val) if saved_val else "")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                self.table.setItem(row, col, item)

            self.update_row_visual_score(row)

        self.table.blockSignals(False)

    def update_row_visual_score(self, row):
        # UI-only update for the specific row (faster than full recalc)
        day_name = self.table.item(row, 0).text()
        curr_date = self.current_week_start + timedelta(days=row)
        date_key = curr_date.strftime("%Y-%m-%d")

        pct, _, _ = self.calculate_day_stats(date_key, day_name)

        score_item = QTableWidgetItem(f"{int(pct)}%")
        score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        score_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        bg = "#ccffcc" if pct >= 80 else "#fff4cc" if pct >= 50 else "#ffcccc"
        score_item.setBackground(QColor(bg))
        self.table.setItem(row, self.table.columnCount()-1, score_item)

    def on_item_changed(self, item):
        row, col = item.row(), item.column()
        if col < 2 or col >= self.table.columnCount()-1: return

        curr_date = self.current_week_start + timedelta(days=row)
        date_key = curr_date.strftime("%Y-%m-%d")
        task_name = self.tasks_config[col-2]['name']
        task_type = self.tasks_config[col-2]['type']

        val = None
        if task_type == 'bool': val = (item.checkState() == Qt.CheckState.Checked)
        else: val = item.text().strip()

        if date_key not in self.data: self.data[date_key] = {}
        self.data[date_key][task_name] = val

        # Save & Update
        with open(DATA_FILE, 'w') as f: json.dump(self.data, f, indent=4)

        self.update_row_visual_score(row)
        self.update_graphs() # <--- REFRESH GRAPHS INSTANTLY

    def prev_week(self):
        self.current_week_start -= timedelta(days=7)
        self.render_week_data()

    def next_week(self):
        self.current_week_start += timedelta(days=7)
        self.render_week_data()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = TaskManager()
    window.show()
    sys.exit(app.exec())
