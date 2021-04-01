import random
import config as conf


class Battery:

    def __init__(self, charge=random.gauss(conf.C * 0.2, 1000), last_update=0):
        self.charge = 0 if charge < 0 else charge
        self.charge = conf.C * 0.4 if charge > conf.C * 0.4 else charge
        self.last_update = last_update
        self.booked = False

    def update_charge(self, time, PVpower, price):
        C = conf.C
        CR = conf.CR
        PV_SET = conf.PV_SET

        charge_0 = self.charge

        power_update = (time - self.last_update) / 60  # Amount of power consumed
        if power_update < 0:
            raise Exception('Negative power update')

        price_power_update = 0

        if PVpower != 0 and PV_SET:  # Check if the PV has power
            # Take the power from the PV avoiding the maximum charging rate is exceeded
            if PVpower > CR:
                power_update *= CR
                self.charge = self.charge + power_update

                power_from_grid = 0
                power_from_pv = power_update
            else:
                CR_grid = CR - PVpower
                # Take the power from the PV and the grid
                power_update_pv = power_update * PVpower
                power_update_grid = power_update * CR_grid

                self.charge = self.charge + power_update_pv + power_update_grid
                price_power_update = price * power_update_grid * 1e-6

                power_from_grid = power_update_grid
                power_from_pv = power_update_pv
        else:
            power_update *= CR  # Take the power from the grid
            self.charge = self.charge + power_update
            price_power_update = price * power_update * 1e-6

            power_from_grid = power_update
            power_from_pv = 0

        self.last_update = time
        return price_power_update, power_from_grid, power_from_pv, self.charge - charge_0

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
