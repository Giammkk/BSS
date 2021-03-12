SIM_TIME = 60 * 24 * 365
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
F = NBSS / 3  # Fraction of batteries whose charge can be postponed
TMAX = 20  # Maximum time by which the charge process can be postponed


def check_high_demand(hour=HOUR):
    if hour == 8 or (12 <= hour < 15) or (18 <= hour <= 19):
        return True
    else:
        return False