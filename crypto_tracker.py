import requests
import tkinter as tk
from tkinter import messagebox
import threading
import time
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ================= CONFIGURATION =================

REFRESH_INTERVAL = 2  # seconds
MAX_POINTS = 60       # points on graph

COINS = {
    "Bitcoin": "BTCUSDT",
    "Ethereum": "ETHUSDT",
    "Solana": "SOLUSDT"
}

ALERTS = {
    "Bitcoin": None,
    "Ethereum": None,
    "Solana": None
}

# =================================================


def fetch_price(symbol):
    """Fetch price from Binance API"""
    url = "https://api.binance.com/api/v3/ticker/price"
    params = {"symbol": symbol}
    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    return float(response.json()["price"])


class CryptoTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Live Crypto Tracker (Binance)")
        self.root.geometry("900x700")

        self.price_history = {
            coin: deque(maxlen=MAX_POINTS) for coin in COINS
        }

        self.price_labels = {}
        self.alert_entries = {}

        self.build_ui()
        self.start_updating()

    def build_ui(self):
        title = tk.Label(self.root, text="LIVE CRYPTO TRACKER", font=("Arial", 18, "bold"))
        title.pack(pady=10)

        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # LEFT PANEL (Prices & Alerts)
        left = tk.Frame(self.main_frame)
        left.pack(side=tk.LEFT, padx=10)

        for coin in COINS:
            frame = tk.LabelFrame(left, text=coin, padx=10, pady=10)
            frame.pack(fill=tk.X, pady=5)

            price_label = tk.Label(frame, text="Loading...", font=("Arial", 14))
            price_label.pack()
            self.price_labels[coin] = price_label

            alert_entry = tk.Entry(frame)
            alert_entry.pack(pady=5)
            self.alert_entries[coin] = alert_entry

            set_btn = tk.Button(
                frame,
                text="Set Alert (USD)",
                command=lambda c=coin: self.set_alert(c)
            )
            set_btn.pack()

        # RIGHT PANEL (Graphs)
        right = tk.Frame(self.main_frame)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.fig, self.axes = plt.subplots(len(COINS), 1, figsize=(6, 6))
        if len(COINS) == 1:
            self.axes = [self.axes]

        for ax, coin in zip(self.axes, COINS):
            ax.set_title(f"{coin} Price (USD)")
            ax.set_ylabel("USD")

        for ax in self.axes:
            ax.grid(True, linestyle="--", alpha=0.3)

        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def set_alert(self, coin):
        value = self.alert_entries[coin].get()
        try:
            ALERTS[coin] = float(value)
            messagebox.showinfo("Alert Set", f"{coin} alert set at ${value}")
        except ValueError:
            messagebox.showerror("Invalid Input", "Enter a valid number")

    def start_updating(self):
        threading.Thread(target=self.update_loop, daemon=True).start()

    def update_loop(self):
        while True:
            for coin, symbol in COINS.items():
                try:
                    price = fetch_price(symbol)
                    self.price_history[coin].append(price)

                    self.root.after(
                        0,
                        lambda c=coin, p=price: self.price_labels[c].config(
                            text=f"${p:,.2f}"
                        )
                    )

                    if ALERTS[coin] and price >= ALERTS[coin]:
                        self.root.after(
                            0,
                            lambda c=coin: messagebox.showinfo(
                                "Price Alert",
                                f"{c} reached alert price!"
                            )
                        )
                        ALERTS[coin] = None

                except Exception as e:
                    print("Error:", e)

            self.root.after(0, self.update_graphs)
            time.sleep(REFRESH_INTERVAL)

    def update_graphs(self):
        for ax, coin in zip(self.axes, COINS):
            ax.plot(self.price_history[coin])
            ax.set_title(f"{coin} Price (USD)")
            ax.set_ylabel("USD")

        self.canvas.draw()


def main():
    root = tk.Tk()
    app = CryptoTrackerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
