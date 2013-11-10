import despotic
import numpy as np
import warnings
import os
from collections import defaultdict
from astropy import units as u
from .utils import united,uvalue

try:
    from astropy import units as u
    from astropy import constants
except ImportError:
    u = False

class Despotic(object):
    """
    A class meant to be similar to RADEX in terms of how it is called but to
    use Despotic instead of RADEX as the backend
    """

    # escapeprobabilty geometry names
    _epgdict = {'lvg':'LVG','sphere':'sphere','slab':'slab'}

    def __call__(self, **kwargs):
        # reset the parameters appropriately
        self.__init__(**kwargs)
        return self.lineLum(self.species)

    def __init__(self,
                 collider_densities={'ph2':990,'oh2':10},
                 temperature=30,
                 species='co',
                 datapath=None,
                 hcolumn=1e21,
                 abundance=1e-5,
                 #column=1e13,
                 tbackground=2.7315,
                 deltav=1.0,
                 escapeProbGeom='lvg',
                 outfile='radex.out',
                 logfile='radex.log',
                 debug=False,
                 ):
        """
        Interface to DESPOTIC

        Parameters
        ----------
        collider_densities: dict
            Dictionary giving the volume densities of the collider(s) in units of
            cm^-3.  Valid entries are h2,oh2,ph2,e,He,H,H+.  The keys are
            case-insensitive.
        temperature: float
            Local gas temperature in K
        species: str
            A string specifying a valid chemical species.  This is used to look
            up the specified molecule
        hcolumn: float
            The total column density of hydrogen.
        abundance: float
            The molecule's abundance relative to H.
        tbackground: float
            Background radiation temperature (e.g., CMB)
        deltav: float
            The FWHM line width (really, the single-zone velocity width to
            scale the column density by: this is most sensibly interpreted as a
            velocity gradient (dv/dR))
        sigmaNT: float
            Nonthermal velocity dispersion
            (this is strictly ignored - deltav IS sigmant)
        datapath: str
            Path to the molecular data files
        """
        
        self.cloud = despotic.cloud()
        self.cloud.nH = float(np.sum([collider_densities[k]*2 if 'h2' in k.lower()
                                      else collider_densities[k]
                                      for k in collider_densities]))

        for k in collider_densities.keys():
            collider_densities[k.lower()] = collider_densities[k]

        if 'ph2' in collider_densities:
            self.cloud.comp.xpH2 = collider_densities['ph2'] / self.cloud.nH
        if 'oh2' in collider_densities:
            self.cloud.comp.xoH2 = collider_densities['oh2'] / self.cloud.nH

        self.cloud.Td = uvalue(temperature,u.K)
        self.cloud.Tg = uvalue(temperature,u.K)
        self.cloud.dust.sigma10 = 0.0

        self.cloud.colDen = uvalue(hcolumn,u.cm**-2)


        if uvalue(tbackground,u.K) > 2.7315:
            self.cloud.rad.TradDust = uvalue(tbackground,u.K)

        self.species = species
        if datapath is None:
            emitterFile = species+'.dat'
        else:
            emitterFile = os.path.expanduser(os.path.join(datapath, species+'.dat'))
        self.cloud.addEmitter(species, abundance, emitterFile=emitterFile)


        self.cloud.comp.computeDerived(self.cloud.nH)

        self.deltav = deltav

        self.escapeProbGeom = escapeProbGeom

    @property
    def deltav(self):
        return united(self._dv,u.km/u.s)

    @deltav.setter
    def deltav(self, deltav):
        FWHM = united(deltav,u.km/u.s)
        self.cs = np.sqrt(constants.k_B*united(self.cloud.Tg,u.K)/(self.cloud.comp.mu*constants.m_p)).to(u.km/u.s)
        self.sigmaTot = FWHM/np.sqrt(8.0*np.log(2))
        self.cloud.sigmaNT = uvalue(np.sqrt(self.sigmaTot**2 -
                                            self.cs**2/self.cloud.emitters[self.species].data.molWgt),
                                    u.km/u.s)
        self.cloud.dVdr = uvalue(united(deltav,u.km/u.s/u.pc),u.s**-1)


    def lineLum(self, **kwargs):
        if 'escapeProbGeom' not in kwargs:
            kwargs['escapeProbGeom'] = self.escapeProbGeom
        return self.cloud.lineLum(self.species, **kwargs)

    @property
    def escapeProbGeom(self):
        return self._epg

    @escapeProbGeom.setter
    def escapeProbGeom(self, escapeProbGeom):
        mdict = self._epgdict
        if escapeProbGeom.lower() not in mdict:
            raise ValueError("Invalid escapeProbGeom, must be one of "+",".join(mdict.values()))
        self._epg = mdict[escapeProbGeom]

    @property
    def density(self):
        d = {'H2':self.cloud.comp.xH2*self.nH,
             'oH2':self.cloud.comp.xoH2*self.nH,
             'pH2':self.cloud.comp.xpH2*self.nH,
             'e':self.cloud.comp.xe*self.nH,
             'H':self.cloud.comp.xHI*self.nH,
             'He':self.cloud.comp.xHe*self.nH,
             'H+':self.cloud.comp.xHplus*self.nH}
        if u:
            for k in d:
                d[k] = d[k] * u.cm**-3
        return d

    @property
    def nH(self):
        return self.cloud.nH

    @nH.setter
    def nH(self, nh):
        self.cloud.nH = nh

    @property
    def nH2(self):
        return self.cloud.nH/2.

    @nH2.setter
    def nH2(self, nh2):
        self.nh = nh2*2.


    @density.setter
    def density(self, collider_density):
        collider_densities = defaultdict(lambda: 0)
        for k in collider_density:
            collider_densities[k.upper()] = collider_density[k]

        if 'OH2' in collider_densities:
            if not 'PH2' in collider_densities:
                raise ValueError("If o-H2 density is specified, p-H2 must also be.")
            collider_densities['H2'] = (collider_densities['OH2'] + collider_densities['PH2'])
        elif 'H2' in collider_densities:
            warnings.warn("Using a default ortho-to-para ratio (which "
                          "will only affect species for which independent "
                          "ortho & para collision rates are given)")

            T = self.temperature.value if hasattr(self.temperature,'value') else self.temperature
            if T > 0:
                opr = min(3.0,9.0*np.exp(-170.6/T))
            else:
                opr = 3.0
            fortho = opr/(1+opr)
            collider_densities['OH2'] = collider_densities['H2']*fortho
            collider_densities['PH2'] = collider_densities['H2']*(1-fortho)

        total_density = np.sum([collider_densities[x] * (2 if '2' in x else 1)
                                for x in (['OH2','PH2','H','E','HE','H+'])])
        self.nH = total_density

        self.cloud.comp.xH2 = collider_densities['H2']/self.nH
        self.cloud.comp.xoH2 = (collider_densities['OH2'])/self.nH
        self.cloud.comp.xpH2 = (collider_densities['PH2'])/self.nH

        self.cloud.comp.xe = collider_densities['E']/self.nH
        self.cloud.comp.xHI = collider_densities['H']/self.nH
        self.cloud.comp.xHe = collider_densities['HE']/self.nH
        self.cloud.comp.xHplus = collider_densities['H+']/self.nH

        self.cloud.comp.computeDerived()

    @property
    def temperature(self):
        return self.cloud.Tg
