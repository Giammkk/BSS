import json
import pandas as pd

class DatasetManager:
    def __init__(self):
        prices = pd.read_csv('data/electricity_prices.csv', header=None)
        self.prices_winter = [float(i) for i in prices.loc[prices[1] == 'WINTER'][2].tolist()]
        self.prices_spring = [float(i) for i in prices.loc[prices[1] == 'SPRING'][2].tolist()]
        self.prices_summer = [float(i) for i in prices.loc[prices[1] == 'SUMMER'][2].tolist()]
        self.prices_fall   = [float(i) for i in prices.loc[prices[1] == 'FALL'][2].tolist()]

        self.pv_production = json.loads(open('data/PVproduction_PanelSize1kWp.json', 'r').read())


    def get_pv_data(self):
        return self.pv_production


    def get_prices_electricity(self, m, d, h):
        """
        Return the list of the electricity prices by hours of a day given a season.
        """
        if m==1 or m==2 or (m==3 and d<20) or (m==12 and d>=21):
            pc = self.prices_winter
        elif (m==3 and d>=20) or m==4 or m==5 or (m==6 and d<20):
            pc = self.prices_spring
        elif (m==6 and d>=20) or m==7 or m==8 or (m==9 and d<22):
            pc = self.prices_summer
        elif (m==9 and d>=22) or m==10 or m==11 or (m==12 and d<21):
            pc = self.prices_fall

        return pc[h]
    
    
    def get_PV_power(self, m, d, h, spv, nbss):
        return self.pv_production[str(m)][str(d)][str(h)] * spv / nbss