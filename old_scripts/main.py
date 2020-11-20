import random
from queue import PriorityQueue
# import pandas as pd
from calendar import monthrange
# import json
from plot import Plot, MultiPlot
# import matplotlib.pyplot as plt
import numpy as np
from data_manager import DatasetManager
from components import ShareGlobals, Socket, Battery, EV

# random.seed(1)

## Global variables ##
SIM_TIME = 60
DAY = 1                 # Day of the simulation (from 1 to 365)
HOUR = 0                # Current hour (from 0 to 23)
CURRENT_DAY = 1         # Current day (from 1 to 30/31/28)
MONTH = 1               # Current month in the simulation
C = 40000               # Battery capacity
TOL = 0.97              # Percentage of charge to be full
NBSS = 15               # Max number of chargers
B = 2*NBSS              # Max number of batteries (charging + queue)
ARRIVAL = 5             # Fixed interarrival time
ARRIVAL_FIXED = False   # True: if average arrival rate fixed (Point 1)...
                        # ...False: if variable (Point 2)
WMAX = 15               # Max waiting time for EV
BTH = 20000             # Minimum charge level
CR = int(C/2)           # Charging rate per hour
PV_SET = 1              # Indicator of presence of a PV in the BSS
SPV = 5                 # Nominal capacity of the set of PV (kW)
F = 0                   # Fraction of batteries whose charge can be postponed
TMAX = 0                # Maximum time by which the charge process can be postponed
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
        
class AvgStatistics:
    def __init__(self, r=1, c=1):
        self.avg_arrivals = np.zeros((r,c))
        self.avg_loss = np.zeros((r,c))
        self.avg_cost = np.zeros((r,c))
        self.avg_avg_ready = np.zeros((r,c))
        self.avg_avg_wait = np.zeros((r,c))


def next_arrival():
    if not ARRIVAL_FIXED:
        arrival_coeff = [30, 30, 30, 30, 20, 15, 13, 10, 5, 8, 15, 15, 3, # 0->13
                         4, 10, 13, 15, 15, 2, 5, 15, 18, 20, 25] # 14->23

        interarrival = random.expovariate(1 / arrival_coeff[HOUR])

    else:
        interarrival = ARRIVAL

    return interarrival


def arrival(time, ev, FES, queue, sockets, ready_batteries, stats):
    """
    An EV is arrived at the BSS.
    """
    ready_batteries = update_all_batteries(time, queue, sockets, ready_batteries, stats)
    next_ready = 60 * C / CR # Max time to charge a battery (2h)
    can_wait = ev.can_wait

    flag = 0
    battery_booked = None

    stats.avg_ready[DAY] += ready_batteries

    if can_wait == 1: # can_wait=0: EV has already arrived and it's waiting

        stats.daily_arr[HOUR] += 1
        stats.arrivals[DAY] += 1

        interarrival = next_arrival() # Schedule the next arrival
        FES.put((time + interarrival, "2_arrival", EV(random.gauss(8000, 1000), time)))

        for socket in sockets: # Look for a charging battery not booked yet
            if socket.busy and not socket.battery.booked:

                if socket.battery.time_to_ready(HIGH_DEMAND, HOUR) < next_ready:
                    next_ready = socket.battery.time_to_ready(HIGH_DEMAND, HOUR)
                    battery_booked = socket.battery # Book a battery if ready_batteries is 0

            else:
                flag = 1

        if not flag:
            if (next_ready + time, "0_batteryavailable", None) not in FES.queue:
                FES.put((next_ready + time, "0_batteryavailable", None))

    if ready_batteries > 0 and can_wait != -1:
        ready_batteries -= 1

        if can_wait == 1:
            battery = ev.battery
        else:
            ev = queue.pop(0)
            battery = ev.battery

        for socket in sockets: # Plug battery in the first free socket
            if not socket.busy:
                socket.plug_battery(battery, time)
                break

    elif next_ready <= WMAX and can_wait == 1 and battery_booked and len(queue) <= NBSS:
        # print(DAY, next_ready)
        stats.avg_wait[DAY] += next_ready
        battery_booked.booked = True
        queue.append( ev )
        ev.can_wait = 0
        FES.put((next_ready + time, "2_arrival", ev))

    elif can_wait == -1:
        # print("can wait -1")
        pass
    else:
        stats.loss[DAY] += 1

    return ready_batteries


