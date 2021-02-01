import random
from queue import PriorityQueue
from calendar import monthrange
from plot import Plot, MultiPlot
import numpy as np
from data_manager import DatasetManager
from components import ShareGlobals, Socket, Battery, EV, BSS
import warnings
import sys

random.seed(4)

## Global variables ##
SIM_TIME = 60*24*365
DAY = 1                 # Day of the simulation (from 1 to 365)
HOUR = 0                # Current hour (from 0 to 23)
CURRENT_DAY = 1         # Current day (from 1 to 30/31/28)
MONTH = 1               # Current month in the simulation
C = 40000               # Battery capacity
TOL = 0.98              # Percentage of charge to be full
NBSS = 15               # Max number of chargers
B = 2*NBSS              # Max number of batteries (charging + queue)
WMAX = 15               # Max waiting time for EV
BTH = 38000             # Minimum charge level
CR = int(C/2)           # Charging rate per hour
PV_SET = 1              # Indicator of presence of a PV in the BSS
SPV = 100               # Nominal capacity of one PV (kW) * number of panels
F = NBSS/3              # Fraction of batteries whose charge cannot be postponed
TMAX = 20               # Maximum time by which the charge process can be postponed
HIGH_DEMAND = False     # High demand indicator

dm = DatasetManager()
pv_production = dm.get_pv_data()

## Statistics ##
class Statistics:

    def __init__(self):
        self.avg_ready = {i+1:0 for i in range(365)} # Average ready batteries
        self.last_update = 0

        self.arrivals = {i+1:0 for i in range(365)} # Daily arrivals
        self.wait_delay = {i+1:0 for i in range(365)} # Daily average waiting delay
        self.loss = {i+1:0 for i in range(365)} # Daily number of missed services
        self.avg_wait = {i+1:0 for i in range(365)} # Avg time for EV to wait for to have a full battery
        self.cost = {i+1:0 for i in range(365)} # Cost of charging batteries

        self.daily_arr = {i:0 for i in range(24)} # Average number of arrivals at each hour
        self.len_queue = {i+1:0 for i in range(365)} # Mean length of queue
        self.busy_sockets = {i+1:0 for i in range(365)}
        self.consumption = {i+1:0 for i in range(365)}
        self.loss_prob = {i+1:0 for i in range(365)}


def next_arrival():
    arrival_coeff = [30, 30, 30, 30, 20, 15, 13, 10, 5, 8, 15, 15, 3, # 0->13
                      4, 10, 13, 15, 15, 2, 5, 15, 18, 20, 25] # 14->23
    return random.expovariate(1 / arrival_coeff[HOUR])


def arrival(time, ev, FES, bss, stats):
    """
    An EV is arrived at the BSS.
    """
    sockets = bss.sockets
    queue = bss.queue
    update_all_batteries(time, bss, stats, 0)
    next_ready = 60 * C / CR # Max time to charge a battery (2h)
    can_wait = ev.can_wait
    resume_charge = 0
    flag = 0
    battery_booked = None

    stats.avg_ready[DAY] += bss.ready_batteries

    if can_wait == 1: # can_wait=0: EV has already arrived and it's waiting

        stats.daily_arr[HOUR] += 1
        stats.arrivals[DAY] += 1

        interarrival = next_arrival() # Schedule the next arrival
        FES.put((time + interarrival, "2_arrival", EV(random.gauss(8000, 1000), 0)))

        for socket in sockets: # Look for a charging battery not booked yet
            if socket.busy and not socket.battery.booked:

                if socket.battery.time_to_ready(time, HIGH_DEMAND, DAY, HOUR) < next_ready:
                    next_ready = socket.battery.time_to_ready(time, HIGH_DEMAND, DAY, HOUR)
                    battery_booked = socket.battery # Book a battery if ready_batteries is 0
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
                ev = queue.get()
                ev.can_wait = -1
            except:
                print("empty queue", time)
                sys.exit()
            battery = ev.battery

        for socket in sockets: # Plug battery in the first free socket
            if not socket.busy:
                socket.plug_battery(battery, time)
                break

    elif next_ready <= WMAX and can_wait == 1 and battery_booked and len(queue.queue) <= NBSS:
        # print(DAY, next_ready)
        stats.avg_wait[DAY] += next_ready
        battery_booked.booked = True
        socket_booked.is_charging = True # Reactivate charging if battery has been booked
        queue.put(ev)
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
def battery_available(time, FES, bss, stats):
    """
    One of the batteries is fully charged.
    """
    sockets = bss.sockets
    queue = bss.queue
    price = dm.get_prices_electricity(MONTH, DAY, HOUR)
    next_ready = 60 * C / CR
    resume_charge = 0

    stats.len_queue[DAY] += len(queue.queue) * (time - stats.last_update)
    stats.busy_sockets[DAY] += sum([s.busy for s in sockets]) * (time - stats.last_update)

    # print(HOUR, DAY)
    PVpower = 0
    if PV_SET:
        PVpower = dm.get_PV_power(MONTH, CURRENT_DAY, HOUR, SPV, NBSS)
        # Divide the energy produced by the PVs by the active sockets
        try: # Handle division by zero
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

                if not queue.empty():
                    ev = queue.get()
                    print(ev)
                    socket.plug_battery(ev.battery, time)
                    bss.ready_batteries -= 1
                    ev.can_wait = -1

            if not HIGH_DEMAND and socket.battery.charge >= C * TOL:
                socket.unplug_battery()
                bss.ready_batteries += 1

                if not queue.empty():
                    ev = queue.get()
                    print(ev)
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
def update_all_batteries(time, bss, stats, flag, FES=None):
    """
    Since every hour electricity price and PV production change, the charge of
    the batteries must be update with the right parameters.
    """
    sockets = bss.sockets
    queue = bss.queue.queue
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

    if FES:
        set_time(FES, stats)
    return 0


