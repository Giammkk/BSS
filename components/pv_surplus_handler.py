class PV_surplus_handler:

    def __init__(self):
        self.last_update = 0

    def sell_energy(self, power, price, time):
        self.last_update = time
        return 0.5 * price * power * 1e-6
