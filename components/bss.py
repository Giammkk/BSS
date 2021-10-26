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
        self.pb_integral = {i: 0 for i in range(24)}
        self.pb_last_update = 0
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
        # else:
        #     # Comment else condition if EV cannot take postponed batteries
        #     for socket in self.sockets:
        #         if socket.busy and not socket.battery.booked:
        #
        #             if socket.battery.time_to_ready(time) < next_ready:
        #                 next_ready = socket.battery.time_to_ready(time)
        #                 battery_booked = socket.battery
        #                 socket_booked = socket

        return next_ready, battery_booked, socket_booked

    def postpone_charge(self, time, dm, month, day, hour):
        month_now = month
        day_now = day
        hour_now = hour
        h = int((time + conf.TMAX - (conf.DAY - 1) * 24 * 60) / 60)
        if h > hour_now:

            pv_now = dm.get_PV_power(month_now, day_now, hour_now)
            if pv_now == 0:
                month, day, hour = self.__check_next_hour(month, day, h)
                if month == 13:
                    return

                # pv_next_hour = dm.get_PV_power(month, day, hour)
                # price_now = dm.get_prices_electricity(month_now, day_now, hour_now)
                # price_next_hour = dm.get_prices_electricity(month, day, hour)

                # busy_sockets = sum([s.busy for s in self.sockets])
                # if pv_next_hour > 0 or price_now > price_next_hour:
                ind = 0
                while self.postponed_batteries < conf.F and ind < self.n_sockets:
                    # print(ind)
                    if self.sockets[ind].busy and self.sockets[ind].is_charging:
                        if self.__check_convenience(time, self.sockets[ind].battery.charge, dm, month, day, hour,
                                                    month_now, day_now, hour_now):
                            if not self.sockets[ind].battery.booked:
                                self.sockets[ind].is_charging = False
                                self.sockets[ind].postpone_timer = int(conf.TMAX / 60)
                                self.n_charging -= 1
                                self.postponed_batteries += 1
                    ind += 1

                return

        return

    def postpone_charge_2(self, time, dm, month, day, hour):
        """
        Second strategy of postponing the charge of the batteries.
        Try to pick the best hour to wake up. Values of TMAX are: 1, 2 ...
        """
        # pvs = [dm.get_PV_power(month, day, hour)]
        prices = [dm.get_prices_electricity(month, day, hour)]

        for i in range(int(time)):
            month, day, hour = self.__check_next_hour(month, day, hour + 1)
            if month == 13:
                return

            # pvs.append(dm.get_PV_power(month, day, hour))
            prices.append(dm.get_prices_electricity(month, day, hour))

        # max_pv = max(pvs)
        # max_pv_ind = pvs.index(max_pv)

        # t = max_pv_ind if max_pv > 20 else prices.index(min(prices))
        t = prices.index(min(prices))

        ind = 0
        while self.postponed_batteries < conf.F and ind < self.n_sockets:
            if self.sockets[ind].busy and self.sockets[ind].is_charging:
                if not self.sockets[ind].battery.booked:
                    self.sockets[ind].is_charging = False
                    self.sockets[ind].postpone_timer = t
                    self.n_charging -= 1
                    self.postponed_batteries += 1
            ind += 1

        return

    def postpone_charge_3(self, time, dm, month, day, hour):
        month_now = month
        day_now = day
        hour_now = hour
        h = int((time + conf.TMAX - (conf.DAY - 1) * 24 * 60) / 60)
        if h > hour_now:

            pv_now = dm.get_PV_power(month_now, day_now, hour_now)
            if pv_now == 0:

                ind = 0
                while self.postponed_batteries < conf.F and ind < self.n_sockets:
                    if self.sockets[ind].busy and self.sockets[ind].is_charging:
                        convenience = self.__check_convenience3(time, self.sockets[ind].battery.charge, dm, month, day,
                                                                hour)
                        if convenience:
                            if not self.sockets[ind].battery.booked:
                                self.sockets[ind].is_charging = False
                                self.sockets[ind].postpone_timer = convenience
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

                if s.postpone_timer <= 0 and not s.is_charging:
                    s.is_charging = True
                    s.postpone_time += time - s.battery.last_update
                    s.battery.last_update = time
                    self.postponed_batteries -= 1

    def __check_next_hour(self, month, day, hour):
        if hour >= 24:
            if day == monthrange(2019, month)[1]:
                return month + 1, 1, hour - 24
            else:
                return month, day + 1, hour - 24
        else:
            return month, day, hour

    def __check_convenience(self, time, charge, dm, month, day, hour, month_now, day_now, hour_now):
        """
        If price now is greater than later this function return True and the charge is postponed.
        """
        price_now = dm.get_prices_electricity(month_now, day_now, hour_now)
        pv_now = dm.get_PV_power(month_now, day_now, hour_now)
        pv_next = dm.get_PV_power(month, day, hour)
        price_next = dm.get_prices_electricity(month, day, hour)

        if charge > conf.C / 2:
            return pv_next > 0  # price_now > price_next
        else:
            month_now_2, day_now_2, hour_now_2 = self.__check_next_hour(month_now, day_now, hour_now + 1)
            month_2, day_2, hour_2 = self.__check_next_hour(month, day, hour + 1)

            if month_2 == 13:
                return

            # price_now_2 = dm.get_prices_electricity(month_now_2, day_now_2, hour_now_2)
            # price_next_2 = dm.get_prices_electricity(month_2, day_2, hour_2)

            pv_now_2 = dm.get_PV_power(month_now_2, day_now_2, hour_now_2)
            pv_next_2 = dm.get_PV_power(month_2, day_2, hour_2)

            return pv_now + pv_now_2 > pv_next + pv_next_2
            # return price_now + price_now_2 > price_next + price_next_2

    def __check_convenience2(self, time, charge, dm, month, day, hour, month_now, day_now, hour_now):
        time_to_ch = 60 * (hour_now + 1) + ((conf.DAY - 1) * 24 * 60) - time
        price_now = dm.get_prices_electricity(month_now, day_now, hour_now)
        price_next = dm.get_prices_electricity(month, day, hour)

        if charge > conf.C / 2:
            return price_now > price_next
        else:
            month_now_2, day_now_2, hour_now_2 = self.__check_next_hour(month_now, day_now, hour_now + 1)
            month_2, day_2, hour_2 = self.__check_next_hour(month, day, hour + 1)

            if month_2 == 13:
                return

            price_now_2 = dm.get_prices_electricity(month_now_2, day_now_2, hour_now_2)
            price_next_2 = dm.get_prices_electricity(month_2, day_2, hour_2)

            delta_c_1 = conf.CR * time_to_ch / 60
            delta_c_2 = conf.C - delta_c_1 - charge

            convenience = price_now * delta_c_1 + price_now_2 * delta_c_2 > \
                          price_next * delta_c_1 + price_next_2 * delta_c_2

            return convenience

    def __check_convenience3(self, time, charge, dm, month, day, hour):
        m = month
        d = day
        h = hour
        prices = [dm.get_prices_electricity(month, day, hour)]
        convenience = 0

        for i in range(int(conf.TMAX / 60) + 2):
            m, d, h = self.__check_next_hour(m, d, h + 1)
            if m == 13:
                return

            prices.append(dm.get_prices_electricity(m, d, h))

        if charge > conf.C / 2:
            convenience = prices.index(min(prices[:-1]))
        else:
            # print(120)
            time_to_ch = 60 * (hour + 1) + ((conf.DAY - 1) * 24 * 60) - time
            delta_c_1 = conf.CR * time_to_ch / 60
            delta_c_2 = conf.C - delta_c_1 - charge
            cost_min = -1
            for i in range(int(conf.TMAX / 60) + 1):
                # print(i)
                cost = prices[i] * delta_c_1 + prices[i + 1] * delta_c_2
                if cost_min < 0 or cost < cost_min:
                    convenience = i
                    cost_min = cost

        # print(convenience)
        return convenience

    def postpone(self, time, dm, month, day, hour):
        # if 0 <= hour <= 3 or hour >= 22:
        # self.postpone_charge_2(5, dm, month, day, hour)
        # else:
        self.postpone_charge(time, dm, month, day, hour)
