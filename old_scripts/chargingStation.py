import random
import json
from queue import Queue, PriorityQueue
import numpy as np
# import seaborn as sns
from scipy.stats import t, sem
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta


class Measure:
    def __init__(self):
        self.arr = 0
        self.dep = 0
        self.ut = 0
        self.oldT = 0
        self.loss = []
        self.cost = 0
        self.waitingTime = []
        self.lossProb = []
        self.timelossProb = []
        self.chargingTime = []
        self.timeCost = []


class PriorityQueue_implemented:
    """
    Implemented priority queue. 
    This class was implemented to avoid 'time travel' 
    problems using the PriorityQueue class.
    """
    def __init__(self):
        self.queue = []

    def put(self, item):
        # Schedule next event
        self.queue.append(item)

    def get(self):
        # Get next event
        time_event = [item[0] for item in self.queue]
        index_next_event = np.argmin(time_event)
        
        if time_event.count(time_event[index_next_event]) == 1:
            return self.queue.pop(index_next_event)
        
        elif time_event.count(time_event[index_next_event]) > 1:
            event_name = [item[1] if item[0] == time_event[index_next_event] else 'z' for item in self.queue]
            index_next_event = np.argmin(event_name)
            return self.queue.pop(index_next_event)


class Battery:
    def __init__(self, arrival_time, charger, Bth=40, inStation=False):
        self.arrival_time = arrival_time
        self.working = inStation
        self.bth = Bth
        if inStation:  # set the battery level for the initial batteries in the chargers
            self.level = batLevel(20, 21)
            self.estimateAvailable = self.arrival_time + ((Bth - self.level) * 60 / chargingRate)  # estimated waiting time for next available battery
            FES.put((self.estimateAvailable, "batteryAvailable", charger))  # Schedule battery available event
        else:
            self.level = batLevel(Bth / 4, 1)
        self.charger = charger


class Charger:
    def __init__(self, NBSS):
        self.chargers = []
        self.working = []
        for i in range(NBSS):
            self.chargers.append(Battery(arrival_time=0, charger=i, inStation=True, Bth=Bth))


def batLevel(mean, std):  # generate random initial charge level
    global Bth
    level = np.random.normal(mean, std)
    if 0 < level < Bth:
        return level
    else:
        return batLevel(mean, std)


def getNextArrival(time, fixed=False):
    """
    time: hour of the day to generate random interarrival time according
          to the given distribution arrivalRateCoeff
    fixed: True if fixed average arrival rate for the EVs according fixed 
           time fixedNextArrival
    """
    if fixed:
        nextArrival = 5
    else:
        arrivalRateCoeff = [30, 30, 30, 30, 20, 15, 13, 10, 5, 8, 15, 15, 3, 4, 10, 13, 15, 15, 2, 5, 15, 18, 20, 25]  # distribution arrival rate (mean time between arrivals)
        hour = int(time / 60)  # hour index from time in minutes
        nextArrival = random.expovariate(1 / arrivalRateCoeff[hour])  # generate arrival time in minutes as function of the hour
    return nextArrival  # minutes


def arrival(time, FES, waitingLine):
    global Bth
    data.arr += 1
    data.ut += len(waitingLine) * (time - data.oldT) # time - oldT = delta T, elapsed time between two events
    if getLosses(data.loss, time, delta=deltaHighDemand) >= lossesHighDemand:  # define high demand even though the departure was already scheduled
        Bth = BthHighDemand
    else:
        Bth = 40
    inter_arrival = getNextArrival(time, fixed)  # get inter_arrival time, True for fixed time
    FES.put((time + inter_arrival, "arrival", -1))  # schedule the next arrival

    updateBatteriesLevel(time, data.oldT)  # update each battery level in chargers (in station) and update cost

    estimatedWaitings = []
    for i in range(len(chargers.chargers)):
        if chargers.chargers[i].working:
            estimatedWaitings.append(chargers.chargers[i].estimateAvailable)
    estimatedWaitings = np.sort(estimatedWaitings) # times at which the batteries will be charged

    if len(waitingLine) < [charger.working for charger in chargers.chargers].count(True): # full waiting line (the comprehension list is to verify how many working batteries there are-->that would be the waiting line available)
        residualWaiting = estimatedWaitings[len(waitingLine)] - time
        
        if 0 < residualWaiting < Wmax:
            waitingLine.append(Battery(arrival_time=time, charger=-1, Bth=Bth))  # charger=-1 means that battery is not charging yet
            
        elif residualWaiting <= 0:  # Battery available, then EV immediately served
            data.dep += 1
            oldBatteryEV = Battery(arrival_time=time, charger=-1, Bth=Bth)
            for i in range(len(chargers.chargers)):
                if chargers.chargers[i].estimateAvailable == estimatedWaitings[len(waitingLine)]:  # More than 1 battery charged, serve with equal available time
                    oldBatteryEV.charger = i
                    oldBatteryEV.working = True
                    data.waitingTime.append(0)  # The car does not wait for the charged battery
                    data.chargingTime.append(time - chargers.chargers[i].arrival_time)  # Compute charging battery time
                    oldBatteryEV.estimateAvailable = time + (Bth - oldBatteryEV.level) * 60 / chargingRate
                    chargers.chargers[i] = oldBatteryEV  # replace battery in charger
                    FES.put((oldBatteryEV.estimateAvailable, "batteryAvailable", i))
                    
        else:
            data.loss.append(time)  # List of time when the loss occurred
            data.waitingTime.append(Wmax)
    else:  # loss
        data.loss.append(time)  # List of time when the loss occurred
        data.waitingTime.append(Wmax)

    data.oldT = time