## Departure ##
def battery_available(time, FES, queue, sockets, ready_batteries, stats):
    """
    One of the batteries is fully charged.
    """
    price = dm.get_prices_electricity(MONTH, DAY, HOUR)
    next_ready = 60 * C / CR

    stats.len_queue[DAY] += len(queue) * (time - stats.last_update)
    stats.busy_sockets[DAY] += sum([s.busy for s in sockets]) * (time - stats.last_update)

    # print(HOUR, DAY)
    PVpower = 0
    if PV_SET:
        PVpower = dm.get_PV_power(MONTH, CURRENT_DAY, HOUR, SPV, NBSS)

    for socket in sockets:
        if socket.busy:
            stats.cost[DAY] += socket.battery.update_charge(time, PVpower, price)

            if HIGH_DEMAND and socket.battery.charge >= BTH * 0.999:
                socket.unplug_battery()
                ready_batteries += 1

                if queue:
                    ev = queue.pop(0)
                    socket.plug_battery(ev.battery, time)
                    ready_batteries -= 1
                    ev.can_wait = -1

            if not HIGH_DEMAND and socket.battery.charge >= C * TOL * 0.999:
                socket.unplug_battery()
                ready_batteries += 1

                if queue:
                    ev = queue.pop(0)
                    socket.plug_battery(ev.battery, time)
                    ready_batteries -= 1
                    ev.can_wait = -1

    for socket in sockets:
        if socket.busy:
            next_ready = min(socket.battery.time_to_ready(HIGH_DEMAND, HOUR), next_ready)

    if (next_ready + time, "0_batteryavailable", None) not in FES.queue:
        FES.put((next_ready + time, "0_batteryavailable", None))

    stats.last_update = time
    return ready_batteries


## Change Hour ##
def update_all_batteries(time, queue, sockets, ready_batteries, stats):
    """
    Since every hour electricity price and PV production change, the charge of
    the batteries must be update with the right parameters.
    """
    price = dm.get_prices_electricity(MONTH, DAY, HOUR)
    check_high_demand(HOUR)

    stats.len_queue[DAY] += len(queue) * (time - stats.last_update)
    stats.busy_sockets[DAY] += sum([s.busy for s in sockets]) * (time - stats.last_update)

    PVpower = 0
    if PV_SET:
        PVpower = dm.get_PV_power(MONTH, CURRENT_DAY, HOUR, SPV, NBSS)

    for socket in sockets:
        if socket.busy:
            stats.cost[DAY] += socket.battery.update_charge(time, PVpower, price)

            if HIGH_DEMAND and socket.battery.charge >= BTH:
                socket.unplug_battery()
                ready_batteries += 1

            if not HIGH_DEMAND and socket.battery.charge >= C * TOL:
                socket.unplug_battery()
                ready_batteries += 1

    stats.last_update = time
    return ready_batteries


def check_high_demand(hour):
    global HIGH_DEMAND
    global ARRIVAL_FIXED

    if not ARRIVAL_FIXED:
        if (hour>=8 and hour<12) or (hour>=16 and hour<19):
            HIGH_DEMAND = True
            return HIGH_DEMAND
        else:
            HIGH_DEMAND = False
            return HIGH_DEMAND


