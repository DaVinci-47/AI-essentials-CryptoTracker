
"""
Live Crypto Tracker - beginner-friendly GUI using CoinGecko

Features:
- Tracks multiple coins (bitcoin, ethereum, solana by default)
- Live price updates from CoinGecko (no API key)
- Auto-refresh interval (configurable in code or UI)
- Matplotlib price history graphs embedded in Tkinter
- Simple Alerts (user can set thresholds per coin)
- Save price history to CSV

Dependencies:
    pip install requests matplotlib

Run:
    python crypto_tracker.py
"""
import requests
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import threading
import time
import csv
from datetime import datetime
from collections import deque

# ----------------- Configuration -----------------
COINS = ["bitcoin", "ethereum", "solana"]  # CoinGecko ids
COIN_DISPLAY = {"bitcoin": "Bitcoin (BTC)", "ethereum": "Ethereum (ETH)", "solana": "Solana (SOL)"}
VS_CURRENCY = "usd"
REFRESH_INTERVAL = 5  # seconds (default auto-refresh)
MAX_HISTORY = 120  # max stored points per coin for plotting
# -------------------------------------------------

class CryptoTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Live Crypto Tracker")
        self.root.geometry("1100x750")
        self.root.resizable(True, True)

        # Data structures
        self.price_history = {coin: deque(maxlen=MAX_HISTORY) for coin in COINS}
        self.timestamps = deque(maxlen=MAX_HISTORY)
        self.current_prices = {coin: None for coin in COINS}
        # Alerts: store dict of {coin: {"threshold": float or None, "direction": "above" or "below"}}
        self.alerts = {coin: {"threshold": None, "direction": "above"} for coin in COINS}

        # UI setup
        self._build_ui()

        # Start first update (non-blocking)
        self._schedule_price_update(0)

    def _build_ui(self):
        header = tk.Label(self.root, text="LIVE CRYPTO TRACKER", font=("Arial", 20, "bold"))
        header.pack(pady=8)

        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Left panel: controls & price labels
        left = tk.Frame(main_frame)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0,10))

        lbl = tk.Label(left, text="Tracked Coins", font=("Arial", 14, "underline"))
        lbl.pack(pady=(0,6))

        self.price_labels = {}
        self.alert_entries = {}
        self.direction_vars = {}
        for coin in COINS:
            frm = tk.Frame(left, relief=tk.RIDGE, bd=1, padx=6, pady=6)
            frm.pack(fill=tk.X, pady=6)

            title = tk.Label(frm, text=COIN_DISPLAY.get(coin, coin.capitalize()), font=("Arial", 12, "bold"))
            title.grid(row=0, column=0, sticky="w")

            price_label = tk.Label(frm, text="Loading...", font=("Arial", 12))
            price_label.grid(row=1, column=0, sticky="w", pady=(4,0))
            self.price_labels[coin] = price_label

            # Alert controls
            alert_frame = tk.Frame(frm)
            alert_frame.grid(row=0, column=1, rowspan=2, padx=(10,0), sticky="n")

            tk.Label(alert_frame, text="Alert:").grid(row=0, column=0, sticky="e")
            alert_entry = tk.Entry(alert_frame, width=10)
            alert_entry.grid(row=0, column=1, padx=(4,0))

            dir_var = tk.StringVar(value="above")
            dir_menu = ttk.Combobox(alert_frame, textvariable=dir_var, values=["above", "below"], width=6, state="readonly")
            dir_menu.grid(row=0, column=2, padx=(4,0))

            set_btn = tk.Button(alert_frame, text="Set", command=lambda c=coin, e=alert_entry, d=dir_var: self.set_alert(c,e,d))
            set_btn.grid(row=1, column=1, columnspan=2, sticky="we", pady=(6,0))

            self.alert_entries[coin] = alert_entry
            self.direction_vars[coin] = dir_var

        # Controls: refresh interval, save CSV
        ctrl_frame = tk.Frame(left, pady=8)
        ctrl_frame.pack(fill=tk.X, pady=(10,0))

        tk.Label(ctrl_frame, text="Refresh (s):").grid(row=0, column=0, sticky="w")
        self.refresh_var = tk.IntVar(value=REFRESH_INTERVAL)
        refresh_spin = tk.Spinbox(ctrl_frame, from_=1, to=3600, textvariable=self.refresh_var, width=6)
        refresh_spin.grid(row=0, column=1, padx=(6,0))

        save_btn = tk.Button(ctrl_frame, text="Save History (CSV)", command=self.save_history_csv)
        save_btn.grid(row=1, column=0, columnspan=2, pady=(8,0), sticky="we")

        clear_btn = tk.Button(ctrl_frame, text="Clear History", command=self.clear_history)
        clear_btn.grid(row=2, column=0, columnspan=2, pady=(8,0), sticky="we")

        help_btn = tk.Button(ctrl_frame, text="How to use", command=self.show_help)
        help_btn.grid(row=3, column=0, columnspan=2, pady=(8,0), sticky="we")

        # Right panel: plots
        right = tk.Frame(main_frame)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        plots_label = tk.Label(right, text="Price History (last {} updates)".format(MAX_HISTORY), font=("Arial", 12, "underline"))
        plots_label.pack(pady=(0,6))

        # A canvas area with scroll for many coins
        canvas = tk.Canvas(right)
        scrollbar = tk.Scrollbar(right, orient=tk.VERTICAL, command=canvas.yview)
        self.plots_frame = tk.Frame(canvas)

        self.plots_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0,0), window=self.plots_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # For each coin we create a matplotlib figure and canvas
        self.figures = {}
        self.axes = {}
        self.canvases = {}
        for coin in COINS:
            fig = plt.Figure(figsize=(6,2.8), dpi=100)
            ax = fig.add_subplot(111)
            ax.set_title(COIN_DISPLAY.get(coin, coin))
            ax.set_xlabel("Updates")
            ax.set_ylabel(f"Price ({VS_CURRENCY.upper()})")
            fig.tight_layout()

            frame = tk.Frame(self.plots_frame, pady=6)
            frame.pack(fill=tk.BOTH, expand=True)

            canvas_agg = FigureCanvasTkAgg(fig, master=frame)
            canvas_agg.draw()
            widget = canvas_agg.get_tk_widget()
            widget.pack(fill=tk.BOTH, expand=True)

            self.figures[coin] = fig
            self.axes[coin] = ax
            self.canvases[coin] = canvas_agg

    def show_help(self):
        text = (
            "How to use the Live Crypto Tracker:\n\n"
            "- The app fetches prices from CoinGecko every few seconds (set Refresh in left panel).\n"
            "- Set an alert for a coin by typing a numeric threshold and selecting 'above' or 'below', then click Set.\n"
            "- Click 'Save History (CSV)' to export recorded price history.\n"
            "- Click 'Clear History' to reset stored price history.\n\n"
            "Note: This is a beginner-friendly app for demonstration. Network errors will be shown in a message box."
        )
        messagebox.showinfo("How to use", text)

    def set_alert(self, coin, entry_widget, dir_var):
        txt = entry_widget.get().strip()
        if txt == "":
            # clear alert
            self.alerts[coin]["threshold"] = None
            messagebox.showinfo("Alert cleared", f"Alert cleared for {COIN_DISPLAY.get(coin, coin)}")
            return
        try:
            val = float(txt.replace(",", ""))
            direction = dir_var.get()
            self.alerts[coin]["threshold"] = val
            self.alerts[coin]["direction"] = direction
            messagebox.showinfo("Alert set", f"Alert for {COIN_DISPLAY.get(coin, coin)}: {direction} {val}")
        except ValueError:
            messagebox.showerror("Invalid number", "Please enter a valid numeric threshold (e.g., 30000 or 2.5)")

    def _schedule_price_update(self, delay_seconds=None):
        # Schedule the next price update (non-blocking)
        if delay_seconds is None:
            delay_seconds = self.refresh_var.get()
        # Use threading to fetch so tkinter mainloop isn't blocked
        t = threading.Thread(target=self._fetch_and_process_prices, daemon=True)
        t.start()
        # After 'delay_seconds', call scheduler again to fetch continuously.
        # But we don't want overlapping fetches, so we schedule this after the current fetch finishes.
        # Instead, we will schedule the next call from the end of processing.

    def _fetch_and_process_prices(self):
        """Fetch latest prices and then update UI (uses root.after for thread-safe UI update)."""
        try:
            prices = self.fetch_prices()
        except Exception as e:
            prices = None
            err = str(e)
        # Update UI via main thread
        self.root.after(0, lambda: self._process_fetch_result(prices))

    def fetch_prices(self):
        """Get current prices from CoinGecko simple/price endpoint"""
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": ",".join(COINS),
            "vs_currencies": VS_CURRENCY
        }
        resp = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Example: {'bitcoin': {'usd': 12345.67}, 'ethereum': {'usd': 234.56}}
        result = {}
        for coin in COINS:
            if coin in data and VS_CURRENCY in data[coin]:
                result[coin] = float(data[coin][VS_CURRENCY])
            else:
                result[coin] = None
        return result

    def _process_fetch_result(self, prices):
        """Update labels, histories, graphs, and alerts. Then schedule next fetch.
        if prices is None:
            messagebox.showerror("Network Error", "Failed to fetch prices from CoinGecko. Will retry.")
            # schedule next attempt
            self.root.after(max(1000, int(self.refresh_var.get()*1000)), lambda: self._schedule_price_update())
            return"""

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # store timestamp once per update
        self.timestamps.append(ts)

        for coin, price in prices.items():
            if price is None:
                self.price_labels[coin].config(text="N/A")
                continue

            self.current_prices[coin] = price
            self.price_labels[coin].config(text=f"${price:,.2f}")

            # append to history
            self.price_history[coin].append(price)

            # check alerts
            alert_conf = self.alerts.get(coin)
            if alert_conf and alert_conf["threshold"] is not None:
                thr = alert_conf["threshold"]
                direction = alert_conf.get("direction", "above")
                triggered = False
                if direction == "above" and price >= thr:
                    triggered = True
                if direction == "below" and price <= thr:
                    triggered = True
                if triggered:
                    # Show alert and then clear it to avoid repeat spam
                    messagebox.showinfo("Price Alert", f"{COIN_DISPLAY.get(coin, coin)} is {direction} {thr} (current: ${price:,.2f})")
                    # Optionally you can comment out the next line if you want repeated alerts
                    self.alerts[coin]["threshold"] = None
                    self.alert_entries[coin].delete(0, tk.END)

        # Update plots
        for coin in COINS:
            self._update_plot(coin)

        # schedule next fetch after configured seconds
        delay_ms = max(1000, int(self.refresh_var.get() * 1000))
        self.root.after(delay_ms, lambda: self._schedule_price_update())

    def _update_plot(self, coin):
        ax = self.axes[coin]
        ax.clear()
        hist = list(self.price_history[coin])
        if len(hist) == 0:
            ax.text(0.5, 0.5, "No data yet", horizontalalignment='center', verticalalignment='center')
        else:
            ax.plot(hist, linewidth=1.5)
            # show last and first value markers
            ax.scatter(len(hist)-1, hist[-1], s=20)
            ax.set_title(f"{COIN_DISPLAY.get(coin, coin)} - Last: ${hist[-1]:,.2f}")
            ax.set_xlabel("Updates (newest on right)")
            ax.set_ylabel(f"Price ({VS_CURRENCY.upper()})")
        self.canvases[coin].draw()

    def save_history_csv(self):
        """Save the current stored history to CSV file."""
        if all(len(v) == 0 for v in self.price_history.values()):
            messagebox.showinfo("No Data", "No price history to save yet.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save price history as CSV"
        )
        if not filepath:
            return
        # Construct rows: timestamp, coin1, coin2, ...
        # We'll align by index; if a coin is shorter, we leave blank.
        max_len = max(len(v) for v in self.price_history.values())
        # Convert deques to lists aligned to the right (most recent at end)
        lists = {coin: list(self.price_history[coin]) for coin in COINS}
        # We don't have per-price timestamps per coin (they share update timestamps), so use recorded timestamps.
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            header = ["timestamp"] + [COIN_DISPLAY.get(c, c) for c in COINS]
            writer.writerow(header)
            # Use recorded timestamps aligned to the end of lists
            # We'll use the timestamps deque (may be shorter)
            ts_list = list(self.timestamps)
            # If we have fewer timestamps than max_len, pad left with empty strings
            pad = max_len - len(ts_list)
            padded_ts = [""]*pad + ts_list
            for idx in range(max_len):
                row = []
                row.append(padded_ts[idx] if idx < len(padded_ts) else "")
                for coin in COINS:
                    hist = lists[coin]
                    # align to right
                    pad_coin = max_len - len(hist)
                    value = ""
                    if idx >= pad_coin:
                        value = hist[idx - pad_coin]
                    row.append(value)
                writer.writerow(row)
        messagebox.showinfo("Saved", f"Price history saved to:\n{filepath}")

    def clear_history(self):
        for coin in COINS:
            self.price_history[coin].clear()
        self.timestamps.clear()
        messagebox.showinfo("Cleared", "Stored price history has been cleared.")
        # refresh plots
        for coin in COINS:
            self._update_plot(coin)

def main():
    root = tk.Tk()
    app = CryptoTrackerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