def updateBatteriesLevel(time, oldT):  # update batteries level and cost
    global chargingRate, Spv
    deltaCharge = (time - oldT) * chargingRate / 60
    listCosts = getCosts(time, oldT)
    for i in range(len(chargers.chargers)): # chargers.chargers = chargers.batteries
        if chargers.chargers[i].working:  # Check if chargers are working (work postponed due to high cost, daylight, and Tmax)
        
            if (chargers.chargers[i].level + deltaCharge) < C:  # If battery is not charged at full capacity
            
                chargers.chargers[i].level = chargers.chargers[i].level + deltaCharge  # update battery level
                
                if Spv == 0:  # If Spv is equal to 0 it means we are using the power grid and we need to pay for that
                    for pair in listCosts:
                        if (time - oldT) != 0:  # avoid zero division
                            data.cost += ((pair[0]) / (time - oldT)) * deltaCharge * pair[1]  # adding the cost of the fraction of time according to listCosts
            else:  # If deltaCharge plus battery level is greater than full capacity, charge battery until full capacity and dismiss the extra charge (Avoid overload)
                chargers.chargers[i].level = C


def batteryAvailable(time, FES, waitingLine, charger):  # departure
    global Bth
    updateBatteriesLevel(time, data.oldT)  # updated each battery level in chargers(in station) and update cost
    data.ut += len(waitingLine) * (time - data.oldT)
    if getLosses(data.loss, time, delta=deltaHighDemand) >= lossesHighDemand:
        Bth = BthHighDemand
    else:
        Bth = 40

    if len(waitingLine) != 0:
        data.dep += 1
        oldBatteryEV = waitingLine.pop(0)  # take battery from car
        data.waitingTime.append(time - oldBatteryEV.arrival_time)  # To estimate the individual waiting time
        data.chargingTime.append(time - chargers.chargers[charger].arrival_time)  # To estimate the charging battery time
        oldBatteryEV.charger = charger
        oldBatteryEV.working = True
        oldBatteryEV.arrival_time = time
        oldBatteryEV.estimateAvailable = time + (Bth - oldBatteryEV.level) * 60 / chargingRate
        chargers.chargers[charger] = oldBatteryEV  # replace battery in charger
        FES.put((oldBatteryEV.estimateAvailable, "batteryAvailable", charger))
    data.oldT = time


def updateEstimateAvailable(time):
    for i in range(len(chargers.chargers)):
        if chargers.chargers[i].working:
            if (Bth - chargers.chargers[i].level) != 0:  # If battery is already charged we don´t change the estimate available charge time
                chargers.chargers[i].estimateAvailable = time + (Bth - chargers.chargers[i].level) * 60 / chargingRate
                j = 0
                while j < len(FES.queue):
                    if FES.queue[j][1] in 'batteryAvailable' and FES.queue[j][2] == i:
                        FES.queue.pop(j)
                        break
                    else:
                        j += 1
                FES.put((chargers.chargers[i].estimateAvailable, 'batteryAvailable', i))
    estimatedWaitings = []
    for i in range(len(chargers.chargers)):
        if chargers.chargers[i].working:
            estimatedWaitings.append(chargers.chargers[i].estimateAvailable)
    estimatedWaitings = np.sort(estimatedWaitings)
    i = 0
    while i < len(waitingLine):
        if waitingLine[i].arrival_time + Wmax <= estimatedWaitings[i]:  # If EV needs to wait more than the arrival time plus Wmax, the EV leaves and is added to losses
            waitingLine.pop(i)
            data.loss.append(time)
            data.waitingTime.append(Wmax)
        else:
            i += 1


