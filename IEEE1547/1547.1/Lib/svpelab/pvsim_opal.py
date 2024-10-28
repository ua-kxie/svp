"""
Copyright (c) 2017, Sandia National Labs and SunSpec Alliance
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

Neither the names of the Sandia National Labs and SunSpec Alliance nor the names of its
contributors may be used to endorse or promote products derived from
this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Questions can be directed to support@sunspec.org
"""

import os
from . import pvsim

opal_info = {
    'name': os.path.splitext(os.path.basename(__file__))[0],
    'mode': 'Opal'
}

def pvsim_info():
    return opal_info

def params(info, group_name):
    gname = lambda name: group_name + '.' + name
    pname = lambda name: group_name + '.' + GROUP_NAME + '.' + name
    mode = opal_info['mode']
    info.param_add_value(gname('mode'), mode)
    info.param_group(gname(GROUP_NAME), label='%s Parameters' % mode,
                     active=gname('mode'),  active_value=mode, glob=True)

    # TODO : add more sophistacated PV sim parameter
    info.param(pname('irr'), label='Irradiance (W/m^2)', default=1200.0)
    info.param(pname('temp'), label='Temperature (C)', default=25.0)



GROUP_NAME = 'Opal'


class PVSim(pvsim.PVSim):

    def __init__(self, ts, group_name, support_interfaces=None):
        pvsim.PVSim.__init__(self, ts, group_name,support_interfaces=support_interfaces)
        self.ts = ts
        if self.hil is None:
            ts.log_warning('No HIL support interface was provided to pvsim_opal.py')


    def _param_value(self, name):
        return self.ts.param_value(self.group_name + '.' + GROUP_NAME + '.' + name)



    def info(self):
        return "PVsim using pvsim_opal.py"

    def irradiance_set(self, irradiance=1100,temperature = 25.0):
        self.hil.set_matlab_variable_value("IRRADIANCE",irradiance)
        params = {}
        params["IRRADIANCE"] = self.hil.get_matlab_variable_value("IRRADIANCE")
        return params

    def measurements_get(self):
        """
        Measure the voltage, current, and power of all channels - calculate the average voltage, total current, and
        total power

        :return: dictionary with dc power data with keys: 'DC_V', 'DC_I', and 'DC_P'
        """
        pass

    def power_set(self, power, irradiance=1100):
        self.irradiance_set((power/self.ts.params['eut.s_rated'])*irradiance)
        pass

    def profile_load(self, profile_name):
        pass

    def power_on(self):
        pass

    def power_off(self):
        pass

    def profile_start(self):
        pass

    def profile_stop(self):
        pass

    def measure_power(self):
        """
        Get the current, voltage, and power from the TerraSAS
        returns: dictionary with power data with keys: 'DC_V', 'DC_I', and 'DC_P'
        """
        pass

if __name__ == "__main__":
    pass
