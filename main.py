from sim import simulate
import config as conf


def reset_parameters():
    conf.NBSS = 15
    conf.SPV = 100
    conf.B = 2 * conf.NBSS
    conf.TMAX = 20
    conf.F = conf.NBSS / 3


if __name__ == "__main__":
    reset_parameters()
    # SPV / NBSS
    spv_list = [15, 30, 100, 200, 400, 600, 800, 1000, 1200, 2000]
    nbss_list = list(range(5, 35, 5))
    # stats_by_nbss = AvgStatistics(len(spv_list), len(nbss_list))

    # F / TMAX
    f_list = range(1, 5)
    tmax_list = range(5, 40, 10)
    # stats_by_tmaxf = AvgStatistics(len(tmax_list), len(f_list))

    # BTH
    bth_list = range(int(conf.C / 2), conf.C, 1000)
    # stats_by_bth = AvgStatistics(r=len(bth_list))

    # for SPV in spv_list:
    #     for NBSS in nbss_list:
    for tmax in tmax_list:
        for f in f_list:
            # for BTH in bth_list:
            conf.TMAX = tmax
            conf.F = f
            stats = simulate()
            print("-")
