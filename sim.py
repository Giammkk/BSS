import random
import sys
import warnings
from calendar import monthrange
from queue import PriorityQueue

import numpy as np

import config as conf
from components import Socket, Battery, EV, BSS
from data_manager import DatasetManager
from plot import Plot
from statistics import Statistics

dm = DatasetManager()
pv_production = dm.get_pv_data()


def next_arrival():
    return random.expovariate(1 / conf.arrival_rate[conf.HOUR])


def arrival(time, ev, QoE, bss, stats):
    update_all_batteries(time, bss, stats, 0)

    if ev.status == "just_arrived":

        stats.daily_arr[conf.HOUR] += 1
        stats.arrivals[conf.DAY] += 1
        stats.avg_ready[conf.DAY] += bss.ready_batteries

        # Schedule the next arrival
        QoE.put((time + next_arrival(), "3_arrival", EV(random.gauss(8000, 1000), 0)))

        queue = bss.queue
        update_all_batteries(time, bss, stats, 0)

        if bss.ready_batteries > 0:
            bss.ready_batteries -= 1
            battery = ev.battery

            bss.plug_battery(time, battery)

        else:  # There are no ready batteries
            next_ready, battery_booked, socket_booked = bss.book_battery(time)

            if battery_booked and next_ready < conf.WMAX:
                # EV waits
                stats.avg_wait[conf.DAY] += next_ready

                battery_booked.booked = True
                socket_booked.is_charging = True  # Reactivate charging if battery has been booked
                queue.put(ev)
                ev.status = "waiting"
                ev.service_time = next_ready + time
                QoE.put((next_ready + time, "2_serve_queue", ev))

            else:
                stats.loss[conf.DAY] += 1

    if not conf.check_high_demand() and conf.F > 0:
        r_c = bss.postpone_charge(time, dm, conf.MONTH, conf.CURRENT_DAY, conf.HOUR)
        bss.resume_charge_flag = r_c


## Serve waiting EV ##
def serve_queue(time, bss, stats):
    update_all_batteries(time, bss, stats, 0)

    ev = bss.queue.get()
    if ev.status == "waiting":
        bss.plug_battery(time, ev.battery)


## Departure ##
def battery_available(time, QoE, bss, stats):
    """
    One of the batteries is fully charged.
    """
    sockets = bss.sockets
    queue = bss.queue
    price = dm.get_prices_electricity(conf.MONTH, conf.DAY, conf.HOUR)
    next_ready = 60 * conf.C / conf.CR

    stats.len_queue[conf.DAY] += len(queue.queue) * (time - stats.last_update)
    stats.busy_sockets[conf.DAY] += sum([s.busy for s in sockets]) * (time - stats.last_update)

    # print(HOUR, DAY)
    PVpower = 0
    if conf.PV_SET:
        PVpower = dm.get_PV_power(conf.MONTH, conf.CURRENT_DAY, conf.HOUR)
        # Divide the energy produced by the PVs by the active sockets
        try:  # Handle division by zero
            PVpower /= sum([s.is_charging * s.busy for s in sockets])
        except:
            pass

    threshold = conf.C if conf.check_high_demand() else conf.BTH
    threshold *= conf.TOL

    for socket in sockets:
        if socket.busy:
            if socket.is_charging:
                cost, power = socket.battery.update_charge(time, PVpower, price)
                stats.cost[conf.DAY] += cost
                stats.consumption[conf.DAY] += power

            if socket.battery.charge > threshold:
                socket.unplug_battery()
                bss.ready_batteries += 1

                if not queue.empty():
                    ev = queue.get()
                    # print(ev)
                    socket.plug_battery(ev.battery, time)
                    bss.ready_batteries -= 1
                    ev.status = "served"

    for socket in sockets:
        if socket.busy:
            next_ready = min(socket.battery.time_to_ready(time), next_ready)

    if (next_ready + time, "0_battery_available", None) not in QoE.queue:
        QoE.put((next_ready + time, "0_battery_available", None))

    stats.last_update = time

    if not conf.check_high_demand() and conf.F > 0:
        r_c = bss.postpone_charge(time, dm, conf.MONTH, conf.CURRENT_DAY, conf.HOUR)
        bss.resume_charge_flag = r_c


