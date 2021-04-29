import pandas as pd
from calendar import monthrange
import json

pv_df = pd.read_csv('data/PVproduction_PanelSize1kWp.csv')

pv_production = {i + 1: {j + 1: {k: 0 for k in range(24)} for j in range(monthrange(2019, i + 1)[1])} for i in
                 range(12)}
for m in range(12):
    for d in range(monthrange(2019, m + 1)[1]):
        for h in range(24):
            pv_production[m + 1][d + 1][h] = float(pv_df.where(pv_df['Month'] == m + 1).
                                                   dropna().where(pv_df['Day'] == d + 1). \
                                                   dropna().where(pv_df['Hour'] == h). \
                                                   dropna()['Output power (W)'])

file = open('data/PVproduction_PanelSize1kWp.json', 'w')
json.dump(pv_production, file)
file.close()