def chargingRate_change(time, FES):
    global chargingRate, Spv
    updateBatteriesLevel(time, data.oldT)  # updated each battery level in chargers (in station) and update cost
    FES.put((time + 60, "chargingRate_change", -1))  # Check every hour
    hour = int(time / 60)
    if hour % 24 == 0:  # Bug fix when there is a new day we start again at hour equal 0 not 24
        hour = 0
    PowerDayHour = PV_production[(PV_production['Month'] == month) & (PV_production['Day'] == day) & (PV_production['Hour'] == hour)]
    OutPow = PowerDayHour.iloc[0][3]  # Retrieving output power according to day, month, and hour
    Spv = S_one_PV * PV * OutPow  # Power of a set of panels in a given day, month, and hour (Wh)
    if Spv == 0:  # If solar panels are not producing energy (night hours or not PV 'installed')
        chargingRate = maxChargingRate
        if checkHighCost(hour):  # Checking if there is a high cost to postpone battery charging (numeral 3 lab)
            workingBatteries = [battery.working for battery in chargers.chargers]  # Creating a list if battery is working or not
            if all(workingBatteries):  # This is the first time (all arguments in True) we are going to change working batteries for not working batteries
                fracBatteries = np.floor(f * NBSS)  # Fraction of batteries that will NOT be used in the postponed time
                batteryLevel = [battery.level for battery in chargers.chargers]
                FES.put((time + Tmax, 'reconnectBatteries', -1))  # Event to reconnect batteries
                for i in range(int(fracBatteries)):  # Disconnect batteries (no additional cost added)
                    index = np.argmin(batteryLevel)
                    batteryLevel[index] = C + 1
                    if chargers.chargers[index].level < C:  # Disconnect battery only if it is not fully charged
                        chargers.chargers[index].working = False
                        j = 0
                        while j < len(FES.queue):
                            if FES.queue[j][1] in 'batteryAvailable' and FES.queue[j][2] == index:
                                FES.queue.pop(j)
                                break
                            else:
                                j += 1
                while NBSS - fracBatteries < len(waitingLine):  # If more customers are waiting and we have removed more batteries we have to take out the customers due to lack of batteries
                    waitingLine.pop()
                    data.loss.append(time)
        else:  # There is no high cost so I reconnect the batteries
            reconnectBatteries(time, FES)
    else:
        reconnectBatteries(time, FES)  # Making sure that every battery charger is connected because there is sunlight
        chargingRate = (Spv / NBSS) / 1000  # Over 1000 to convert it to kWh
        print(chargingRate)
        if chargingRate > 20:  # if charging rate is more than 20 kWh limit that power to avoid battery damage
            chargingRate = 20
    updateEstimateAvailable(time)
    data.oldT = time


def reconnectBatteries(time, FES):
    # Making sure that no other reconnect battery event is scheduled
    j = 0
    while j < len(FES.queue):
        if FES.queue[j][1] in 'reconnectBatteries':
            FES.queue.pop(j)
        else:
            j += 1
    # Reconnect batteries and rescheduling batteries available
    for i in range(NBSS):
        if not chargers.chargers[i].working:
            chargers.chargers[i].estimateAvailable = time + (Bth - chargers.chargers[i].level) * 60 / chargingRate
            FES.put((chargers.chargers[i].estimateAvailable, 'batteryAvailable', i))
            chargers.chargers[i].working = True
    updateEstimateAvailable(time)


def checkHighCost(hour):  # Checking if there is a high cost to postpone battery charging (numeral 3 lab)
    season = getSeason()
    cost = prices[(prices['Hour'] == hour) & (prices['Season'] == season)].iloc[0]['Cost']
    costsSeason = prices[(prices['Season'] == season)]
    highCost = costsSeason['Cost'].max() - costsSeason['Cost'].std()
    if cost >= highCost:
        return True
    else:
        return False


