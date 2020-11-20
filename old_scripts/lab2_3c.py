#!/usr/bin/python3

import random
from queue import Queue, PriorityQueue
import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt
# import xlsxwriter 

# ******************************************************************************
# Constants
# ******************************************************************************
SERVICE = 2           # Av charging time ???
ARRIVAL   = 5/60      # Av inter-arrival time
C = 40000               # Battery capacity,
w_max = 30/60          # Maximum waiting time
SIM_TIME = 24         # Simulation time
N_BSS = 6               # Maximum number of batteries that can be plugged
B = 2*N_BSS             # Capacity of the system
pv_set = True           # Indicator of presence of a PV in the BSS
Spv = 500               # Panel size
arrival_fixed = False   # True: if average arrival rate fixed (Point 1)/ False: if variable (Point 2)
Bth = 20000             # Minimum charge level
Month = 7               # Day to simulate
Day = 18                # Month to simulate
f = 0.7                 # Fraction of batteries
Tmax = 1                # Maximum time by which the charge process can be postponed
seed = 100
Post = True


prices = pd.read_csv('../data/electricity_prices.csv', sep=',', header=None,warn_bad_lines=True) 
prices_winter = [float(i) for i in prices.loc[prices[1] == 'WINTER'][2].tolist()] # winter 
prices_spring = [float(i) for i in prices.loc[prices[1] == 'SPRING'][2].tolist()] # spring
prices_summer = [float(i) for i in prices.loc[prices[1] == 'SUMMER'][2].tolist()] # summer
prices_fall   = [float(i) for i in prices.loc[prices[1] == 'FALL'][2].tolist()] # fall
panel_v= pd.read_csv('../data/PVproduction_PanelSize1kWp.csv', sep=',', header=0, warn_bad_lines=True)




# ******************************************************************************
# To take the measurements
# ******************************************************************************
class Measure:
    def __init__(self,Narr,Ndep,NAvgbattery,NAveragebatteryQueue,OldTimeEvent,AverageDelay,AverageWaitDelay,busy_time,lost_packets):
        self.arr = Narr                 #number of arr
        self.dep = Ndep                 #number of departures
        self.ut = NAvgbattery       #number of average batteries
        self.uq = NAveragebatteryQueue  #number of average battery_number in queue line
        self.oldT = OldTimeEvent 
        self.delay = AverageDelay       #average delay
        self.wdelay = AverageWaitDelay  #average waiting delay
        self.busy_time = busy_time      #time that server spends in a busy state
        self.lp=lost_packets            #number of missed services
        
# ******************************************************************************
# battery
# ******************************************************************************
class Battery:
    def __init__(self,type,arrival_time):
        self.type = type
        self.arrival_time = arrival_time

# ******************************************************************************
# BSS
# ******************************************************************************
class BSS(object):

    # constructor
    def __init__(self,is_idle,busy_t,depar_time,post_time,numDep,is_booked):#,bt_per_hour):

        self.idle = is_idle    #whether the server is idle or not
        self.busy_time=busy_t  #time a plug of the BSS is used
        self.pt=post_time      #time a charging process is postponed
        self.dep_num=numDep    #number of departures
        self.booked=is_booked  #indicates if a plug of the BSS is busy or not


# ******************************************************************************
# arrivals 
# ******************************************************************************
def arrival(time, FES, queue, servers):
    global battery_number
    global high_demand
    wait=True
    
    # cumulate statistics
    data.arr += 1
    data.ut += battery_number*(time-data.oldT)
    if battery_number>N_BSS:
        data.uq += (battery_number-N_BSS)*(time-data.oldT)

                
    data.oldT = time

    # schedule the next arrival
    checkHighDemand()
    inter_arrival=interArrivalTimeGeneration()
    FES.put((time + inter_arrival, "2arrival"))

   
    battery_number += 1
    
    if battery_number > N_BSS: #Book a plug of the BSS
        for i in range(len(servers)):
            if not servers[i].booked and (servers[i].dt - time) <= w_max:
                servers[i].booked=True
                wait=True
                break
            else:
                wait=False

    if (battery_number <= B and wait):
        
        battery = Battery(1,time)

        queue.append(battery) # insert the record in the queue
        
        if battery_number <= N_BSS:

            service_time, time_in_BSS, postponed_time, price_pos, price_g=serviceTimeGeneration(time,high_demand)

            total_t=server_assignment(servers,time,service_time, time_in_BSS, postponed_time, price_pos, price_g)

            FES.put((time + total_t, "1departure")) # schedule when the battery will be charged
                
    else:
        data.lp+=1
        battery_number -= 1

        
