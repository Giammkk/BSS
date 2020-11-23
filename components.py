import random
from calendar import monthrange

C      = 0
CR     = 0
BTH    = 0
PV_SET = 0
TOL    = 0
F      = 0
TMAX   = 0

## Check global variables ##
class ShareGlobals:
    def __init__(self):
        pass

    def set_globals(self, C_, CR_, BTH_, PV_SET_, TOL_, F_, TMAX_):
        global C, CR, BTH, PV_SET, TOL, F, TMAX

        C = C_
        CR = CR_
        BTH = BTH_
        PV_SET = PV_SET_
        TOL = TOL_
        F = F_
        TMAX = TMAX_

    def check(self):
        print('C:', C, '| CR:', CR, '| BTH:', BTH,
              '| PV_SET:', PV_SET, '| TOL:', TOL,
              '| F:', F, '| TMAX:', TMAX)

## Socket ##
class Socket:

    def __init__(self, busy=False):
        self.busy = busy
        self.is_charging = True
        self.battery = None
        self.bss = None
        self.postpone_time = 0
        self.postpone_timer = int(TMAX/60)

    def plug_battery(self, battery, time):
        self.busy = True
        # self.is_charging = True
        self.battery = battery
        self.battery.last_update = time
        self.bss.n_charging += 1

    def unplug_battery(self):
        self.busy = False
        # self.is_charging = False
        self.battery = None
        self.bss.n_charging -= 1

## Battery ##
class Battery:

    def __init__(self, charge=random.gauss(8000, 1000), last_update=0):
        self.charge = 0 if charge < 0 else charge
        self.charge = 16000 if charge > 16000 else charge
        self.last_update = last_update
        self.booked = False

    def update_charge(self, time, PVpower, price):
        power_update = (time - self.last_update) / 60 # Hours
        if power_update < 0:
            raise Exception('Negative power update')

        price_power_update = 0

        if PVpower != 0 and PV_SET: # Check if the PV has power
            # Take the power from the PV avoiding the maximum charging rate is exceeded
            if PVpower > CR:
                power_update *= CR
                self.charge += power_update
            else:
                CR_grid = CR - PVpower
                # Take the power from the PV and the grid
                power_update_pv = power_update * PVpower
                power_update_grid = power_update * CR_grid
                self.charge = self.charge + power_update_pv + power_update_grid
                price_power_update = price * power_update_grid * 1e-6
                power_update = power_update_grid
        else:
            power_update *= CR # Take the power from the grid
            self.charge = self.charge + power_update
            price_power_update = price * power_update * 1e-6

        # print(self.charge, '/', C)
        self.last_update = time
        return price_power_update, power_update
    
    def time_to_ready(self, time, high_demand, day, hour):
        time_to_ch = 60 * (hour + 1) + ((day - 1) * 24 * 60) - time
        
        if high_demand:
            t = (BTH - self.charge) * 60 / CR
            t = time_to_ch + 0.001 if t < 0 else t # If battery was not full
            # in previous not high-demand hour, but higher than Bth
        else:
            t = (C - self.charge) * 60 / CR
                    
        if t < time_to_ch:
            return t
        else:
            delta_charge = time_to_ch * CR / 60
            if self.__check_high_demand(hour + 1):
                if BTH - (self.charge + delta_charge) > 0:
                    t = time_to_ch + (BTH - (self.charge + delta_charge)) * 60 / CR
                else:
                    t = time_to_ch + 0.001
            else:
                if C - (self.charge + delta_charge) < 0:
                    # print("C - (self.charge + delta_charge) < 0")
                    t = time_to_ch + 0.001
                else:
                    t = time_to_ch + (C - (self.charge + delta_charge)) * 60 / CR
        return t 
    
    def __check_high_demand(hour):
        if (hour>=8 and hour<12) or (hour>=16 and hour<19):
            return True
        else:
            return False

## Electric Vehicle ##
class EV:
    def __init__(self, charge, arrival_time):
        self.can_wait = 1
        self.battery = Battery(charge=charge)
        self.arrival_time = arrival_time
        self.service_time = 0 # What time EV is served (used in case of waiting)
    
    def __lt__(self, other): 
        return self.arrival_time < other.arrival_time
    
## Battery Switch Station ##
class BSS:
    def __init__(self, sockets=[], n_charging=0):
        self.sockets = sockets
        self.queue = list()
        self.n_sockets = len(sockets)
        self.n_charging = 0
        self.cnt = 0
        self.postponed_batteries = 0
        self.ready_batteries = 0
        self.power_consumption = 0

    def postpone_charge(self, time, sim_day, dm, month, day, hour, spv, nbss):
        h = int((time + TMAX - (sim_day-1) * 24 * 60) / 60)
        if h >= hour + 1:

            pv_now = dm.get_PV_power(month, day, hour, spv, nbss)
            if pv_now == 0:
                month, day, hour = self.__check_next_hour(month, day, hour)
                if month == 13:
                    return False

                pv_next_hour = dm.get_PV_power(month, day, hour, spv, nbss)
                price_now = dm.get_prices_electricity(month, day, hour-1)
                price_next_hour = dm.get_prices_electricity(month, day, hour)

                # busy_sockets = sum([s.busy for s in self.sockets])
                if  pv_next_hour > 0 or price_now > price_next_hour:
                    ind = 0
                    while self.postponed_batteries < F and ind < self.n_sockets:
                        # print(ind)
                        if self.sockets[ind].busy:
                            if not self.sockets[ind].battery.booked:
                                self.sockets[ind].is_charging = False
                                self.cnt += 1
                                self.n_charging -= 1
                                self.postponed_batteries += 1
                        ind += 1

                    return True

        return False

    def resume_charge(self, time):
        for s in self.sockets:
            if s.busy:
                if not s.is_charging:
                    s.postpone_timer -= 1
                    
                    
                
                if s.postpone_timer <= 0:
                    s.is_charging = True
                    s.postpone_time += time - s.battery.last_update
                    s.battery.last_update = time
                    self.postponed_batteries = 0

    def __check_next_hour(self, month, day, hour):
        if hour + 1 == 24:
            if day == monthrange(2019, month)[1]:
                return month + 1, 1, 0
            else:
                return month, day + 1, 0
        else:
            return month, day, hour + 1