def getCosts(time, oldT):  # return eur/kWh according to the season
    cost = []
    season = getSeason()
    if int(oldT / 60) == int(time / 60):
        iterHour = int(time / 60)
        iterCost = prices[(prices['Hour'] == iterHour) & (prices['Season'] == season)].iloc[0]['Cost'] / 1000
        cost.append((time - oldT, iterCost))
    else:
        iterHour = int(oldT / 60)
        iterCost = prices[(prices['Hour'] == iterHour) & (prices['Season'] == season)].iloc[0]['Cost'] / 1000
        cost.append((60 - (oldT % 60), iterCost))
        iterHour += 1
        while iterHour != int(time / 60):
            if iterHour == 24:
                iterHour = 0
            iterCost = prices[(prices['Hour'] == iterHour) & (prices['Season'] == season)].iloc[0]['Cost'] / 1000
            cost.append((60, iterCost))
            iterHour += 1
        if iterHour == 24:
            iterHour = 0
        iterCost = prices[(prices['Hour'] == iterHour) & (prices['Season'] == season)].iloc[0]['Cost'] / 1000
        cost.append((time % 60, iterCost))
    return cost


def getSeason():
    if datetime(2020, 3, 20) <= datetime(2020, month, day) < datetime(2020, 6, 20):
        season = "SPRING"
    elif datetime(2020, 6, 20) <= datetime(2020, month, day) < datetime(2020, 9, 22):
        season = "SUMMER"
    elif datetime(2020, 9, 22) <= datetime(2020, month, day) < datetime(2020, 12, 21):
        season = "FALL"
    elif (datetime(2020, 1, 1) <= datetime(2020, month, day) < datetime(2020, 3, 20)) or (datetime(2020, 12, 21) <= datetime(2020, month, day) <= datetime(2020, 12, 31)):
        season = "WINTER"
    else:
        season = "NA"
    return season


def getLosses(lossses_list, time, delta):
    count = 0
    for i in lossses_list:
        if time - delta < i < time:  # Count the number of losses in the time span defined by the delta
            count += 1
    return count


if __name__ == '__main__':
    C = 40  # Max battery capacity
    NBSS = 10  # Max number of chargers
    fixed = False  # fixed arrival time 5 min
    fixedTime = 5
    Wmax = 20  # Max waiting time for EV
    Bth = 40  # Battery capacity
    BthHighDemand = 40  # Accepted minimum charge level
    deltaHighDemand = 60
    lossesHighDemand = 2
    chargingRate = 20  # charging rate per hour
    maxChargingRate = 20  # Fixed charging rate
    PV = 0  # Number of Photovoltaic Panels
    S_one_PV = 1  # Nominal Cap. of one PV (1kWp)
    prices = pd.read_csv('../data/electricity_prices.csv')  # Prices dataframe
    PV_production = pd.read_csv('../data/PVproduction_PanelSize1kWp.csv')  # Output PV power dataframe
    day = 26
    month = 6
    Spv = 0  # Nominal Cap. of the set of PV (kW), as we start at midnight the nom. cap. will always be 0
    f = 0
    Tmax = 0
    # numberChargers = [1, 5, 10, 15, 16, 17, 18, 19, 20]
    numberChargers = [1, 5, 10, 15, 20]
    outputData = {}
    # for seed in range(5):
    seed = 42
    NBSS = 10


    random.seed(seed)
    np.random.seed(seed)
    SIM_TIME = 24 * 60  # Simulation time in minutes
    time = 0
    waitingLine = []
    data = Measure()
    
    FES = PriorityQueue_implemented()  # list of events
    FES.put((0, "arrival", -1))  # schedule first arrival at t=0
    FES.put((60, "chargingRate_change", -1))
    
    chargers = Charger(NBSS)
    listChargingRate = []
    
    while time < SIM_TIME:
        (time, event_type, charger) = FES.get()

        if event_type == "arrival":
            arrival(time, FES, waitingLine)

        elif event_type == "batteryAvailable":
            batteryAvailable(time, FES, waitingLine, charger)

        elif event_type == "chargingRate_change":
            chargingRate_change(time, FES)
            
        data.lossProb.append(len(data.loss) / data.arr)
        data.timelossProb.append(time)
        
    confidenceIntLoss = t.interval(0.999, len(data.lossProb) - 1, np.mean(data.lossProb), sem(data.lossProb))
    print(f"Confidence interval Waiting Time: {confidenceIntLoss}")
    print(f"Number of arrivals: {data.arr}")
    print(f"Number of departures: {data.dep}")
    print(f"Number of losses: {len(data.loss)}")
    print(f"Total cost: {data.cost}")



