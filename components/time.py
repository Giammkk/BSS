from calendar import monthrange


class Time:

    def __init__(self):
        self.sim_last = 365  # Last of simulation (days)
        self.sim_time = 60 * 24 * self.sim_last
        self.day = 1  # Day of the simulation (from 1 to 365)
        self.hour = 0  # Current hour (from 0 to 23)
        self.current_day = 1  # Current day (from 1 to 30/31/28)
        self.month = 1  # Current month in the simulation

    def set_time(self, stats):
        self.hour += 1

        if self.hour == 24:
            stats.compute_daily_stats(self.day)
            self.hour = 0
            self.DAY += 1
            self.current_day += 1

            if self.current_day > monthrange(2019, self.month)[1]:
                self.current_day = 1
                self.month += 1

    @staticmethod
    def check_next_hour(month, day, hour):
        if hour >= 24:
            if day == monthrange(2019, month)[1]:
                return month + 1, 1, hour - 24
            else:
                return month, day + 1, hour - 24
        else:
            return month, day, hour

    def reset_time(self):
        self.day = 1
        self.hour = 0
        self.current_day = 1
        self.month = 1
