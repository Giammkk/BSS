import random
from queue import PriorityQueue
import pandas as pd
from calendar import monthrange
import json
from plot import Plot, MultiPlot
import matplotlib.pyplot as plt
import numpy as np

random.seed(2)

## Global variables ##
SIM_TIME = 60
DAY = 1                 # Day of the simulation (from 1 to 365)
HOUR = 0                # Current hour (from 0 to 23)
CURRENT_DAY = 1         # Current day (from 1 to 30/31/28)
MONTH = 1               # Current month in the simulation
C = 40000               # Battery capacity
TOL = 0.96              # Percentage of charge to be full
NBSS = 20               # Max number of chargers
B = 2*NBSS              # Max number of batteries (charging + queue)
ARRIVAL = 5             # Fixed interarrival time
ARRIVAL_FIXED = False   # True: if average arrival rate fixed (Point 1)...
                        # ...False: if variable (Point 2)
WMAX = 10               # Max waiting time for EV
BTH = 20000             # Minimum charge level
CR = int(C/2)           # Charging rate per hour
PV_SET = 1              # Indicator of presence of a PV in the BSS
SPV = 1                 # Nominal capacity of the set of PV (kW)
F = 0                   # Fraction of batteries whose charge can be postponed
TMAX = 0                # Maximum time by which the charge process can be postponed
HIGH_DEMAND = False     # High demand indicator

prices = pd.read_csv('data/electricity_prices.csv', header=None)
prices_winter = [float(i) for i in prices.loc[prices[1] == 'WINTER'][2].tolist()]
prices_spring = [float(i) for i in prices.loc[prices[1] == 'SPRING'][2].tolist()]
prices_summer = [float(i) for i in prices.loc[prices[1] == 'SUMMER'][2].tolist()]
prices_fall   = [float(i) for i in prices.loc[prices[1] == 'FALL'][2].tolist()]

# pv_df = pd.read_csv('data/PVproduction_PanelSize1kWp.csv')
pv_production = json.loads(open('data/PVproduction_PanelSize1kWp.json', 'r').read())

## Statistics ##
class Statistics:
    def __init__(self):
        # self.departures = 0         # Number of departures
        self.avg_ready = {i+1:0 for i in range(365)} # Average ready batteries
        self.last_update = 0

        self.arrivals = {i+1:0 for i in range(365)} # Daily arrivals
        self.wait_delay = {i+1:0 for i in range(365)} # Daily average waiting delay
        self.loss = {i+1:0 for i in range(365)} # Daily number of missed services
        self.avg_wait = {i+1:0 for i in range(365)} # Avg time for EV to wait for to have a full battery
        self.cost = {i+1:0 for i in range(365)} # Cost of charging batteries

        self.daily_arr = {i:0 for i in range(24)}

class AvgStatistics:
    def __init__(self, r=1, c=1):
        self.avg_arrivals = np.zeros((r,c))
        self.avg_loss = np.zeros((r,c))
        self.avg_cost = np.zeros((r,c))
        self.avg_avg_ready = np.zeros((r,c))
        self.avg_avg_wait = np.zeros((r,c))

## Socket ##
class Socket:

    def __init__(self, busy=False, busy_time=0, post_time=0, n_departures=0):
        self.busy = busy                    # Whether the socket is charging or not
        self.busy_time = busy_time          # Time a plug of the BSS is used
        self.post_time = post_time          # Time a charging process is postponed
        self.n_departures = n_departures    # Number of departures
        self.battery = None

    def plug_battery(self, battery):
        self.busy = True
        self.battery = battery

    def unplug_battery(self):
        self.busy = False
        self.battery = None


## Battery ##
class Battery:

    def __init__(self, charge=random.gauss(8000, 500), last_update=0):
        self.charge = 0 if charge < 0 else charge
        self.charge = 16000 if charge > 16000 else charge
        self.last_update = last_update
        self.booked = False

    def update_charge(self, time, PVpower, price):
        power_update = (time - self.last_update) / 60 # To convert the charging rate Watt/minutes
        price_power_update = 0

        if PVpower != 0 and PV_SET: # Check if the PV has power
            if PVpower > CR:
                power_update *= CR # Take the power from the PV avoiding the maximum charging rate is exceeded
                self.charge += power_update
            else:
                power_update *= PVpower # Take the power from the PV
                self.charge = self.charge + power_update
        else:
            power_update *= CR # Take the power from the grid
            self.charge = self.charge + power_update
            price_power_update = price * power_update * 1e-6 / 60

        self.last_update = time
        return price_power_update

    def time_to_ready(self):
        if HIGH_DEMAND or check_high_demand(HOUR + 1):
            t = (BTH - self.charge) * 60 / CR

        else:
            t = (C*TOL - self.charge) * 60 / CR

        return t

