import random
import config as conf
from calendar import monthrange
from queue import PriorityQueue


## Socket ##
class Socket:

    def __init__(self):
        self.bss = None
        self.battery = None
        self.busy = False
        self.is_charging = True
        self.postpone_time = 0
        self.postpone_timer = int(conf.TMAX / 60)

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
        C = conf.C
        CR = conf.CR
        PV_SET = conf.PV_SET

        power_update = (time - self.last_update) / 60  # Hours
        if power_update < 0:
            raise Exception('Negative power update')

        price_power_update = 0

        if PVpower != 0 and PV_SET:  # Check if the PV has power
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
            power_update *= CR  # Take the power from the grid
            self.charge = self.charge + power_update
            price_power_update = price * power_update * 1e-6

        # print(self.charge, '/', C)
        self.last_update = time
        return price_power_update, power_update

    def time_to_ready(self, time):
        C = conf.C
        BTH = conf.BTH
        CR = conf.CR
        hour = conf.HOUR
        day = conf.DAY

        delta_t = 0

        while True:
            FC = C if conf.check_high_demand(hour) else BTH  # Full charge
            time_to_ch = 60 * (hour + 1) + ((day - 1) * 24 * 60) - time  # Time to change hour

            t = (FC - self.charge) * 60 / CR
            if t > time_to_ch:
                delta_t += time_to_ch

            elif 0 < t < time_to_ch:
                delta_t += t
                return delta_t

            elif t < 0:
                return delta_t

            hour += 1


## Electric Vehicle ##
class EV:
    def __init__(self, charge, arrival_time):
        self.status = "just_arrived"  # "waiting" "served"
        self.battery = Battery(charge=charge)
        self.arrival_time = arrival_time
        self.service_time = 0  # What time EV is served (used in case of waiting)

    def __lt__(self, other):
        return self.arrival_time < other.arrival_time


## Battery Switch Station ##
class BSS:
    def __init__(self, sockets=[]):
        self.sockets = sockets
        self.queue = PriorityQueue()
        self.n_sockets = len(sockets)
        self.n_charging = 0
        self.ready_batteries = 0
        self.postponed_batteries = 0
        self.resume_charge_flag = False

    def plug_battery(self, time, battery):
        for socket in self.sockets:  # Plug battery in the first free socket
            if not socket.busy:
                socket.plug_battery(battery, time)
                break

    def book_battery(self, time, wmax):
        next_ready = 60 * conf.C / conf.CR  # Max time to charge a battery (2h)
        battery_booked = None
        socket_booked = None

        for socket in self.sockets:  # Look for a charging battery not booked yet
            if socket.busy and socket.is_charging and not socket.battery.booked:

                if socket.battery.time_to_ready(time) < next_ready:
                    next_ready = socket.battery.time_to_ready(time)
                    battery_booked = socket.battery  # Book a battery if ready_batteries is 0
                    socket_booked = socket

        if battery_booked and next_ready < wmax:
            return next_ready, battery_booked, socket_booked
        else:
            # Comment else condition if EV cannot take postponed batteries
            for socket in self.sockets:
                if socket.busy and not socket.battery.booked:

                    if socket.battery.time_to_ready(time) < next_ready:
                        next_ready = socket.battery.time_to_ready(time)
                        battery_booked = socket.battery
                        socket_booked = socket

        return next_ready, battery_booked, socket_booked

    def postpone_charge(self, time, dm, month, day, hour):
        h = int((time + conf.TMAX - (conf.DAY - 1) * 24 * 60) / 60)
        if h >= hour + 1:

            pv_now = dm.get_PV_power(month, day, hour)
            if pv_now == 0:
                month, day, hour = self.__check_next_hour(month, day, hour)
                if month == 13:
                    return False

                pv_next_hour = dm.get_PV_power(month, day, hour)
                price_now = dm.get_prices_electricity(month, day, hour - 1)
                price_next_hour = dm.get_prices_electricity(month, day, hour)

                # busy_sockets = sum([s.busy for s in self.sockets])
                if pv_next_hour > 0 or price_now > price_next_hour:
                    ind = 0
                    while self.postponed_batteries < conf.F and ind < self.n_sockets:
                        # print(ind)
                        if self.sockets[ind].busy:
                            if not self.sockets[ind].battery.booked:
                                self.sockets[ind].is_charging = False
                                # self.cnt += 1
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
