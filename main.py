from sim import simulate
import config as conf
from plot import MultiPlot
from statistics import AvgStatistics
import numpy as np


def reset_parameters():
    conf.NBSS = 15
    conf.SPV = 100
    conf.BTH = 38000
    conf.TMAX = 20
    conf.F = conf.NBSS / 3


def plot_tmaxf(stats_by_tmaxf):
    MultiPlot(stats_by_tmaxf.avg_arrivals.T, title="Arrivals", labels=f_list).plot("TMAX")
    MultiPlot(stats_by_tmaxf.avg_loss.T, title="Losses", labels=f_list).plot("TMAX")
    MultiPlot(stats_by_tmaxf.avg_avg_wait.T, title="Waiting", labels=f_list).plot("TMAX")
    MultiPlot(stats_by_tmaxf.avg_avg_ready.T, title="Average ready", labels=f_list).plot("TMAX")
    MultiPlot(stats_by_tmaxf.avg_cost.T, title="Costs", labels=f_list).plot("TMAX")

def plot_nbss(stats_by_nbss):
    MultiPlot(stats_by_nbss.avg_arrivals, title="Arrivals", labels=spv_list).plot()
    MultiPlot(stats_by_nbss.avg_loss, title="Losses", labels=spv_list).plot()
    MultiPlot(stats_by_nbss.avg_avg_wait, title="Waiting", labels=spv_list).plot()
    MultiPlot(stats_by_nbss.avg_avg_ready, title="Average ready", labels=spv_list).plot()
    MultiPlot(stats_by_nbss.avg_cost, title="Costs", labels=spv_list).plot()


if __name__ == "__main__":
    reset_parameters()

    # SPV / NBSS
    spv_list = [15, 30, 100, 200, 400, 600, 800, 1000, 1200, 2000]
    nbss_list = list(range(5, 35, 5))
    stats_by_nbss = AvgStatistics(len(spv_list), len(nbss_list))

    # F / TMAX
    f_list = range(1, 14)
    tmax_list = range(5, 60, 10)
    stats_by_tmaxf = AvgStatistics(len(tmax_list), len(f_list))

    # BTH
    bth_list = range(int(conf.C / 2), conf.C, 1000)
    # stats_by_bth = AvgStatistics(r=len(bth_list))

    for spv in spv_list:
        for nbss in nbss_list:
            conf.SPV = spv
            conf.NBSS = nbss
            stats = simulate()
            print("-")

            r = spv_list.index(conf.SPV)
            c = nbss_list.index(conf.NBSS)
            stats_by_nbss.avg_arrivals[r][c] = np.mean(list(stats.arrivals.values()))
            stats_by_nbss.avg_loss[r][c] = np.mean(list(stats.loss.values()))
            stats_by_nbss.avg_avg_wait[r][c] = np.mean(list(stats.avg_wait.values()))
            stats_by_nbss.avg_avg_ready[r][c] = np.mean(list(stats.avg_ready.values()))
            stats_by_nbss.avg_cost[r][c] = np.mean(list(stats.cost.values()))

    plot_nbss(stats_by_nbss)

    # for bth in bth_list:
    #     conf.BTH = bth
    # ...

    # for tmax in tmax_list:
    #     for f in f_list:
    #         conf.TMAX = tmax
    #         conf.F = f
    #         stats = simulate()
    #         print("-")
    #
    #         r = tmax_list.index(conf.TMAX)
    #         c = f_list.index(conf.F)
    #         stats_by_tmaxf.avg_arrivals[r][c] = np.mean(list(stats.arrivals.values()))
    #         stats_by_tmaxf.avg_loss[r][c] = np.mean(list(stats.loss.values()))
    #         stats_by_tmaxf.avg_avg_wait[r][c] = np.mean(list(stats.avg_wait.values()))
    #         stats_by_tmaxf.avg_avg_ready[r][c] = np.mean(list(stats.avg_ready.values()))
    #         stats_by_tmaxf.avg_cost[r][c] = np.mean(list(stats.cost.values()))
    #
    # plot_tmaxf(stats_by_tmaxf)
