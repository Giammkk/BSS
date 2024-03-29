SIM_LAST = 59   # Last of simulation (days)
SIM_TIME = 60 * 24 * SIM_LAST
DAY = 1  # Day of the simulation (from 1 to 365)
HOUR = 0  # Current hour (from 0 to 23)
CURRENT_DAY = 1  # Current day (from 1 to 30/31/28)
MONTH = 6  # Current month in the simulation
C = 20000  # Battery capacity
TOL = 1  # Percentage of charge to be full
NBSS = 15  # Max number of chargers
B = 2 * NBSS  # Max number of batteries (charging + queue)
WMAX = 15  # Max waiting time for EV
BTH = C * 0.8  # Minimum charge level
CR = int(C / 2)  # Charging rate per hour
PV_SET = 1  # Indicator of presence of a PV in the BSS
SPV = 100  # Nominal capacity of one PV (kW) * number of panels
F = NBSS   # Fraction of batteries whose charge can be postponed
TMAX = 30  # Maximum time by which the charge process can be postponed

arrival_rate = [30, 30, 30, 30, 20, 15, 13, 10, 5, 8, 15, 15, 3,  # 0->13
                4, 10, 13, 15, 15, 3, 5, 15, 18, 20, 25]  # 14->23

arrival_rate_2 = [29, 29, 29, 26, 20, 15, 13, 10, 2.5, 6, 11, 13, 15,
                  15, 12, 13, 10, 2.5, 5, 7, 15, 18, 20, 25]

arrival_rate_3 = [10] * 24


def check_high_demand(hour=HOUR):
    if hour == 8 or (12 <= hour < 15) or (18 <= hour <= 19):
        return True
    else:
        return False
