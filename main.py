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
    conf.F = 2 * conf.NBSS / 3


def plot_tmaxf(stats_by_tmaxf):
    MultiPlot(stats_by_tmaxf.avg_arrivals.T, title="Arrivals", labels=f_list).plot("TMAX")
    MultiPlot(stats_by_tmaxf.avg_loss.T, title="Losses", labels=f_list).plot("TMAX")
    MultiPlot(stats_by_tmaxf.avg_avg_wait.T, title="Waiting", labels=f_list).plot("TMAX")
    MultiPlot(stats_by_tmaxf.avg_avg_ready.T, title="Average ready", labels=f_list).plot("TMAX")
    MultiPlot(stats_by_tmaxf.avg_cost.T, title="Costs", labels=f_list).plot("TMAX")


def plot_nbss(stats_by_nbss, label):
    MultiPlot(stats_by_nbss.avg_arrivals, title="Arrivals", labels=spv_list).plot()
    MultiPlot(stats_by_nbss.avg_loss, title="Losses", labels=spv_list).plot()
    MultiPlot(stats_by_nbss.avg_avg_wait, title="Waiting", labels=spv_list).plot()
    MultiPlot(stats_by_nbss.avg_avg_ready, title="Average ready", labels=spv_list).plot()
    MultiPlot(stats_by_nbss.avg_cost, title="Costs", labels=spv_list).plot()
    # MultiPlot(stats_by_nbss.avg_cost, stats_by_nbss.avg_loss_prob, title="Cost / prob loss").plot_cost_prob_loss(label)


def plot_stats(stats, params, label):
    MultiPlot(stats.avg_arrivals, title="Arrivals", labels=params, xlabel=label).single_plot()
    MultiPlot(stats.avg_loss, title="Losses", labels=params, xlabel=label).single_plot()
    MultiPlot(stats.avg_avg_wait, title="Waiting", labels=params, xlabel=label).single_plot()
    MultiPlot(stats.avg_avg_ready, title="Average ready", labels=params, xlabel=label).single_plot()
    MultiPlot(stats.avg_cost, title="Costs", labels=params, xlabel=label).single_plot()
    MultiPlot(stats.avg_cost, stats.avg_loss_prob, title="Cost / prob loss").plot_cost_prob_loss(params)


if __name__ == "__main__":
    reset_parameters()

    # SPV / NBSS
    spv_list = list(range(0, 40, 5))
    spv_list.append(100)
    nbss_list = list(range(5, 15, 5))
    stats_by_nbss = AvgStatistics(len(nbss_list), len(spv_list))
    stats_by_spv = AvgStatistics(r=len(spv_list))

    # F / TMAX
    f_list = range(1, 14)
    tmax_list = range(60, 60 * 7, 60)
    stats_by_tmaxf = AvgStatistics(len(tmax_list), len(f_list))
    stats_by_f = AvgStatistics(r=len(f_list))
    stats_by_Tmax = AvgStatistics(r=len(tmax_list))

    # BTH
    bth_list = range(int(conf.C / 2), conf.C, 1000)
    stats_by_bth = AvgStatistics(r=len(bth_list))

    # for spv in spv_list:
    #     for nbss in nbss_list:
    #         conf.SPV = spv
    #         conf.NBSS = nbss
    #         stats = simulate()
    #         print("-")
    #
    #         stats_by_nbss.compute_avg(stats, nbss_list.index(conf.NBSS), spv_list.index(conf.SPV))
    #
    # plot_nbss(stats_by_nbss, spv_list)

    # for spv in spv_list:
    #     conf.SPV = spv
    #     stats = simulate()
    #     print("-")
    #
    #     stats_by_spv.compute_avg(stats, spv_list.index(conf.SPV))
    #
    # plot_stats(stats_by_spv, spv_list, "SPV")

    # for bth in bth_list:
    #     conf.BTH = bth
    #     stats = simulate()
    #     print("-")
    #
    #     stats_by_bth.compute_avg(stats, bth_list.index(conf.BTH))
    #
    # plot_stats(stats_by_bth, bth_list, "Bth")

    # for tmax in tmax_list:
    #     for f in f_list:
    #         conf.TMAX = tmax
    #         conf.F = f
    #         stats = simulate()
    #         print("-")
    #
    #         stats_by_tmaxf.compute_avg(stats, tmax_list.index(conf.TMAX), f_list.index(conf.F))
    #
    # plot_tmaxf(stats_by_tmaxf)

    # for f in f_list:
    #     conf.F = f
    #     stats = simulate()
    #     print("-")
    #
    #     stats_by_f.compute_avg(stats, f_list.index(conf.F))
    #
    # plot_stats(stats_by_f, f_list, "F")

    for tmax in tmax_list:
        conf.TMAX = tmax
        stats = simulate()
        print("-")

        stats_by_Tmax.compute_avg(stats, tmax_list.index(conf.TMAX))

    plot_stats(stats_by_Tmax, tmax_list, "TMAX")