def check_high_demand(hour):
    global HIGH_DEMAND

    if hour==8 or (hour>=12 and hour<15) or (hour>=18 and hour<=19):
        HIGH_DEMAND = True
        return HIGH_DEMAND
    else:
        HIGH_DEMAND = False
        return HIGH_DEMAND


def set_time(FES, stats):
    global HOUR, DAY, CURRENT_DAY, MONTH

    HOUR += 1

    if HOUR == 24:
        compute_daily_stats(stats)
        HOUR = 0
        DAY += 1
        CURRENT_DAY += 1

        if CURRENT_DAY > monthrange(2019, MONTH)[1]:
            CURRENT_DAY = 1
            MONTH += 1

    FES.put((60 * (HOUR + 1) + ((DAY-1) * 24 * 60), "1_changehour", None))


def compute_daily_stats(stats):
    stats.avg_wait[DAY] = stats.avg_wait[DAY] / stats.arrivals[DAY]
    stats.avg_ready[DAY] = stats.avg_ready[DAY] / stats.arrivals[DAY]
    stats.len_queue[DAY] = stats.len_queue[DAY] / (60 * 24)
    stats.busy_sockets[DAY] = stats.busy_sockets[DAY] / (60 * 24)
    stats.loss_prob[DAY] = stats.loss[DAY] / stats.arrivals[DAY]

## Main ##
if __name__ == "__main__":

    warnings.filterwarnings("ignore")

    sg = ShareGlobals()
    sg.set_globals(C, CR, BTH, PV_SET, TOL, F, TMAX)
    sg.check()

    if PV_SET:
        print("SPV: ", SPV)

    time = 0

    FES = PriorityQueue()
    # Schedule the first arrival at t=0
    FES.put((0, "2_arrival", EV(random.gauss(8000, 1000), 0)))
    FES.put((60, "1_changehour", None))

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

    rc_flag = 0
    while time < SIM_TIME:

        (time, event, ev) = FES.get()
        if ev:
            ev.arrival_time = time

        # Check if time always increases
        if previous_time > time:
            raise Exception("Error: ", previous_time, time)
        else:
            previous_time = time

        ## DEBUG ##
        try:
            print(event, time, '| Busy sock:', sum([s.busy for s in sockets]),
                  '| Ready:', bss.ready_batteries, '| Queue', len(bss.queue.queue),
                  '| Canwait: ', ev.can_wait, '| FES:', FES.queue)
        except :
            print(event, time, '| Busy sock:', sum([s.busy for s in sockets]),
                  '| Ready:', bss.ready_batteries, '| Queue', len(bss.queue.queue),
                  '| FES:', FES.queue)

        if time > 319090:
            print("debug")

        if event == "2_arrival":
            resume_charge = arrival(time, ev, FES, bss, stats)

        elif event == "1_changehour":
            rc_flag = update_all_batteries(time, bss, stats, rc_flag, FES)

        elif event == "0_batteryavailable":
            resume_charge = battery_available(time, FES, bss, stats)

        if resume_charge:
            rc_flag = 1


    #%% Show statistics ##
    print("Mean arrivals: %f" % (np.mean(list(stats.arrivals.values()))))
    print("Mean loss: %f" % (np.mean(list(stats.loss.values()))))
    print("Mean cost: %f" % (np.mean(list(stats.cost.values()))))


    Plot([i/365 for i in stats.daily_arr.values()], title="Arrivals by hour").plot_by_hour()

    Plot(stats.arrivals.values(), title="Daily arrivals").plot_by_day()
    Plot(stats.loss.values(), title="Daily losses").plot_by_day()
    Plot(stats.avg_wait.values(), title="Daily waiting").plot_by_day()
    Plot(stats.avg_ready.values(), title="Avg ready batteries").plot_by_day()
    Plot(stats.len_queue.values(), title="Avg queue length").plot_by_day()
    Plot(stats.busy_sockets.values(), title="Busy sockets").plot_by_day()
    Plot(stats.consumption.values(), title="Power consumption").plot_by_day()

    if PV_SET:
        Plot(stats.cost.values(), title="Daily cost with PV").plot_by_day()
    else:
        Plot(stats.cost.values(), title="Daily cost without PV").plot_by_day()