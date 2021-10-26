import random
import warnings
from calendar import monthrange
from queue import PriorityQueue

import numpy as np

import config as conf
from components.socket import Socket
from components.battery import Battery
from components.ev import EV
from components.bss import BSS
from components.pv_surplus_handler import PV_surplus_handler
from data_manager import DatasetManager
from statistics import Statistics

dm = DatasetManager()
pv_production = dm.get_pv_data()
pv_surplus = PV_surplus_handler()


def next_arrival():
    return random.expovariate(0.75 / conf.arrival_rate[conf.HOUR])


def arrival(time, ev, QoE, bss, stats):
    update_all_batteries(time, bss, stats, 0)

    if ev.status == "just_arrived":

        stats.daily_arr[conf.HOUR] += 1
        stats.arrivals[conf.DAY] += 1
        stats.avg_ready[conf.DAY] += bss.ready_batteries

        # Schedule the next arrival
        QoE.put((time + next_arrival(), "3_arrival", EV(random.uniform(conf.C * 0.2, conf.C * 0.4), 0)))

        queue = bss.queue

        if bss.ready_batteries > 0:
            bss.ready_batteries -= 1
            battery = ev.battery

            bss.plug_battery(time, battery)

        else:  # There are no ready batteries
            next_ready, battery_booked, socket_booked = bss.book_battery(time, conf.WMAX)

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
        bss.postpone(time, dm, conf.MONTH, conf.CURRENT_DAY, conf.HOUR)


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
        n = sum([s.is_charging for s in sockets])
        PVpower = dm.get_PV_power(conf.MONTH, conf.CURRENT_DAY, conf.HOUR, n)

    threshold = conf.C if not conf.check_high_demand() else conf.BTH
    threshold *= conf.TOL

    for socket in sockets:
        p_pv = 0
        if socket.busy:
            pv_available = PVpower * (time - socket.battery.last_update) / 60
            if socket.is_charging:
                cost, power, p_pv, _, tot_power = socket.battery.update_charge(time, PVpower, price, pv_surplus)

                stats.cost[conf.DAY] += cost
                stats.consumption[conf.DAY] += power  # grid
                stats.spv_production[conf.DAY] += p_pv  # pv
                stats.total_consumption[conf.DAY] += tot_power  # total

            if socket.battery.charge > threshold:
                socket.unplug_battery()
                bss.ready_batteries += 1

                if not queue.empty():
                    ev = queue.get()
                    socket.plug_battery(ev.battery, time)
                    bss.ready_batteries -= 1
                    ev.status = "served"

            if socket.is_charging and PVpower > conf.CR:
                # Sell surplus of pv energy for half of the price
                # stats.saving[conf.DAY] += pv_surplus.sell_energy(pv_available - p_pv, price, time)
                # if pv_available - p_pv > conf.CR:
                #     print(1, pv_available - p_pv)
                pv_surplus.store_energy(pv_available - p_pv, time, price, stats)

    for socket in sockets:
        if socket.busy:
            next_ready = min(socket.battery.time_to_ready(time), next_ready)

    if (next_ready + time, "0_battery_available", None) not in QoE.queue:
        QoE.put((next_ready + time, "0_battery_available", None))

    stats.last_update = time

    if not conf.check_high_demand() and conf.F > 0:
        bss.postpone(time, dm, conf.MONTH, conf.CURRENT_DAY, conf.HOUR)


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
        n = sum([s.is_charging for s in sockets])
        if n > 0:
            PVpower = dm.get_PV_power(conf.MONTH, conf.CURRENT_DAY, conf.HOUR, n)
        else:
            PVpower = dm.get_PV_power(conf.MONTH, conf.CURRENT_DAY, conf.HOUR, 1)
            time_0 = pv_surplus.last_update
            # stats.saving[conf.DAY] += pv_surplus.sell_energy(PVpower, price, time)
            # if PVpower * (time - time_0) / 60 > conf.CR:
            #     print(2, PVpower * (time - time_0) / 60, time, time_0)
            pv_surplus.store_energy(PVpower * (time - time_0) / 60, time, price, stats)

    threshold = conf.C if not conf.check_high_demand() else conf.BTH
    threshold *= conf.TOL

    for socket in sockets:
        p_pv = 0
        if socket.busy:
            pv_available = PVpower * (time - socket.battery.last_update) / 60
            if socket.is_charging:
                cost, power, p_pv, _, tot_power = socket.battery.update_charge(time, PVpower, price, pv_surplus)

                stats.cost[conf.DAY] += cost
                stats.consumption[conf.DAY] += power
                stats.spv_production[conf.DAY] += p_pv
                stats.total_consumption[conf.DAY] += tot_power

                if socket.battery.charge >= threshold:
                    socket.unplug_battery()
                    bss.ready_batteries += 1

            if socket.is_charging and PVpower > conf.CR:
                # Sell surplus of pv energy for half of the price
                # stats.saving[conf.DAY] += pv_surplus.sell_energy(pv_available - p_pv, price, time)
                # if pv_available - p_pv > conf.CR:
                #     print(3, pv_available - p_pv)
                pv_surplus.store_energy(pv_available - p_pv, time, price, stats)

    stats.last_update = time

    if QoE:
        set_time(QoE, stats)
        bss.resume_charge(time)
    return


