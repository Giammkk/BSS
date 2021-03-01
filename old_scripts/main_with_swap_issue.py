import random
from queue import PriorityQueue
from calendar import monthrange
from plot import Plot, MultiPlot
import numpy as np
from data_manager import DatasetManager
from components import ShareGlobals, Socket, Battery, EV, BSS
import warnings
import sys

## Global variables ##
SIM_TIME = 60
DAY = 1  # Day of the simulation (from 1 to 365)
HOUR = 0  # Current hour (from 0 to 23)
CURRENT_DAY = 1  # Current day (from 1 to 30/31/28)
MONTH = 1  # Current month in the simulation
C = 40000  # Battery capacity
TOL = 0.98  # Percentage of charge to be full
NBSS = 15  # Max number of chargers
B = 2 * NBSS  # Max number of batteries (charging + queue)
WMAX = 15  # Max waiting time for EV
BTH = 38000  # Minimum charge level
CR = int(C / 2)  # Charging rate per hour
PV_SET = 1  # Indicator of presence of a PV in the BSS
SPV = 100  # Nominal capacity of one PV (kW) * number of panels
F = 0  # NBSS/3              # Fraction of batteries whose charge cannot be postponed
TMAX = 20  # Maximum time by which the charge process can be postponed
HIGH_DEMAND = False  # High demand indicator

dm = DatasetManager()
pv_production = dm.get_pv_data()


## Statistics ##
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


class AvgStatistics:
    def __init__(self, r=1, c=1):
        self.avg_arrivals = np.zeros((r, c))
        self.avg_loss = np.zeros((r, c))
        self.avg_cost = np.zeros((r, c))
        self.avg_avg_ready = np.zeros((r, c))
        self.avg_avg_wait = np.zeros((r, c))


def next_arrival():
    arrival_coeff = [30, 30, 30, 30, 20, 15, 13, 10, 5, 8, 15, 15, 3,  # 0->13
                     4, 10, 13, 15, 15, 2, 5, 15, 18, 20, 25]  # 14->23
    return random.expovariate(1 / arrival_coeff[HOUR])


def arrival(time, ev, FES, queue, bss, stats):
    """
    An EV is arrived at the BSS.
    """
    sockets = bss.sockets
    update_all_batteries(time, queue, bss, stats, 0)
    next_ready = 60 * C / CR  # Max time to charge a battery (2h)
    can_wait = ev.can_wait
    resume_charge = 0
    flag = 0
    battery_booked = None

    stats.avg_ready[DAY] += bss.ready_batteries

    if can_wait == 1:  # can_wait=0: EV has already arrived and it's waiting

        stats.daily_arr[HOUR] += 1
        stats.arrivals[DAY] += 1

        interarrival = next_arrival()  # Schedule the next arrival
        FES.put((time + interarrival, "2_arrival", EV(random.gauss(8000, 1000), 0)))

        for socket in sockets:  # Look for a charging battery not booked yet
            if socket.busy and not socket.battery.booked:

                if socket.battery.time_to_ready(time, HIGH_DEMAND, DAY, HOUR) < next_ready:
                    next_ready = socket.battery.time_to_ready(time, HIGH_DEMAND, DAY, HOUR)
                    battery_booked = socket.battery  # Book a battery if ready_batteries is 0
                    socket_booked = socket

            else:
                flag = 1

        if not flag:
            if (next_ready + time, "0_batteryavailable", None) not in FES.queue:
                FES.put((next_ready + time, "0_batteryavailable", None))

    if bss.ready_batteries > 0 and can_wait != -1:
        bss.ready_batteries -= 1

        if can_wait == 1:
            battery = ev.battery
        else:
            try:
                ev = queue.pop(0)
            except:
                print("empty queue", time)
                sys.exit()
            battery = ev.battery

        for socket in sockets:  # Plug battery in the first free socket
            if not socket.busy:
                socket.plug_battery(battery, time)
                break

    elif next_ready <= WMAX and can_wait == 1 and battery_booked and len(queue) <= NBSS:
        # print(DAY, next_ready)
        stats.avg_wait[DAY] += next_ready
        battery_booked.booked = True
        socket_booked.is_charging = True  # Reactivate charging if battery has been booked
        queue.append(ev)
        ev.can_wait = 0
        ev.service_time = next_ready + time
        FES.put((next_ready + time, "2_arrival", ev))

    elif can_wait == -1:
        # print("can wait -1")
        pass
    else:
        stats.loss[DAY] += 1

    if not HIGH_DEMAND and F > 0:
        v = bss.postpone_charge(time, DAY, dm, MONTH, CURRENT_DAY, HOUR,
                                SPV, NBSS)
        if v:
            resume_charge = 1
    return resume_charge