## Main ##
if __name__ == '__main__':

    sg = ShareGlobals()
    sg.set_globals(C, CR, BTH, PV_SET, TOL)
    sg.check()
    
    spv_list = [15, 30, 100, 200, 400, 600, 800, 1000, 1200]
    nbss_list = list(range(5,35,5))
    stats_by_nbss = AvgStatistics(len(spv_list), len(nbss_list))
    
    for SPV in spv_list:
        for NBSS in nbss_list:

            time = 0
            previous_time = -1
        
            FES = PriorityQueue()
            # Schedule the first arrival at t=0
            FES.put((0, "2_arrival", EV(random.gauss(8000, 1000), 0)))
        
            queue = list()
            ready_batteries = 0
        
            sockets = list()
            for i in range(NBSS):
                s = Socket()
                s.plug_battery(Battery(charge=random.gauss(8000, 1000)), time)
                sockets.append(s)
        
            stats = Statistics()
            MONTH = 1
            DAY = 1
                     
            while MONTH <= 12:
                number_of_days = monthrange(2019, MONTH)[1]
                CURRENT_DAY = 1
        
                while CURRENT_DAY <= number_of_days:
                    # pri1nt(f"{CURRENT_DAY}/{MONTH}")
                    HOUR = 0
        
                    while HOUR < 24:
        
                        FES.put((60 * (HOUR + 1) + ((DAY-1) * 24 * 60), "1_changehour", None))
                        # print(f"{HOUR}")
                        while time < SIM_TIME * (HOUR + 1) + ((DAY-1) * 24 * 60):
        
                            (time, event, ev) = FES.get()
        
                            # Check if time always increases
                            if previous_time > time:
                                raise Exception("Error.")
                            else:
                                previous_time = time
        
                            # try:
                            #     print(event, time, '| Busy sock:', sum([s.busy for s in sockets]), '| Ready:', ready_batteries, '| Queue', len(queue), '| Canwait: ', ev.can_wait)
                            # except :
                            #     print(event, time, '| Busy sock:', sum([s.busy for s in sockets]), '| Ready:', ready_batteries, '| Queue', len(queue))
        
                            if event == "2_arrival":
                                ready_batteries = arrival(time, ev, FES, queue, sockets, ready_batteries, stats)
        
                            elif event == "1_changehour":
                                ready_batteries = update_all_batteries(time, queue, sockets, ready_batteries, stats)
        
                            elif event == "0_batteryavailable":
                                ready_batteries = battery_available(time, FES, queue, sockets, ready_batteries, stats)
        
                        HOUR += 1
        
                    stats.avg_wait[DAY] = stats.avg_wait[DAY] / stats.arrivals[DAY]
                    stats.avg_ready[DAY] = stats.avg_ready[DAY] / stats.arrivals[DAY]
                    stats.len_queue[DAY] = stats.len_queue[DAY] / (60 * 24)
                    stats.busy_sockets[DAY] = stats.busy_sockets[DAY] / (60 * 24)
        
                    DAY += 1
                    CURRENT_DAY += 1
        
                MONTH += 1
                
            r = spv_list.index(SPV)
            c = nbss_list.index(NBSS)
            stats_by_nbss.avg_arrivals[r][c] = np.mean(list(stats.arrivals.values()))
            stats_by_nbss.avg_loss[r][c] = np.mean(list(stats.loss.values()))
            stats_by_nbss.avg_avg_wait[r][c] = np.mean(list(stats.avg_wait.values()))
            stats_by_nbss.avg_avg_ready[r][c] = np.mean(list(stats.avg_ready.values()))
            stats_by_nbss.avg_cost[r][c] = np.mean(list(stats.cost.values()))

    # Show statistics ##
    # print(f"Mean arrivals: {np.mean(list(stats.arrivals.values()))}")
    # print(f"Mean loss: {np.mean(list(stats.loss.values()))}")


    # Plot([i/365 for i in stats.daily_arr.values()], "Arrivals by hour").plot_by_hour()

    # Plot(stats.arrivals.values(), "Daily arrivals").plot()
    # Plot(stats.loss.values(), "Daily losses").plot()
    # Plot(stats.avg_wait.values(), "Daily waiting").plot()
    # Plot(stats.avg_ready.values(), "Avg ready batteries").plot()
    # Plot(stats.len_queue.values(), "Avg queue length").plot()
    # Plot(stats.busy_sockets.values(), "Busy sockets").plot()
    # if PV_SET:
    #     Plot(stats.cost.values(), "Daily cost with PV", 1).plot()
    # else:
    #     Plot(stats.cost.values(), "Daily cost without PV", 1).plot()
    
    MultiPlot(stats_by_nbss.avg_arrivals, "Arrivals", spv_list).plot()
    MultiPlot(stats_by_nbss.avg_loss, "Losses", spv_list).plot()
    MultiPlot(stats_by_nbss.avg_avg_wait, "Waiting", spv_list).plot()
    MultiPlot(stats_by_nbss.avg_avg_ready, "Average ready", spv_list).plot()
    MultiPlot(stats_by_nbss.avg_cost, "Costs", spv_list).plot()