# ******************************************************************************
# departures 
# ******************************************************************************
def departure(time, FES, queue, servers):
    global battery_number
    global delayed_vans
    global high_demand
    
    battery = queue.pop(0)
    
    for i in range(len(servers)):
        if not servers[i].idle and servers[i].dt==time: 
            servers[i].idle=True
            servers[i].booked=False
            servers[i].dep_num+=1
            break
    
    # cumulate statistics
    data.dep += 1
    data.ut += battery_number * (time-data.oldT)
    
    if battery_number > N_BSS:
        data.uq += (battery_number-N_BSS) * (time-data.oldT)
        delayed_vans += 1
        nextbattery = queue[N_BSS-1]
        data.wdelay += (time-nextbattery.arrival_time)
        #print("*.*.*.*", data.wdelay)
    
    data.delay += (time-battery.arrival_time)
    battery_number -= 1

    checkHighDemand()
    
    if battery_number > N_BSS-1:
        
        service_time, time_in_BSS, postponed_time, price_pos, price_g=serviceTimeGeneration(time,high_demand)
    
        total_t=server_assignment(servers,time,service_time, time_in_BSS, postponed_time, price_pos, price_g)
        
        FES.put((time + total_t, "1departure")) # schedule when the battery will be charged

    data.oldT = time

    
# ******************************************************************************
# Method to check if high demand
# ******************************************************************************     
def checkHighDemand():
    global high_demand
    global arrival_fixed
    if not arrival_fixed:
        high_demand = True if (time>=8 and time<12) or (time>=16 and time<19) else False
    
   
# ******************************************************************************
# Inter-arrival time generation method
# ******************************************************************************     
def interArrivalTimeGeneration(): 
    global high_demand
    if not arrival_fixed:
        if (time<7) or (time>=19): #low demand
            inter_arrival = random.expovariate(1.0/1.5)
        elif (time>=7 and time<8) or (time>=12 and time<16): #Intermediate demand
            inter_arrival = random.expovariate(1.0/0.5)
        elif (time>=8 and time<12) or (time>=16 and time<19): #High demand
            inter_arrival = random.expovariate(1.0/(5/60))
    else:
        inter_arrival = ARRIVAL
    
    return inter_arrival

