import pandas as pd
import matplotlib.pyplot as plt
import json
from calendar import monthrange

pv_df = pd.read_csv("../data/PVproduction_PanelSize1kWp.csv")
print(pv_df.where(pv_df['Output power (W)']!=0).dropna().describe())

pv = json.loads(open('../data/PVproduction_PanelSize1kWp.json', 'r').read())

avg_pv_by_day = {i+1 : 0 for i in range(365)}
ind = 0

for m in range(1, 13):
    for d in range(1, monthrange(2019, m)[1]+1):
        ind += 1 
        for h in range(24):
            avg_pv_by_day[ind] += float(pv[str(m)][str(d)][str(h)]) * 100
        # avg_pv_by_day[ind] /= 24

plt.figure()
plt.xlim((0,365))
plt.axvline(80, linestyle='--', c='r')
plt.axvline(172, linestyle='--', c='r')
plt.axvline(265, linestyle='--', c='r')
plt.axvline(356, linestyle='--', c='r')
plt.title("SPV daily production")
plt.xlabel("Day")
plt.ylabel("Power [W]")
plt.hist(range(1,366,1), weights=avg_pv_by_day.values(), bins=365)

# SPV = 100
# NBSS = 1
# avg_pv_by_day = {i+1 : 0 for i in range(365)}
# ind = 0
# for m in range(1,13):
#     for d in range(1, monthrange(2019, m)[1]+1):
#         ind += 1
#         for h in range(24):
#             avg_pv_by_day[ind] += float(pv[str(m)][str(d)][str(h)])
#         avg_pv_by_day[ind] /= 24
#         avg_pv_by_day[ind] *= (SPV/NBSS)
#
# plt.figure()
# plt.xlim((0,365))
# plt.axvline(80, linestyle='--', c='r')
# plt.axvline(172, linestyle='--', c='r')
# plt.axvline(265, linestyle='--', c='r')
# plt.scatter(range(1,366,1), avg_pv_by_day.values(), label="PV")
# # plt.scatter(range(1,366,1), stats.loss.values(), marker='x', label="Loss")
# plt.legend()
plt.show()