## Departure ##
def battery_available(time, FES, queue, bss, stats):
    """
    One of the batteries is fully charged.
    """
    sockets = bss.sockets
    price = dm.get_prices_electricity(MONTH, DAY, HOUR)
    next_ready = 60 * C / CR
    resume_charge = 0

    stats.len_queue[DAY] += len(queue) * (time - stats.last_update)
    stats.busy_sockets[DAY] += sum([s.busy for s in sockets]) * (time - stats.last_update)

    # print(HOUR, DAY)
    PVpower = 0
    if PV_SET:
        PVpower = dm.get_PV_power(MONTH, CURRENT_DAY, HOUR, SPV, NBSS)
        # Divide the energy produced by the PVs by the active sockets
        try:  # Handle division by zero
            PVpower /= sum([s.is_charging * s.busy for s in sockets])
        except:
            pass

    for socket in sockets:
        if socket.busy:
            if socket.is_charging:
                cost, power = socket.battery.update_charge(time, PVpower, price)
                stats.cost[DAY] += cost
                stats.consumption[DAY] += power

            if HIGH_DEMAND and socket.battery.charge >= BTH * TOL:
                socket.unplug_battery()
                bss.ready_batteries += 1

                if queue:
                    ev = queue.pop(0)
                    socket.plug_battery(ev.battery, time)
                    bss.ready_batteries -= 1
                    ev.can_wait = -1

            if not HIGH_DEMAND and socket.battery.charge >= C * TOL:
                socket.unplug_battery()
                bss.ready_batteries += 1

                if queue:
                    ev = queue.pop(0)
                    socket.plug_battery(ev.battery, time)
                    bss.ready_batteries -= 1
                    ev.can_wait = -1

    for socket in sockets:
        if socket.busy:
            next_ready = min(socket.battery.time_to_ready(time, HIGH_DEMAND, DAY, HOUR), next_ready)

    if (next_ready + time, "0_batteryavailable", None) not in FES.queue:
        FES.put((next_ready + time, "0_batteryavailable", None))

    stats.last_update = time

    if not HIGH_DEMAND and F > 0:
        v = bss.postpone_charge(time, DAY, dm, MONTH, CURRENT_DAY, HOUR,
                                SPV, NBSS)
        if v:
            resume_charge = 1
    return resume_charge


## Change Hour ##
def update_all_batteries(time, queue, bss, stats, flag):
    """
    Since every hour electricity price and PV production change, the charge of
    the batteries must be update with the right parameters.
    """
    sockets = bss.sockets
    price = dm.get_prices_electricity(MONTH, DAY, HOUR)
    check_high_demand(HOUR)

    stats.len_queue[DAY] += len(queue) * (time - stats.last_update)
    stats.busy_sockets[DAY] += sum([s.busy for s in sockets]) * (time - stats.last_update)

    PVpower = 0
    if PV_SET:
        PVpower = dm.get_PV_power(MONTH, CURRENT_DAY, HOUR, SPV, NBSS)

    for socket in sockets:
        if socket.busy and socket.is_charging:
            cost, power = socket.battery.update_charge(time, PVpower, price)
            stats.cost[DAY] += cost
            stats.consumption[DAY] += power

            if HIGH_DEMAND and socket.battery.charge >= BTH * TOL:
                socket.unplug_battery()
                bss.ready_batteries += 1

            if not HIGH_DEMAND and socket.battery.charge >= C * TOL:
                socket.unplug_battery()
                bss.ready_batteries += 1

    stats.last_update = time
    if flag:
        bss.resume_charge(time)
    return