# ******************************************************************************
# Service time generation method
# ******************************************************************************     
def serviceTimeGeneration(time,high_demand): 
    hour=math.floor(time) if math.floor(time)<24 else math.floor(time)-24*(math.floor(time/24))
    pw=0 
    service_time=0
    time_in_BSS=0
    ind=True
    postponed_time=0
    price_pos=0
    price_g=0
    global price
    last_p=0
    charge_level=random.gauss(8000, 500)
    charge_level=0 if charge_level<0 else charge_level
                      
    charge_level=16000 if charge_level>16000 else charge_level
                          
        
    t_Bth.append(time)
    
    if high_demand:
        cap=Bth-charge_level
        v_Bth.append(Bth)
    else:
        cap=C-charge_level
        v_Bth.append(C)
             
    first_m=0
    x = (Day-1 + (time/24)) 
    while x>0:
        x = x - int(panel_v.where(panel_v['Month']==Month+first_m).dropna().shape[0]/24)
        first_m=first_m+1
    first_m=Month if first_m==0 else Month+first_m-1
    if pv_set: #If the station has a set of PV
        
        #Calculate the service time without postpone battery charging------------------------

        for m in range(first_m, 13):
        
            first_d = math.floor(Day + (time/24))
            
            for d in range(first_d,int(panel_v.where(panel_v['Month']==m).dropna().shape[0]/24)): #Iterate over days
                
                pv=panel_v.where(panel_v['Month']==m).where(panel_v['Day']==d).dropna() #Discriminate the month and day
                
                pc = pricesElectricity(m,d)
            
                                                           
                
                first_h = hour if d==first_d else 0 
                
                for h in range(first_h,24): #Iterate over hours
                                                                                                      
                    
                    power=float(pv.where(pv['Hour']==h)['Output power (W)'].dropna())*Spv/N_BSS #Take power of the hour     
                    
                    if pw<cap: #If power has nor reach the minimum level 
                        pw, power_h, ind, price_g , last_p =powerCalculation(power,pw,hour,time,hour,h,ind,price_g,pc) 
                        
                    elif pw>cap: #If power is higher than the minimum level 
                        if last_p!=0:    
                            price_g=price_g - (pc[23 if h==0 else h-1]*(pw-cap)*1e-6)
                        dif=power_h-(pw-cap)
                        service_time=((h+(24*(d-Day)))-time-1)+(dif/power_h) #Calculate service time 
                        break
                    else:  #If power is equal to the minimum level 
                        service_time=(h+(24*(d-Day)))-time #Calculate service time 
                        break
                    
                                        
                if service_time !=0:
                    break
                                                               
                
            if service_time !=0:
                break
        #------------------------------------------------------------------------------------
                
        pw=0     
        hour2=hour
        ind=True
        last_p=0
        if Post :
            
            #Calculate the service time postponing battery charging------------------------------
            
            for m in range(first_m, 13):
            
                first_d = math.floor(Day + (time/24))
                
                for d in range(first_d,int(panel_v.where(panel_v['Month']==m).dropna().shape[0]/24)): #Iterate over days
                    
                    pv=panel_v.where(panel_v['Month']==m).where(panel_v['Day']==d).dropna() #Discriminate the month and day
                    
                    pc = pricesElectricity(m,d)
                    
                    first_h = hour if d==first_d else 0 
                        
                    for h in range(first_h,24): #Iterate over hours
    
                                                                                                                             
        
                        power=float(pv.where(pv['Hour']==h)['Output power (W)'].dropna())*Spv/N_BSS  #Take power of the hour     
            
                        if pw<cap: #If power has nor reach the minimum level 
                            #If price is higher than 60 euros, no renewable energy available and Tmax not exceeded
                            if pc[h]>60 and power==0 and postponed_time<Tmax: 
                                postponed_time=postponed_time+1 #Count postponed hours
                                if pw==0 and hour!=time:
                                    hour2=h+1
                            else:    
                                pw, power_h, ind, price_pos,last_p=powerCalculation(power,pw,hour2,time,hour,h,ind,price_pos,pc)
                        elif pw>cap: #If power is higher than the minimum level 
                            if last_p !=0:
                                price_pos=price_pos - (pc[23 if h==0 else h-1]*(pw-cap)*1e-6)
                            dif=power_h-(pw-cap)
                            time_in_BSS=((h+(24*(d-Day)))-time-1)+(dif/power_h) #Calculate total time = service time + postponed time 
                            break
                        else: #If power is equal to the minimum level 
                            time_in_BSS=(h+(24*(d-Day)))-time #Calculate total time = service time + postponed time 
                            break
                        
                    if time_in_BSS !=0:
                        break
                             
                    
                if time_in_BSS !=0:
                    break
                
        #------------------------------------------------------------------------------------    
    else: #If there is not a set of PV
        service_time=(cap*SERVICE)/C
        
        first_h = math.floor(time)
        out=False
        for m in range(first_m, 13):
            
            first_d = math.floor(Day + (time/24))
            
            for d in range(first_d,int(panel_v.where(panel_v['Month']==Month).dropna().shape[0]/24)): #Iterate over days
            
                pc = pricesElectricity(m,d)
                
                for h in range(first_h,math.floor(time+service_time+1)): #Iterate over hours
                
                    if (time-h>0):
                        price_g= price_g + (pc[h-24*(math.floor(h/24)) if h>=24 else h]*(1-(time-h)))*(0.020)
                    elif (time+service_time-h<1):
                        price_g= price_g + (pc[h-24*(math.floor(h/24)) if h>=24 else h]*(time+service_time-h))*(0.020)
                    else:
                        price_g= price_g + (pc[h-24*(math.floor(h/24)) if h>=24 else h]*0.020)
                    
                    if (h%24)==0 and h!=0:
                        first_h=h+1
                        break
                
                    if h == math.floor(time+service_time):
                        out=True
                
                if out:
                    break
                
            if out:
                    break
        
    return service_time, time_in_BSS, postponed_time , price_pos, price_g


