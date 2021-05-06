from sim import simulate
import config as conf
from plot import MultiPlot
from statistics import AvgStatistics
import numpy as np


def reset_parameters():
    conf.NBSS = 15
    conf.SPV = 100
    conf.BTH = conf.C * 0.8
    conf.TMAX = 20
    conf.F = 10


def multi_plot(stats, x, legend_values, xlabel, legend_label):
    MultiPlot(stats.avg_arrivals, xvalues=x, title="Arrivals", labels=legend_label, xlabel=xlabel).plot(legend_values)
    MultiPlot(stats.avg_loss, xvalues=x, title="Losses", labels=legend_label, xlabel=xlabel).plot(legend_values)
    MultiPlot(stats.avg_avg_wait, xvalues=x, title="Avg wait", labels=legend_label, xlabel=xlabel).plot(legend_values)
    MultiPlot(stats.avg_avg_ready, xvalues=x, title="Avg ready batteries", labels=legend_label, xlabel=xlabel).plot(
        legend_values)
    MultiPlot(stats.avg_cost, xvalues=x, title="Costs", ylabel="Euro per day", labels=legend_label, xlabel=xlabel).plot(
        legend_values)
    MultiPlot(stats.avg_saving, xvalues=x, title="Savings", ylabel="Euro per day", labels=legend_label,
              xlabel=xlabel).plot(legend_values)
    MultiPlot(stats.cost_per_service, xvalues=x, title="Cost per service", ylabel="Euro per service",
              labels=legend_label, xlabel=xlabel).plot(legend_values)


def plot_stats(stats, params, label):
    MultiPlot(stats.avg_arrivals, title="Arrivals", xvalues=label, labels=label).single_plot()
    MultiPlot(stats.avg_loss, title="Losses", xvalues=label, xlabel=params, labels=label).single_plot()
    MultiPlot(stats.avg_avg_wait, title="Waiting", xvalues=label, labels=label).single_plot()
    MultiPlot(stats.avg_avg_ready, title="Average ready", xvalues=label, labels=label).single_plot()
    MultiPlot(stats.avg_cost, title="Costs", xvalues=label, xlabel=params,
              ylabel="Euro per day", labels=label).single_plot()

    y = np.array((stats.avg_tot_consumption.tolist(), stats.avg_consumption.tolist(),
                  stats.avg_spv_consumption.tolist()))
    MultiPlot(y, title="Consumption", xlabel=params,
              ylabel="Energy per day [Wh/day]", xvalues=label).plot(["Tot", "Grid", "SPV"])

    MultiPlot(stats.avg_cost, stats.avg_loss_prob, title="Cost / prob loss").plot_cost_prob_loss(label)


if __name__ == "__main__":
    reset_parameters()

    # SPV / NBSS
    spv_list = list(range(10, 110, 10))
    nbss_list = list(range(10, 16, 1))
    stats_by_nbss = AvgStatistics(len(nbss_list), len(spv_list))
    stats_by_spv = AvgStatistics(r=len(spv_list))

    # F / TMAX
    f_list = list(range(1, conf.NBSS + 1))
    tmax_list = list(range(10, 60, 10)) + list(range(60, 360, 60))
    stats_by_tmaxf = AvgStatistics(len(tmax_list), len(f_list))
    stats_by_f = AvgStatistics(r=len(f_list))
    stats_by_Tmax = AvgStatistics(r=len(tmax_list))

    # BTH
    bth_list = [bth / 100 for bth in range(60, 95, 5)]
    stats_by_bth = AvgStatistics(r=len(bth_list))

    # ARRIVAL_COEFF
    arrival_list = [conf.arrival_rate, conf.arrival_rate_2, conf.arrival_rate_3]
    stats_by_arr_rate = AvgStatistics(r=len(arrival_list))

    # for spv in spv_list:
    #     for nbss in nbss_list:
    #         conf.SPV = spv
    #         conf.NBSS = nbss
    #         stats = simulate()
    #         print("-")
    #
    #         stats_by_nbss.compute_avg(stats, nbss_list.index(conf.NBSS), spv_list.index(conf.SPV))
    #
    # multi_plot(stats_by_nbss, spv_list, nbss_list, "SPV", "NBSS")

    # for spv in spv_list:
    #     conf.SPV = spv
    #     stats = simulate()
    #     print("-")
    #
    #     stats_by_spv.compute_avg(stats, spv_list.index(conf.SPV))
    #
    # plot_stats(stats_by_spv, "SPV", spv_list)

    # for bth in bth_list:
    #     conf.BTH = conf.C * bth
    #     stats = simulate()
    #     print("-")
    #
    #     stats_by_bth.compute_avg(stats, bth_list.index(bth))
    #
    # plot_stats(stats_by_bth, "Bth", bth_list)

    for tmax in tmax_list:
        for f in f_list:
            conf.TMAX = tmax
            conf.F = f
            stats = simulate()
            print("-")

            stats_by_tmaxf.compute_avg(stats, tmax_list.index(conf.TMAX), f_list.index(conf.F))

    multi_plot(stats_by_tmaxf, f_list, tmax_list, "F", "TMAX")

    # for f in f_list:
    #     conf.F = f
    #     stats = simulate()
    #     print("-")
    #
    #     stats_by_f.compute_avg(stats, f_list.index(conf.F))
    #
    # plot_stats(stats_by_f, "F", f_list)

    # for tmax in tmax_list:
    #     conf.TMAX = tmax
    #     stats = simulate()
    #     print("-")
    #
    #     stats_by_Tmax.compute_avg(stats, tmax_list.index(conf.TMAX))
    #
    # plot_stats(stats_by_Tmax, "TMAX", tmax_list)

    # for i in range(len(arrival_list)):
    #     conf.arrival_rate = arrival_list[i]
    #     stats = simulate()
    #     print("-")
    #
    #     stats_by_arr_rate.compute_avg(stats, i)
    #
    # plot_stats(stats_by_arr_rate, list(range(3)), ["3 peaks", "2 peaks", "Fixed coeff"])