def next_arrival():
    # global HIGH_DEMAND

    if not ARRIVAL_FIXED:
        arrival_coeff = [30, 40, 40, 30, 20, 15, 13, 10, 5, 8, 15, 15, 3, 4, # 0->13
                          10, 13, 15, 15, 2, 5, 15, 18, 20, 25] # 14->23

        interarrival = random.expovariate(1 / arrival_coeff[HOUR])

    else:
        interarrival = ARRIVAL

    return interarrival


def arrival(time, can_wait, FES, queue, sockets, ready_batteries, stats):
    """
    An EV is arrived at the BSS.
    """

    ready_batteries = update_all_batteries(time, sockets, ready_batteries, stats)
    next_ready = 60 * C / CR # Max time to charge a battery (2h)
    flag = 0
    battery_booked = None

    if can_wait: # can_wait=0: EV has already arrived and it's waiting

        stats.daily_arr[HOUR] += 1

        interarrival = next_arrival() # Schedule the next arrival
        FES.put((time + interarrival, "2_arrival", 1))

        stats.arrivals[DAY] += 1

        for socket in sockets:
            if socket.busy and not socket.battery.booked:
                next_ready = min(next_ready, socket.battery.time_to_ready())
                battery_booked = socket.battery
            else:
                flag = 1

        if not flag:
            stats.avg_wait[DAY] += next_ready
        stats.avg_ready[DAY] += ready_batteries

    if ready_batteries > 0:
        ready_batteries -= 1

        if can_wait:
            battery = Battery(last_update=time)
        else:
            battery = queue.pop(0)

        for socket in sockets: # Plug battery in the first free socket
            if not socket.busy:
                socket.plug_battery(battery)
                break

    elif next_ready < WMAX and can_wait and battery_booked and len(queue) < NBSS:
        battery_booked.booked = True
        queue.append(Battery(last_update=next_ready + time))
        FES.put((next_ready + time, "2_arrival", 0))

    else:
        stats.loss[DAY] += 1

    return ready_batteries


def prices_electricity(m, d, h):
    """
    Return the list of the electricity prices by hours of a day given a season.
    """
    if m==1 or m==2 or (m==3 and d<20) or (m==12 and d>=21):
        pc = prices_winter
    elif (m==3 and d>=20) or m==4 or m==5 or (m==6 and d<20):
        pc = prices_spring
    elif (m==6 and d>=20) or m==7 or m==8 or (m==9 and d<22):
        pc = prices_summer
    elif (m==9 and d>=22) or m==10 or m==11 or (m==12 and d<21):
        pc = prices_fall

    return pc[h]


## Departure ##
def battery_available(time, FES, queue, sockets, ready_batteries, stats):
    """
    One of the batteries is fully charged.
    """
    price = prices_electricity(MONTH, DAY, HOUR)

    PVpower = 0
    if PV_SET:
        PVpower = pv_production[str(MONTH)][str(CURRENT_DAY)][str(HOUR)]\
            * SPV / NBSS

    for socket in sockets:
        stats.cost[DAY] += socket.battery.update_charge(time, PVpower, price)

        if HIGH_DEMAND and socket.battery.charge >= BTH:
            socket.unplug_battery()
            ready_batteries += 1

        if not HIGH_DEMAND and socket.battery.charge >= C * TOL:
            socket.unplug_battery()
            ready_batteries += 1

    return ready_batteries


## Change Hour ##
def update_all_batteries(time, sockets, ready_batteries, stats):
    """
    Since every hour electricity price and PV production change, the charge of
    the batteries must be update with the right parameters.
    """
    price = prices_electricity(MONTH, DAY, HOUR)
    check_high_demand(HOUR)

    PVpower = 0
    if PV_SET:
        PVpower = pv_production[str(MONTH)][str(CURRENT_DAY)][str(HOUR)]*SPV/NBSS

    for socket in sockets:
        if socket.busy:
            stats.cost[DAY] += socket.battery.update_charge(time, PVpower, price)

            if HIGH_DEMAND and socket.battery.charge >= BTH:
                socket.unplug_battery()
                ready_batteries += 1

            if not HIGH_DEMAND and socket.battery.charge >= C * TOL:
                socket.unplug_battery()
                ready_batteries += 1

    return ready_batteries