# ******************************************************************************
# Prices of electricity method
# ****************************************************************************** 
def pricesElectricity(m,d):
    if m==1 or m==2 or (m==3 and d<20) or (m==12 and d>=21):
        pc = prices_winter #winter
    elif (m==3 and d>=20) or m==4 or m==5 or (m==6 and d<20):
        pc = prices_spring #spring
    elif (m==6 and d>=20) or m==7 or m==8 or (m==9 and d<22):
        pc = prices_summer #summer
    elif (m==9 and d>=22) or m==10 or m==11 or (m==12 and d<21):
        pc = prices_fall #fall
    
    return pc

# ******************************************************************************
# Power calculation method
# ****************************************************************************** 
def powerCalculation(power,pw,hour2,time,hour,h,ind,price_g,pc):
    last_p=0
    if power!=0: #Check if the PV has power 
        if power>C/2: 
            pw=pw+C/2 #Take the power from the PV avoiding the maximum charging rate is exceeded 
            power_h=C/2
        else:
            pw=pw+power #Take the power from the PV
            power_h=power
    else: 
        power_h=C/SERVICE #Take the power from the grid
        pw=pw+C/SERVICE
        last_p=(pc[h]*power_h*1e-6)
        price_g=price_g + (pc[h]*power_h*1e-6)
    
    if h==hour2 and math.floor(time)!=time and ind:
        pw=pw*(1-(time-math.floor(time)))
        ind=False
        price_g=price_g + (pc[h]*pw*1e-6) if power==0 else price_g+0
    
    return pw, power_h , ind, price_g ,last_p


# ******************************************************************************
# Server assignment method
# ****************************************************************************** 
def server_assignment(servers,time,service_time, time_in_BSS, postponed_time , price_pos, price_g):
    global bt_susp
    global price
    bt=0
    for i in range(len(servers)):
        bt=bt+1
        if servers[i].idle:           
            servers[i].idle=False #Indicate the server is idle or not
            if bt>num_b and postponed_time>0 and Post: #If there is a charge postponed and the current plug is disabled
                servers[i].dt=time + time_in_BSS
                servers[i].busy_time+=(time_in_BSS-postponed_time)
                servers[i].pt+=postponed_time
                total_t=time_in_BSS
                bt_susp+= 1
                price = price + price_pos
            else:
                servers[i].dt=time + service_time
                servers[i].busy_time+=service_time
                servers[i].pt+=0
                total_t=service_time
                price = price + price_g
            break  
    return total_t


# ******************************************************************************
# main
# ******************************************************************************

# Global Variables (for)

