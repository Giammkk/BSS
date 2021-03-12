from plot import Plot
import config as conf
import numpy as np


class Statistics:
    def __init__(self):
        self.avg_ready = {i + 1: 0 for i in range(365)}  # Average ready batteries
        self.last_update = 0

        self.arrivals = {i + 1: 0 for i in range(365)}  # Daily arrivals
        self.wait_delay = {i + 1: 0 for i in range(365)}  # Daily average waiting delay
        self.loss = {i + 1: 0 for i in range(365)}  # Daily number of missed services
        self.avg_wait = {i + 1: 0 for i in range(365)}  # Avg time for EV to wait for to have a full battery
        self.cost = {i + 1: 0 for i in range(365)}  # Cost of charging batteries

        self.daily_arr = {i: 0 for i in range(24)}  # Average number of arrivals at each hour
        self.len_queue = {i + 1: 0 for i in range(365)}  # Mean length of queue
        self.busy_sockets = {i + 1: 0 for i in range(365)}
        self.consumption = {i + 1: 0 for i in range(365)}
        self.loss_prob = {i + 1: 0 for i in range(365)}

    def compute_daily_stats(self, day):
        self.avg_wait[day] = self.avg_wait[day] / self.arrivals[day]
        self.avg_ready[day] = self.avg_ready[day] / self.arrivals[day]
        self.len_queue[day] = self.len_queue[day] / (60 * 24)
        self.busy_sockets[day] = self.busy_sockets[day] / (60 * 24)
        self.loss_prob[day] = self.loss[day] / self.arrivals[day]

    def plot_stats(self):
        Plot([i / 365 for i in self.daily_arr.values()], title="Arrivals by hour").plot_by_hour()

        Plot(self.arrivals.values(), title="Daily arrivals").plot_by_day()
        Plot(self.loss.values(), title="Daily losses").plot_by_day()
        Plot(self.avg_wait.values(), title="Daily waiting").plot_by_day()
        Plot(self.avg_ready.values(), title="Avg ready batteries").plot_by_day()
        Plot(self.len_queue.values(), title="Avg queue length").plot_by_day()
        Plot(self.busy_sockets.values(), title="Busy sockets").plot_by_day()
        Plot(self.consumption.values(), title="Power consumption").plot_by_day()

        if conf.PV_SET:
            Plot(self.cost.values(), title="Daily cost with PV").plot_by_day()
        else:
            Plot(self.cost.values(), title="Daily cost without PV").plot_by_day()

        # prob_losses = list(self.loss.values()) / list(self.arrivals.values())
        prob_losses = [i / j for i, j in zip(self.loss.values(), self.arrivals.values())]
        Plot(self.cost.values(), prob_losses, title="Cost / prob losses").scatter()


class AvgStatistics:
    def __init__(self, r=1, c=1):
        self.avg_arrivals = np.zeros((r, c))
        self.avg_loss = np.zeros((r, c))
        self.avg_cost = np.zeros((r, c))
        self.avg_avg_ready = np.zeros((r, c))
        self.avg_avg_wait = np.zeros((r, c))