def check_high_demand(hour):
    global HIGH_DEMAND
    global ARRIVAL_FIXED

    if not ARRIVAL_FIXED:
        HIGH_DEMAND = True if (hour>=8 and hour<12) or (hour>=16 and hour<19) else False


## Main ##
if __name__ == '__main__':
    
    spv_list = list(range(1,11))
    nbss_list = list(range(5,25,5))
    stats_by_nbss = AvgStatistics(len(spv_list), len(nbss_list))
    
    for SPV in spv_list:
        for NBSS in nbss_list:
            
            time = 0
            DAY = 1
            HOUR = 0
            CURRENT_DAY = 1
            MONTH = 1
            
            FES = PriorityQueue()
            FES.put((0, "2_arrival", 1)) # Schedule the first arrival at t=0
            
            queue = list()
            ready_batteries = NBSS
            
            sockets = list()
            for i in range(NBSS):
                s = Socket()
                # s.plug_battery(Battery())
                sockets.append(s)
            
            stats = Statistics()
               
            while MONTH <= 12:
                number_of_days = monthrange(2019, MONTH)[1]
                CURRENT_DAY = 1
            
                while CURRENT_DAY <= number_of_days:
            
                    HOUR = 0
            
                    while HOUR < 24:
            
                        FES.put((60*HOUR*DAY, "1_changehour", -1))
            
                        while time < SIM_TIME * (HOUR + 1) + ((DAY-1) * 24 * 60):
            
                            (time, event, can_wait) = FES.get()
            
                            if event == "2_arrival":
                                ready_batteries = arrival(time, can_wait, FES, queue, sockets, ready_batteries, stats)
            
                            elif event == "1_changehour":
                                ready_batteries = update_all_batteries(time, sockets, ready_batteries, stats)
            
                            elif event == "0_batteryavailable":
                                ready_batteries = battery_available(time, FES, queue, sockets, ready_batteries, stats)
            
                        HOUR += 1
            
                    stats.avg_wait[DAY] = stats.avg_wait[DAY] / stats.arrivals[DAY]
                    stats.avg_ready[DAY] = stats.avg_ready[DAY] / stats.arrivals[DAY]
                    DAY += 1
                    CURRENT_DAY += 1
            
                MONTH += 1
            
            r = SPV - 1
            c = int(NBSS/5) - 1
            stats_by_nbss.avg_arrivals[r][c] = np.mean(list(stats.arrivals.values()))
            stats_by_nbss.avg_loss[r][c] = np.mean(list(stats.loss.values()))
            stats_by_nbss.avg_avg_wait[r][c] = np.mean(list(stats.avg_wait.values()))
            stats_by_nbss.avg_avg_ready[r][c] = np.mean(list(stats.avg_ready.values()))
            stats_by_nbss.avg_cost[r][c] = np.mean(list(stats.cost.values()))
    
    ## Show statistics ##
    
    MultiPlot(stats_by_nbss.avg_arrivals, "Arrivals").plot()
    MultiPlot(stats_by_nbss.avg_loss, "Losses").plot()
    MultiPlot(stats_by_nbss.avg_avg_wait, "Waiting").plot()
    MultiPlot(stats_by_nbss.avg_avg_ready, "Average ready").plot()
    MultiPlot(stats_by_nbss.avg_cost, "Costs").plot()
    
    # fig = plt.figure()
    # plt.grid()
    # plt.xlim((0,23))
    # ax = fig.add_subplot(1, 1, 1)
    # major_ticks = np.arange(0, 23, 1)
    # minor_ticks = np.arange(0, 23, 1)  
    # ax.set_xticks(major_ticks)
    # ax.set_xticks(minor_ticks, minor=True)
    # plt.plot(range(24), [int(i/365) for i in stats.daily_arr.values()], '.-')


    # Plot(stats.arrivals.values(), "Daily arrivals").plot()
    # Plot(stats.loss.values(), "Daily losses").plot()
    # Plot(stats.avg_wait.values(), "Daily waiting").plot()
    # Plot(stats.avg_ready.values(), "Avg ready batteries").plot()
    # if PV_SET:
    #     Plot(stats.cost.values(), "Daily cost with PV", 1).plot()
    # else:
    #     Plot(stats.cost.values(), "Daily cost without PV", 1).plot()