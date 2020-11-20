# import json

# file = open("data/PVproduction_PanelSize1kWp.json", "r")
# o = file.read()
# a = json.loads(o)

# file.close()
# class Battery:
    
#     def __init__(self, charge=0, last_update=0):
#         self.charge = 0 if charge < 0 else charge
#         self.charge = 16000 if charge > 16000 else charge
#         self.last_update = last_update
#         self.booked = False
        
# a = None
# b = Battery()

# if a:
#     print("a")
    
# if b:
#     print("b")
import numpy as np
import matplotlib.pyplot as plt

sipv = np.load("siPV.npy")
nopv = np.load("noPV.npy")
title = "Daily cost"

fig = plt.figure()
plt.grid()
plt.title(title)

plt.xlim((0,365))
plt.ylim((np.min(sipv), np.max(nopv)+2))

# if title == "Daily cost":
#     plt.axvline(80, linestyle='--', c='r')
#     plt.axvline(172, linestyle='--', c='r')
#     plt.axvline(265, linestyle='--', c='r')

ax = fig.add_subplot(1, 1, 1)

major_ticks = np.arange(0, 365, 30)
minor_ticks = np.arange(0, 365, 5)

ax.set_xticks(major_ticks)
ax.set_xticks(minor_ticks, minor=True)

ax.grid(which='both')

ax.grid(which='minor', alpha=0.2)
ax.grid(which='major', alpha=0.5)

# if self.yscale:
#     plt.yscale(self.yscale)
#     ticks = self.ticks()
#     ax.set_yticks(ticks)
#     plt.yticks(ticks, [str(s) for s in ticks])
    
plt.plot(range(365), nopv, 'r')
plt.plot(range(365), sipv, 'g')
plt.legend(['PV(5)', 'No PV'])

# if self.save:
#     plt.savefig(f"plots/{self.title}.png")
    
plt.show()