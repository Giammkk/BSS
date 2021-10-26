import config as conf


class PV_surplus_handler:

    def __init__(self):
        self.last_update = 0
        self.stored_energy = 0
        self.max_stored = 0
        self.capacity = 0  # conf.C * 5

    def sell_energy(self, power, price, time):
        self.last_update = time
        # print(conf.MONTH, conf.DAY, conf.HOUR, 0.5 * price, power)
        return 0.5 * price * power * 1e-6

    def store_energy(self, energy, time, price, stats):
        # if energy > 10000:
        #     print(energy)
        self.stored_energy += energy
        self.last_update = time

        self.max_stored = self.stored_energy

        if self.stored_energy > self.capacity:
            stats.saving[conf.DAY] += self.sell_energy(self.stored_energy - self.capacity, price, time)
            self.stored_energy = self.capacity

    def drain_energy(self, request):
        if self.stored_energy >= request:
            self.stored_energy -= request
            return request
        elif 0 < self.stored_energy < request:
            request = self.stored_energy
            self.stored_energy = 0
            return request
        else:
            return 0
