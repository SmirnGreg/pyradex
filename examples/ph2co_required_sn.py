"""
Simple proposal-writing experiment: For a given signal-to-noise in a line, what
signal-to-noise do you get in a derived parameter (e.g., temperature)?
"""
import pyradex
import pylab as pl
import numpy as np
import matplotlib
import astropy.units as u

ntemp = 50
temperatures = np.linspace(10,200,ntemp)
abundance = 10**-8.5

density = 1e4

R = pyradex.Radex(species='ph2co-h2', abundance=abundance, collider_densities={'H2':density}, column=None, temperature=temperatures[0])

pl.figure(1)
pl.clf()

for temperature in [10,50,100]:
    R.temperature = temperature
    R.run_radex()
    S = pyradex.synthspec.SyntheticSpectrum(218.2*u.GHz,218.8*u.GHz,R.get_table(),linewidth=10*u.km/u.s)
    S.plot(label='%i K' % temperature)

pl.legend(loc='best')

# create a small grid...
ratio = []
f1 = []
f2 = []

for temperature in temperatures:
    R.temperature = temperature
    R.run_radex()

    F1 = R.line_flux[2]
    F2 = R.line_flux[12]

    #tb = R.line_brightness(np.pi*(1*u.arcsec)**2)
    #t1 = tb[2]
    #t2 = tb[12]

    ratio.append(F2/F1)
    f2.append(F2)
    f1.append(F1)

ratio = np.array(ratio)

pl.figure(2)
pl.clf()

pl.plot(ratio,temperatures)
pl.ylabel("Temperature")
pl.xlabel("$S(3_{2,1}-2_{2,0})/S(3_{0,3}-2_{0,2})$")

m = 1/((ratio[15]-ratio[5])/(temperatures[15]-temperatures[5]))
b = temperatures[5]-ratio[5]*m
line=(m,b)
pl.plot(ratio,ratio*line[0]+line[1])
pl.axis([0,0.5,10,200,])