av_wdelay_Tmax = []     # Average delay list
av_ms_Tmax = []         # Average missed service list
va_Spv_Tmax = []        # value of size of panels list
total_price_Tmax = []   # Total Price list
for Tmax in range(1,6,1):

    va_f=[]               # value fraction of NBSS 
    av_wdelay=[]          # Average delay
    av_ms=[]              # Average missed service
    total_price=[]        # Total Price
    for f in [1/6, 2/6, 3/6, 4/6, 5/6]:

        # Global Variables

        battery_number=0      #Number of batteries
        bt_susp=0             #Number of batteries whose charge is postponed
        high_demand=False     #High demand indicator
        delayed_vans=0        #number of vans that experience waiting delay
        MM1=[]
        server_list=[]
        t_Bth=[]              # time battery level in departure
        v_Bth=[]              # value battery level in departure
        ms=[]
        tlp=[]
        num_b=N_BSS-round(N_BSS*f) #number of batteries charges in case of peak hour
        price=0

        random.seed(seed)  #same ramdom results
        
        data = Measure(0,0,0,0,0,0,0,0,0)
        
        time = 0
        
        FES = PriorityQueue()
        
        FES.put((0, "2arrival")) # schedule the first arrival at t=0
        
        for i in range(N_BSS):
            server_list.append(BSS(True, 0,0,0,0,False))#,0))
        
        while time < SIM_TIME: # simulate until the simulated time reaches a constant
                
            (time, event_type) = FES.get()
            
            if event_type == "2arrival":
                arrival(time, FES, MM1, server_list)
        
            elif event_type == "1departure": # number to sort in case of equal times
                departure(time, FES, MM1, server_list)
        
            tlp.append(time)
            ms.append(data.lp/data.arr)
        
            
        # print output data
        print("MEASUREMENTS ***********************************************************")       
        print("\nNo. of batteries in the queue:",battery_number,"\nNo. of arrivals =",data.arr,"- No. of departures =",data.dep)
        print("Number of missed services: ",data.lp)
        print("Number of batteries whose charge was postponed: ",bt_susp)
        print("Missed service probability: ",data.lp/data.arr)
        print("Arrival rate: ",data.arr/time," - Departure rate: ",data.dep/time) #lambda and mu
        print("\nAverage number of batteries in the BSS: ",data.ut/time) #Mean number of customers in the queue E[N]
        print("Average number of vans in queuing line: ",data.uq/time) #Mean number of customers in waiting line E[Nw]
        print("\nAverage delay: ",data.delay/data.dep)  #Average time in the queue E[T]
        print("Average waiting delay: ",data.wdelay/data.dep) #Average time in the waiting line E[Tw]
        for i in range(len(server_list)):
            print("\n*** Charger ",i+1,"***")
            print("  Busy time:",server_list[i].busy_time)
            print("  Postponed time:",server_list[i].pt)
            if server_list[i].dep_num !=0:
                print("  Average service time:",server_list[i].busy_time/server_list[i].dep_num)
            print("  No. of departures:",server_list[i].dep_num)
        print("\nSimulation time: ",SIM_TIME)
        print("\nActual queue size: ",len(MM1))
        
        if len(MM1)>0:
            print("Arrival time of the last element in the queue:",MM1[len(MM1)-1].arrival_time)
        av_wdelay.append(data.wdelay/data.dep)
        av_ms.append(data.lp/data.arr)
        va_f.append(f)
        
        total_price.append(price)
    av_wdelay_Tmax.append(av_wdelay)
    av_ms_Tmax.append(av_ms)
    va_Spv_Tmax.append(va_f)
    total_price_Tmax.append(total_price)


ls=[ '-' , '--' , '-.' , ':' , 'o']
plt.figure()
for i in range(0,5,1):
    plt.plot(va_f,av_wdelay_Tmax[i],ls[i],label=f'Tmax = {i+1}', linewidth=2)
plt.ylabel('Average waiting delay [h]')
plt.xlabel('f')
plt.title('Average waiting delay vs  f')
plt.grid()
plt.legend()
plt.show()

plt.figure()
for i in range(0,5,1):
    plt.plot(va_f,av_ms_Tmax[i],ls[i],label=f'Tmax = {i+1}', linewidth=2)
plt.ylabel('Missed service probability')
plt.xlabel(' f')
plt.title('Missed service probability  vs f')
plt.grid()
plt.legend()
plt.show()


plt.figure()
for i in range(0,5,1):
    plt.plot(va_f,total_price_Tmax[i],ls[i],label=f'Tmax = {i+1}', linewidth=2)
plt.ylabel('Total cost [€]')
plt.xlabel('f')
plt.title('Total cost vs  f')
plt.grid()
plt.legend()
plt.show()
    

    