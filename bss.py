from queue import PriorityQueue
from calendar import monthrange
import config as conf


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
                    return

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

                    return

        return

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
