import config as conf


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
        self.is_charging = True
        self.battery = battery
        self.battery.last_update = time
        self.bss.n_charging += 1

    def unplug_battery(self):
        self.busy = False
        self.is_charging = False
        self.battery = None
        self.bss.n_charging -= 1