def set_time(QoE, stats):
    stats.stored_energy[conf.HOUR + 24 * (conf.DAY - 1)] = pv_surplus.max_stored
    conf.HOUR += 1

    if conf.HOUR == 24:
        stats.compute_daily_stats(conf.DAY)
        conf.HOUR = 0
        conf.DAY += 1
        conf.CURRENT_DAY += 1

        if conf.CURRENT_DAY > monthrange(2019, conf.MONTH)[1]:
            conf.CURRENT_DAY = 1
            conf.MONTH += 1

            if conf.MONTH > 12:
                conf.HOUR = 0
                conf.CURRENT_DAY = 1
                conf.MONTH = 1

        set_f(conf.MONTH, conf.DAY)

    QoE.put((60 * (conf.HOUR + 1) + ((conf.DAY - 1) * 24 * 60), "1_change_hour", None))


def set_f(m, d):
    if 3 <= m <= 5:  # spring
        conf.F = 20
        conf.TMAX = 480
    elif 6 <= m <= 8:  # summer
        conf.F = 20
        conf.TMAX = 480
    elif 9 <= m <= 11:  # fall
        conf.F = 16
        conf.TMAX = 480
    elif m == 12 or m == 1 or m == 2:  # winter
        conf.F = 13
        conf.TMAX = 540


def reset_time():
    conf.DAY = 1
    conf.HOUR = 0
    conf.CURRENT_DAY = 1
    conf.MONTH = 1
    pv_surplus.last_update = 0


def simulate():
    warnings.filterwarnings("ignore")
    random.seed(1)

    reset_time()
    set_f(conf.MONTH, conf.DAY)
    time = 0

    QoE = PriorityQueue()
    # Schedule the first arrival at t=0
    QoE.put((60, "1_change_hour", None))
    QoE.put((0, "3_arrival", EV(random.uniform(conf.C * 0.2, conf.C * 0.4), 0)))

    bss = BSS()
    sockets = list()
    for i in range(conf.NBSS):
        s = Socket()
        s.bss = bss
        s.plug_battery(Battery(charge=random.uniform(conf.C * 0.2, conf.C * 0.4)), time)
        sockets.append(s)
    bss.sockets = sockets
    bss.n_charging = len(sockets)
    bss.n_sockets = len(sockets)

    random.seed(2)

    stats = Statistics()

    previous_time = -1

    while time < conf.SIM_TIME:

        (time, event, ev) = QoE.get()
        if time > conf.SIM_TIME:
            print(time)
            break
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

        bss.pb_integral[conf.HOUR] += bss.postponed_batteries * (time - bss.pb_last_update)

        if event == "3_arrival":
            arrival(time, ev, QoE, bss, stats)

        elif event == "2_serve_queue":
            serve_queue(time, bss, stats)

        elif event == "1_change_hour":
            bss.pb_integral[conf.HOUR] /= 60
            bss.pb_last_update = 60 * conf.HOUR + ((conf.DAY - 1) * 24 * 60)
            update_all_batteries(time, bss, stats, QoE)

        elif event == "0_battery_available":
            battery_available(time, QoE, bss, stats)

    stats.pb_integral = bss.pb_integral

    # Print statistics
    print("Mean arrivals: %f" % (np.mean(list(stats.arrivals.values()))))
    print("Mean loss: %f" % (np.mean(list(stats.loss.values()))))
    print("Mean cost: %f" % (np.mean(list(stats.cost.values()))))
    print("Mean net cost: %f" % (np.mean(list(stats.net_cost.values()))))
    print("Max PV stored energy: %f" % pv_surplus.max_stored)
    c = np.mean(list(stats.cost.values()))
    a = np.mean(list(stats.arrivals.values()))
    l = np.mean(list(stats.loss.values()))
    print("Cost per service: %f" % (c / (a - l)))
    print("Mean consumption: %f" % (np.mean(list(stats.total_consumption.values()))))
    print("Mean grid consumption: %f" % (np.mean(list(stats.consumption.values()))))
    print("Mean SPV: %f" % np.mean(list(stats.spv_production.values())))
    print("Mean saving: %f" % np.mean(list(stats.saving.values())))

    return stats


if __name__ == "__main__":
    stats = simulate()
    stats.plot_stats()