def check_high_demand(hour):
    global HIGH_DEMAND

    if hour == 8 or (hour >= 12 and hour < 15) or (hour >= 18 and hour <= 19):
        HIGH_DEMAND = True
        return HIGH_DEMAND
    else:
        HIGH_DEMAND = False
        return HIGH_DEMAND


def simulation(F, TMAX, stats_by_bth, f_list, tmax_list):
    global HOUR, DAY, CURRENT_DAY, MONTH
    sg = ShareGlobals()
    sg.set_globals(C, CR, BTH, PV_SET, TOL, F, TMAX)
    sg.check()
    print("SPV: ", SPV, "| NBSS:", NBSS)
    random.seed(4)
    time = 0

    FES = PriorityQueue()
    # Schedule the first arrival at t=0
    FES.put((0, "2_arrival", EV(random.gauss(8000, 1000), 0)))

    queue = list()
    bss = BSS()
    sockets = list()
    for i in range(NBSS):
        s = Socket()
        s.bss = bss
        s.plug_battery(Battery(charge=random.gauss(8000, 1000)), time)
        sockets.append(s)
    bss.sockets = sockets
    bss.n_charging = len(sockets)
    bss.n_sockets = len(sockets)

    stats = Statistics()

    previous_time = -1
    MONTH = 1
    DAY = 1

    while MONTH <= 12:
        number_of_days = monthrange(2019, MONTH)[1]
        CURRENT_DAY = 1

        while CURRENT_DAY <= number_of_days:
            # pri1nt(f"{CURRENT_DAY}/{MONTH}")
            HOUR = 0

            while HOUR < 24:

                FES.put((60 * (HOUR + 1) + ((DAY - 1) * 24 * 60), "1_changehour", None))
                # print(f"{HOUR}")
                rc_flag = 0
                while time < SIM_TIME * (HOUR + 1) + ((DAY - 1) * 24 * 60):

                    (time, event, ev) = FES.get()
                    if ev:
                        ev.arrival_time = time

                    # Check if time always increases
                    if previous_time > time:
                        raise Exception("Error.")
                    else:
                        previous_time = time

                    if event == "2_arrival":
                        resume_charge = arrival(time, ev, FES, queue, bss, stats)

                    elif event == "1_changehour":
                        update_all_batteries(time, queue, bss, stats, rc_flag)

                    elif event == "0_batteryavailable":
                        resume_charge = battery_available(time, FES, queue, bss, stats)

                    if resume_charge:
                        rc_flag = 1

                HOUR += 1

            stats.avg_wait[DAY] = stats.avg_wait[DAY] / stats.arrivals[DAY]
            stats.avg_ready[DAY] = stats.avg_ready[DAY] / stats.arrivals[DAY]
            stats.len_queue[DAY] = stats.len_queue[DAY] / (60 * 24)
            stats.busy_sockets[DAY] = stats.busy_sockets[DAY] / (60 * 24)

            DAY += 1
            CURRENT_DAY += 1

        MONTH += 1

    # r = spv_list.index(SPV)
    # c = nbss_list.index(NBSS)
    # stats_by_nbss.avg_arrivals[r][c] = np.mean(list(stats.arrivals.values()))
    # stats_by_nbss.avg_loss[r][c] = np.mean(list(stats.loss.values()))
    # stats_by_nbss.avg_avg_wait[r][c] = np.mean(list(stats.avg_wait.values()))
    # stats_by_nbss.avg_avg_ready[r][c] = np.mean(list(stats.avg_ready.values()))
    # stats_by_nbss.avg_cost[r][c] = np.mean(list(stats.cost.values()))

    r = tmax_list.index(TMAX)
    c = f_list.index(F)
    stats_by_tmaxf.avg_arrivals[r][c] = np.mean(list(stats.arrivals.values()))
    stats_by_tmaxf.avg_loss[r][c] = np.mean(list(stats.loss.values()))
    stats_by_tmaxf.avg_avg_wait[r][c] = np.mean(list(stats.avg_wait.values()))
    stats_by_tmaxf.avg_avg_ready[r][c] = np.mean(list(stats.avg_ready.values()))
    stats_by_tmaxf.avg_cost[r][c] = np.mean(list(stats.cost.values()))

    # r = param_list.index(BTH)
    # stats_by_bth.avg_arrivals[r] = np.mean(list(stats.arrivals.values()))
    # stats_by_bth.avg_loss[r] = np.mean(list(stats.loss.values()))
    # stats_by_bth.avg_avg_wait[r] = np.mean(list(stats.avg_wait.values()))
    # stats_by_bth.avg_avg_ready[r] = np.mean(list(stats.avg_ready.values()))
    # stats_by_bth.avg_cost[r] = np.mean(list(stats.cost.values()))

    print("Mean arrivals: %f" % (np.mean(list(stats.arrivals.values()))))
    print("Mean loss: %f" % (np.mean(list(stats.loss.values()))))
    print("Mean cost: %f" % (np.mean(list(stats.cost.values()))))
    print("-")

    return stats