## Change Hour ##
def update_all_batteries(time, bss, stats, QoE=None):
    """
    Since every hour electricity price and PV production change, the charge of
    the batteries must be update with the right parameters.
    """
    sockets = bss.sockets
    queue = bss.queue
    price = dm.get_prices_electricity(conf.MONTH, conf.DAY, conf.HOUR)

    stats.len_queue[conf.DAY] += len(queue.queue) * (time - stats.last_update)
    stats.busy_sockets[conf.DAY] += sum([s.busy for s in sockets]) * (time - stats.last_update)

    PVpower = 0
    if conf.PV_SET:
        PVpower = dm.get_PV_power(conf.MONTH, conf.CURRENT_DAY, conf.HOUR)

    threshold = conf.C if conf.check_high_demand() else conf.BTH
    threshold *= conf.TOL

    for socket in sockets:
        if socket.busy and socket.is_charging:
            cost, power = socket.battery.update_charge(time, PVpower, price)
            stats.cost[conf.DAY] += cost
            stats.consumption[conf.DAY] += power

            if socket.battery.charge >= threshold:
                socket.unplug_battery()
                bss.ready_batteries += 1

    stats.last_update = time
    if bss.resume_charge_flag:
        bss.resume_charge(time)

    if QoE:
        set_time(QoE, stats)
    return


def set_time(QoE, stats):
    conf.HOUR += 1

    if conf.HOUR == 24:
        stats.compute_daily_stats(conf.DAY)
        conf.HOUR = 0
        conf.DAY += 1
        conf.CURRENT_DAY += 1

        if conf.CURRENT_DAY > monthrange(2019, conf.MONTH)[1]:
            conf.CURRENT_DAY = 1
            conf.MONTH += 1

    QoE.put((60 * (conf.HOUR + 1) + ((conf.DAY - 1) * 24 * 60), "1_change_hour", None))


def reset_time():
    conf.DAY = 1
    conf.HOUR = 0
    conf.CURRENT_DAY = 1
    conf.MONTH = 1


def simulate():
    warnings.filterwarnings("ignore")
    random.seed(1)
    time = 0
    reset_time()

    QoE = PriorityQueue()
    # Schedule the first arrival at t=0
    QoE.put((0, "3_arrival", EV(random.gauss(8000, 1000), 0)))
    QoE.put((60, "1_change_hour", None))

    bss = BSS()
    sockets = list()
    for i in range(conf.NBSS):
        s = Socket()
        s.bss = bss
        s.plug_battery(Battery(charge=random.gauss(8000, 1000)), time)
        sockets.append(s)
    bss.sockets = sockets
    bss.n_charging = len(sockets)
    bss.n_sockets = len(sockets)

    random.seed(1)

    stats = Statistics()

    previous_time = -1

    while time < conf.SIM_TIME:

        (time, event, ev) = QoE.get()
        if ev:
            ev.arrival_time = time

        # Check if time always increases
        if previous_time > time:
            raise Exception("Error: ", previous_time, time)
        else:
            previous_time = time

        ## DEBUG ##
        # try:
        #     print(event, time, '| Busy sock:', sum([s.busy for s in sockets]),
        #           '| Ready:', bss.ready_batteries, '| Queue', len(bss.queue.queue),
        #           '| Canwait: ', ev.can_wait, '| QoE:', QoE.queue)
        # except :
        #     print(event, time, '| Busy sock:', sum([s.busy for s in sockets]),
        #           '| Ready:', bss.ready_batteries, '| Queue', len(bss.queue.queue),
        #           '| QoE:', QoE.queue)

        if event == "3_arrival":
            arrival(time, ev, QoE, bss, stats)

        elif event == "2_serve_queue":
            serve_queue(time, bss, stats)

        elif event == "1_change_hour":
            update_all_batteries(time, bss, stats, QoE)

        elif event == "0_battery_available":
            battery_available(time, QoE, bss, stats)

    # Print statistics
    print("Mean arrivals: %f" % (np.mean(list(stats.arrivals.values()))))
    print("Mean loss: %f" % (np.mean(list(stats.loss.values()))))
    print("Mean cost: %f" % (np.mean(list(stats.cost.values()))))

    return stats


if __name__ == "__main__":
    stats = simulate()
    stats.plot_stats()
