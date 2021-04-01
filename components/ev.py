from components.battery import Battery


class EV:
    def __init__(self, charge, arrival_time):
        self.status = "just_arrived"  # "waiting" "served"
        self.battery = Battery(charge=charge)
        self.arrival_time = arrival_time
        self.service_time = 0  # What time EV is served (used in case of waiting)

    def __lt__(self, other):
        return self.arrival_time < other.arrival_time