## Main ##
if __name__ == '__main__':

    warnings.filterwarnings("ignore")

    # SPV / NBSS
    spv_list = [15, 30, 100, 200, 400, 600, 800, 1000, 1200, 2000]
    nbss_list = list(range(5, 35, 5))
    stats_by_nbss = AvgStatistics(len(spv_list), len(nbss_list))

    # F / TMAX
    f_list = range(1, NBSS + 1)
    tmax_list = range(5, 30, 5)
    stats_by_tmaxf = AvgStatistics(len(tmax_list), len(f_list))

    # BTH
    bth_list = range(int(C / 2), C, 500)
    stats_by_bth = AvgStatistics(r=len(bth_list))

    if PV_SET:
        print("SPV: ", SPV)

    # for SPV in spv_list:
    #     for NBSS in nbss_list:
    for TMAX in tmax_list:
        for F in f_list:
            # for BTH in bth_list:
            simulation(F, TMAX, stats_by_bth, f_list, tmax_list)

    # %% Show statistics ##

    # MultiPlot(stats_by_nbss.avg_arrivals, title="Arrivals", labels=spv_list).plot()
    # MultiPlot(stats_by_nbss.avg_loss, title="Losses", labels=spv_list).plot()
    # MultiPlot(stats_by_nbss.avg_avg_wait, title="Waiting", labels=spv_list).plot()
    # MultiPlot(stats_by_nbss.avg_avg_ready, title="Average ready", labels=spv_list).plot()
    # MultiPlot(stats_by_nbss.avg_cost, title="Costs", labels=spv_list).plot()

    MultiPlot(stats_by_tmaxf.avg_arrivals.T, title="Arrivals", labels=f_list).plot("TMAX")
    MultiPlot(stats_by_tmaxf.avg_loss.T, title="Losses", labels=f_list).plot("TMAX")
    MultiPlot(stats_by_tmaxf.avg_avg_wait.T, title="Waiting", labels=f_list).plot("TMAX")
    MultiPlot(stats_by_tmaxf.avg_avg_ready.T, title="Average ready", labels=f_list).plot("TMAX")
    MultiPlot(stats_by_tmaxf.avg_cost.T, title="Costs", labels=f_list).plot("TMAX")

    # MultiPlot(stats_by_bth.avg_arrivals, title="Arrivals", bth_list, xlabel="BTH").single_plot()
    # MultiPlot(stats_by_bth.avg_loss, title="Losses", bth_list, xlabel="BTH").single_plot()
    # MultiPlot(stats_by_bth.avg_avg_wait, title="Waiting", bth_list, xlabel="BTH").single_plot()
    # MultiPlot(stats_by_bth.avg_avg_ready, title="Average ready", bth_list, xlabel="BTH").single_plot()
    # MultiPlot(stats_by_bth.avg_cost, title="Costs", bth_list, xlabel="BTH").single_plot()
