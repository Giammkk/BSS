import json

pv = json.loads(open('data/PVproduction_PanelSize1kWp.json', 'r').read())

print(pv[str(2)][str(19)][str(7)] * 100)