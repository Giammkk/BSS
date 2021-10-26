from plot import Plot, MultiPlot
import config as conf
import numpy as np
from data_manager import DatasetManager
from calendar import monthrange


class Statistics:
    def __init__(self):
        self.avg_ready = {i + 1: 0 for i in range(conf.SIM_LAST)}  # Average ready batteries
        self.last_update = 0

        self.arrivals = {i + 1: 0 for i in range(conf.SIM_LAST)}  # Daily arrivals
        self.wait_delay = {i + 1: 0 for i in range(conf.SIM_LAST)}  # Daily average waiting delay
        self.loss = {i + 1: 0 for i in range(conf.SIM_LAST)}  # Daily number of missed services
        self.avg_wait = {i + 1: 0 for i in range(conf.SIM_LAST)}  # Avg time for EV to wait for to have a full battery
        self.cost = {i + 1: 0 for i in range(conf.SIM_LAST)}  # Cost of charging batteries

        self.daily_arr = {i: 0 for i in range(24)}  # Average number of arrivals at each hour
        self.len_queue = {i + 1: 0 for i in range(conf.SIM_LAST)}  # Mean length of queue
        self.busy_sockets = {i + 1: 0 for i in range(conf.SIM_LAST)}
        self.consumption = {i + 1: 0 for i in range(conf.SIM_LAST)}
        self.loss_prob = {i + 1: 0 for i in range(conf.SIM_LAST)}
        self.spv_production = {i + 1: 0 for i in range(conf.SIM_LAST)}
        self.total_consumption = {i + 1: 0 for i in range(conf.SIM_LAST)}
        self.pb_integral = {}

        self.saving = {i + 1: 0 for i in range(conf.SIM_LAST)}
        self.net_cost = {i + 1: 0 for i in range(conf.SIM_LAST)}
        self.stored_energy = {i + 1: 0 for i in range(24 * conf.SIM_LAST)}

    def compute_daily_stats(self, day):
        self.avg_wait[day] = self.avg_wait[day] / self.arrivals[day]
        self.avg_ready[day] = self.avg_ready[day] / self.arrivals[day]
        self.len_queue[day] = self.len_queue[day] / (60 * 24)
        self.busy_sockets[day] = self.busy_sockets[day] / (60 * 24)
        self.loss_prob[day] = self.loss[day] / self.arrivals[day]
        self.net_cost[day] = self.cost[day] - self.saving[day]

    def plot_stats(self):
        Plot([i / conf.SIM_LAST for i in self.daily_arr.values()],
             title="Arrivals by hour", ylabel="# of vehicles").plot_by_hour()
        # Plot([i / conf.SIM_LAST for i in self.pb_integral.values()], title="Postponed by hour").plot_by_hour()

        Plot(self.arrivals.values(), title="Daily arrivals", ylabel="# of vehicles").plot_by_day()
        Plot(self.loss.values(), title="Daily losses").plot_by_day()
        # Plot(self.avg_wait.values(), title="Daily waiting").plot_by_day()
        # Plot(self.avg_ready.values(), title="Avg ready batteries").plot_by_day()
        # Plot(self.len_queue.values(), title="Avg queue length").plot_by_day()
        # Plot(self.busy_sockets.values(), title="Busy sockets").plot_by_day()
        # Plot(self.consumption.values(), title="Energy consumption", ylabel="Energy [Wh]").plot_by_day()
        Plot(self.cost.values(), title="Daily Cost", ylabel="Euro").plot_by_day()
        Plot(self.stored_energy.values(), range(len(self.stored_energy.values())), title="Surplus of energy", ylabel="Energy [Wh]").plot()

        y = np.array([list(self.total_consumption.values()), list(self.consumption.values()),
                      list(self.spv_production.values())])
        MultiPlot(y, xvalues=range(conf.SIM_LAST), title="Consumption", ylabel="Energy [Wh]").plot(
            ["Tot", "Grid", "SPV"])

        # if conf.PV_SET:
        #     Plot(self.cost.values(), title="Daily cost with PV").plot_by_day()
        # else:
        #     Plot(self.cost.values(), title="Daily cost without PV").plot_by_day()

        # prob_losses = [i / j for i, j in zip(self.loss.values(), self.arrivals.values())]
        # Plot(self.cost.values(), prob_losses, title="Cost / prob losses").scatter()

        dm = DatasetManager()
        pv_daily = {i + 1: 0 for i in range(365)}
        ind = 0
        for m in range(1, 13):
            for d in range(1, monthrange(2019, m)[1] + 1):
                ind += 1
                for h in range(24):
                    pv_daily[ind] += dm.get_PV_power(m, d, h, 1)
        pv_daily = list(pv_daily.values())  # [152:213]
        y = np.array([list(self.spv_production.values()), pv_daily])
        # for i in range(y.shape[1]):
        #     print(y[0, i]-y[1, i])
        # MultiPlot(y, xvalues=range(conf.SIM_LAST), title="PV analysis", ylabel="Energy [Wh]").plot(["Cons", "Prod"])

        y = np.array([list(self.cost.values()), list(self.net_cost.values()),
                      list(self.saving.values())])
        MultiPlot(y, xvalues=range(conf.SIM_LAST), title="Daily Costs", ylabel="Euro").plot(["Tot", "Net", "Saving"])


class AvgStatistics:
    def __init__(self, r=1, c=1):
        self.avg_arrivals = np.zeros((r, c))
        self.avg_loss = np.zeros((r, c))
        self.avg_cost = np.zeros((r, c))
        self.avg_avg_ready = np.zeros((r, c))
        self.avg_avg_wait = np.zeros((r, c))
        self.avg_loss_prob = np.zeros((r, c))
        self.avg_consumption = np.zeros((r, c))
        self.avg_tot_consumption = np.zeros((r, c))
        self.avg_spv_consumption = np.zeros((r, c))
        self.avg_saving = np.zeros((r, c))
        self.cost_per_service = np.zeros((r, c))
        self.avg_net_cost = np.zeros((r, c))

    def compute_avg(self, stats, r=1, c=0):
        self.avg_arrivals[r][c] = np.mean(list(stats.arrivals.values()))
        self.avg_loss[r][c] = np.mean(list(stats.loss.values()))
        self.avg_avg_wait[r][c] = np.mean(list(stats.avg_wait.values()))
        self.avg_avg_ready[r][c] = np.mean(list(stats.avg_ready.values()))
        self.avg_cost[r][c] = np.mean(list(stats.cost.values()))
        self.avg_loss_prob[r][c] = np.mean(list(stats.loss_prob.values()))
        self.avg_consumption[r][c] = np.mean(list(stats.consumption.values()))
        self.avg_saving[r][c] = np.mean(list(stats.saving.values()))
        self.cost_per_service[r][c] = self.avg_cost[r][c] / (self.avg_arrivals[r][c] - self.avg_loss[r][c])
        self.avg_net_cost[r][c] = self.avg_cost[r][c] - self.avg_saving[r][c]
