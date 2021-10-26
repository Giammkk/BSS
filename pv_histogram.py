import pandas as pd
import matplotlib.pyplot as plt
import json, numpy
from calendar import monthrange
from data_manager import DatasetManager

pv_df = pd.read_csv("../data/PVproduction_PanelSize1kWp.csv")
print(pv_df.where(pv_df['Output power (W)'] != 0).dropna().describe())

pv = json.loads(open('../data/PVproduction_PanelSize1kWp.json', 'r').read())

avg_pv_by_day = {i + 1: 0 for i in range(365)}
ind = 0

for m in range(1, 13):
    for d in range(1, monthrange(2019, m)[1] + 1):
        ind += 1
        for h in range(24):
            avg_pv_by_day[ind] += float(pv[str(m)][str(d)][str(h)])
        # avg_pv_by_day[ind] /= 24

plt.figure()
plt.xlim((0, 365))

d = 0
for m in range(1, 13):
    d += monthrange(2019, m)[1]
    plt.axvline(d, linestyle='--', c='r')

# plt.axvline(80, linestyle='--', c='r')
# plt.axvline(172, linestyle='--', c='r')
# plt.axvline(265, linestyle='--', c='r')
# plt.axvline(356, linestyle='--', c='r')
plt.title("PV Daily Production")
plt.xlabel("Day")
plt.ylabel("Power [W]")
plt.hist(range(1, 366, 1), weights=avg_pv_by_day.values(), bins=365)
plt.show()

dm = DatasetManager()
fig = plt.figure()

plt.xlim((0, 23))
ax = fig.add_subplot()
ticks = numpy.arange(0, 23, 1)
ax.set_xticks(ticks, minor=True)
ax.grid(which='both')
ax.grid(which='minor', alpha=0.2)

plt.title("Electricity prices")
plt.ylabel("€ / MWh")
plt.xlabel("Hour of the day")

plt.plot(range(0, 24), dm.prices_winter, label="Winter")
plt.plot(range(0, 24), dm.prices_spring, label="Spring")
plt.plot(range(0, 24), dm.prices_summer, label="Summer")
plt.plot(range(0, 24), dm.prices_fall, label="Fall")

plt.legend()
plt.show()

pv_hour_season = {j: {i: 0 for i in range(24)} for j in range(4)}
ind = {j: 0 for j in range(4)}

for m in range(1, 13):
    for d in range(1, monthrange(2019, m)[1] + 1):
        for h in range(24):
            if m == 1 or m == 2 or (m == 3 and d < 20) or (m == 12 and d >= 21):
                ind[0] += 1
                pv_hour_season[0][h] += float(pv[str(m)][str(d)][str(h)])
            elif (m == 3 and d >= 20) or m == 4 or m == 5 or (m == 6 and d < 20):
                ind[1] += 1
                pv_hour_season[1][h] += float(pv[str(m)][str(d)][str(h)])
            elif (m == 6 and d >= 20) or m == 7 or m == 8 or (m == 9 and d < 22):
                ind[2] += 1
                pv_hour_season[2][h] += float(pv[str(m)][str(d)][str(h)])
            elif (m == 9 and d >= 22) or m == 10 or m == 11 or (m == 12 and d < 21):
                ind[3] += 1
                pv_hour_season[3][h] += float(pv[str(m)][str(d)][str(h)])

for h in range(24):
    for i in range(4):
        pv_hour_season[i][h] = pv_hour_season[i][h] / ind[i]

fig = plt.figure()

plt.xlim((0, 23))
ax = fig.add_subplot()
ticks = numpy.arange(0, 23, 1)
ax.set_xticks(ticks, minor=True)
ax.grid(which='both')
ax.grid(which='minor', alpha=0.2)

plt.title("Average PV power")
plt.ylabel("Power [W]")
plt.xlabel("Hour of the day")

plt.plot(range(0, 24), pv_hour_season[0].values(), label="Winter")
plt.plot(range(0, 24), pv_hour_season[1].values(), label="Spring")
plt.plot(range(0, 24), pv_hour_season[2].values(), label="Summer")
plt.plot(range(0, 24), pv_hour_season[3].values(), label="Fall")

plt.legend()
plt.show()
