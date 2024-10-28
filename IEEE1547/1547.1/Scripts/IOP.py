'''
Copyright (c) 2016, Sandia National Labs and SunSpec Alliance
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

Written by Sandia National Laboratories and SunSpec Alliance
Questions can be directed to Jay Johnson (jjohns2@sandia.gov)
'''


import sys
import os
import traceback
from svpelab import der1547
from svpelab import das
from svpelab import pvsim
from svpelab import gridsim
from svpelab import hil
from svpelab import p1547
import script
import math

# todo
PARAM_MAP = {'np_p_max': 'Active power rating at unity power factor (nameplate active power rating) (kW)',
             'np_p_max_over_pf': 'Active power rating at specified over-excited power factor (kW)',
             'np_over_pf': 'Specified over-excited power factor',
             'np_under_pf': 'Specified under-excited power factor',
             'np_va_max': 'Apparent power maximum rating (kVA)',
             'np_normal_op_cat': 'Normal operating performance category', 
             'np_abnormal_op_cat': 'Abnormal operating performance category', 
             'np_q_max_inj': 'Reactive power injected maximum rating (kvar)',
             'np_q_max_abs': 'Reactive power absorbed maximum rating (kvar)',
             'np_apparent_power_charge_max': 'Apparent power charge maximum rating (kVA)',
             'np_ac_v_nom': 'AC voltage nominal rating',
             'np_ac_v_max_er_max': 'AC voltage maximum rating',
             'np_ac_v_min_er_min': 'AC voltage minimum rating',
             'np_supported_modes': 'Supported control mode functions',
             'UV': 'Supports Low Voltage Ride-Through Mode',
             'OV': 'Supports High Voltage Ride-Through Mode',
             'UF': 'Supports Low Freq Ride-Through Mode',
             'OF': 'Supports High Freq Ride-Through Mode',
             'P_LIM': 'Supports Active Power Limit Mode',
             'PV': 'Supports Volt-Watt Mode',
             'PF': 'Supports Frequency-Watt Curve Mode',
             'CONST_Q': 'Supports Constant VArs Mode',
             'CONST_PF': 'Supports Fixed Power Factor Mode',
             'QV': 'Supports Volt-VAr Control Mode',
             'QP': 'Supports Watt-VAr Mode',
             'np_reactive_susceptance': 'Reactive susceptance that remains connected to the Area EPS in the cease to ' \
                                        'energize and trip state',
             'np_manufacturer': 'Manufacturer',
             'np_model': 'Model',
             'np_serial_num': 'Serial Number',
             'np_fw_ver': 'Version',
             'mn_w': 'Active Power (kW)',
             'mn_var': 'Reactive Power (kVAr)',
             'mn_v': 'Voltage (list) (V)',
             'mn_hz': 'Frequency (Hz)',
             'mn_st': 'Operational State (bool)',
             'mn_conn': 'Connection State (bool)',
             'mn_alrm': 'Alarm Status (dict)',
             'mn_soc_pct': 'Operational State of Charge (%)',
             }


def print_params(param_dict, indent=1):
    """
    Pretty print of parameters from dictionary of parameters returned from der1547

    :param param_dict: dict from a getter function, e.g., der1547.get_nameplate()
    :param indent: number of spaces in the print
    :return: None
    """
    # ts.log('DER Parameter Dictionary: %s' % param_dict)
    if param_dict is None:
        return

    for key, value in param_dict.items():
        skip = False
        if isinstance(value, list):
            ts.log('\t' * indent + str(key) + ': <list>')
            if len(value) == 0:
                ts.log('\t' * (indent+1) + '[]')
            count = 0
            for v in value:
                print_params({'<list item %s>' % count: v}, indent+1)
                count += 1
            skip = True
        if not isinstance(value, dict):
            if not skip:  # if it was already printed as a list
                if isinstance(PARAM_MAP, dict):
                    if key in PARAM_MAP:
                        ts.log('\t' * indent + PARAM_MAP[key] + ' [' + key + '] : ' + str(value))
                    else:
                        ts.log('\t' * indent + str(key) + ': ' + str(value))
                else:
                    ts.log('\t' * indent + str(key) + ': ' + str(value))
        else:   # for sub dicts recall this function
            if isinstance(PARAM_MAP, dict):
                if key in PARAM_MAP:
                    ts.log('\t' * indent + PARAM_MAP[key] + ' [' + key + '] : ')
                else:
                    ts.log('\t' * indent + str(key) + ': ')
            else:
                ts.log('\t' * indent + str(key) + ': ')
            print_params(value, indent+1)


def test_run():

    result = script.RESULT_FAIL
    daq = None
    grid = None
    pv = None
    eut = None
    chil = None
    result_summary = None
    dataset_filename = None
    v_nom = None

    try:

        configuration_test = ts.param_value('iop_params.configuration_test') == 'Yes'
        monitoring_test = ts.param_value('iop_params.monitoring_test') == 'Yes'

        v_nom = float(ts.param_value('eut.v_nom'))
        p_rated = float(ts.param_value('eut.p_rated'))
        w_max = p_rated
        s_rated = float(ts.param_value('eut.s_rated'))
        var_rated = float(ts.param_value('eut.var_rated'))
        var_max = var_rated
        wait_time = float(ts.param_value('eut.wait_time'))

        # initialize DER configuration
        eut = der1547.der1547_init(ts)
        eut.config()

        if ts.param_value('iop_params.print_comm_map') == 'Yes':
            if callable(getattr(eut, "print_modbus_map", None)):
                eut.print_modbus_map(w_labels=True)

        das_points = {'sc': ('event')}
        daq = das.das_init(ts, sc_points=das_points['sc'])

        # initialize HIL environment, if necessary
        chil = hil.hil_init(ts)
        if chil is not None:
            chil.config()

        # pv simulator is initialized with test parameters and enabled
        pv = pvsim.pvsim_init(ts)
        if pv is not None:
            pv.power_set(p_rated)
            pv.power_on()  # Turn on DC so the EUT can be initialized

        # grid simulator is initialized with test parameters and enabled
        grid = gridsim.gridsim_init(ts)  # Turn on AC so the EUT can be initialized
        if grid is not None:
            grid.voltage(v_nom)

        iop = p1547.ActiveFunction(ts=ts, functions=['IOP'], script_name='Interoperability',
                                   criteria_mode=[False, False, False])
        ts.log_debug("1547.1 Library configured for %s" % iop.get_script_name())
        iop.set_params()

        '''
        6.4 Nameplate data test
        a) Read from the DER each nameplate data item listed in Table 28 in IEEE Std 1547-2018.
        b) Compare each value received to the expected values from the manufacturer-provided expected values.
        '''

        ts.log('---')
        nameplate = eut.get_nameplate()
        if nameplate is not None:
            ts.log('DER Nameplate Information:')
            print_params(nameplate)
            ts.log('---')
        else:
            ts.log_warning('DER Nameplate Information not supported')

        if configuration_test:  # Not supported by DNP3 App Note
            '''
            6.5 Configuration information test

            a) Read from the DER each parameter identified in Table 42.
            b) For each, verify that the value reported matches the behavior of the DER measured though independent test
               equipment separate from the DER interface.
            c) Adjust values as identified in Table 42.
            d) Repeat steps a) and b) for the new values.
            e) Adjust parameters back to the initial values and verify that the value reported matches the initial
               values.

            Table 42 - Basic settings test levels
            ____________________________________________________________________________________________________________
            Parameter                           Adjustment required            Additional test instructions
            ____________________________________________________________________________________________________________
            Active Power Maximum                Set to 80% of Initial Value
            Apparent Power Maximum              Set to 80% of Initial Value
            Reactive Power Injected Maximum     Set to 80% of Initial Value
            Reactive Power Absorbed Maximum     Set to 80% of Initial Value
            Active Power Charge Maximum         Set to 80% of Initial Value     This test applies only to DER that
                                                                                include energy storage.
            Apparent Power Charge Maximum       Set to 80% of Initial Value     This test applies only to DER that
                                                                                include energy storage.
            AC Current Maximum                  Set to 80% of Initial Value
            Control Mode Functions              Not applicable
            '''
            ts.log('---')
            settings = eut.get_settings()
            if settings is not None:
                ts.log('DER Settings Information:')
                print_params(settings)
                ts.log('---')
                basic_settings = []
                if settings.get('np_p_max') is not None:
                    basic_settings.append(('np_p_max', 0.8 * settings['np_p_max'], 'P', settings['np_p_max']))
                else:
                    ts.log_warning('DER Settings does not include np_p_max')
                if settings.get('np_va_max') is not None:
                    basic_settings.append(('np_va_max', 0.8 * settings['np_va_max'], 'VA', settings['np_va_max']))
                else:
                    ts.log_warning('DER Settings does not include np_va_max')
                if settings.get('np_q_max_inj') is not None:
                    basic_settings.append(('np_q_max_inj', 0.8 * settings['np_q_max_inj'], 'Q',
                                           settings['np_q_max_inj']))
                else:
                    ts.log_warning('DER Settings does not include np_q_max_inj')
                if settings.get('np_q_max_abs') is not None:
                    basic_settings.append(('np_q_max_abs', 0.8 * settings['np_q_max_abs'], 'Q',
                                           settings['np_q_max_abs']))
                else:
                    ts.log_warning('DER Settings does not include np_q_max_abs')
                if settings.get('np_ac_v_max_er_max') is not None:
                    basic_settings.append(('np_ac_v_max_er_max', 0.8 * settings['np_ac_v_max_er_max'], 'V',
                                           settings['np_ac_v_max_er_max']))  # assume this is a typo for AC Current
                else:
                    ts.log_warning('DER Settings does not include np_ac_v_max_er_max')
                if settings.get('np_p_max_charge') is not None:
                    basic_settings.append(('np_p_max_charge', 0.8 * settings['np_p_max_charge'], 'P',
                                           settings['np_p_max_charge']))
                else:
                    ts.log_warning('DER Settings does not include np_p_max_charge')

                # Run the power system experiments
                for s in range(len(basic_settings)):
                    param = basic_settings[s][0]
                    val = basic_settings[s][1]
                    meas = basic_settings[s][2]
                    final_val = basic_settings[s][3]
                    der_read = eut.get_settings().get(param)
                    if der_read is not None:
                        ts.log('  Currently %s = %0.3f.' % (param, der_read))
                    else:
                        ts.log('  Currently %s = %s.' % (param, der_read))
                    ts.log('  Setting %s to %0.3f.' % (param, val))
                    eut.set_settings(params={param: val})
                    ts.sleep(wait_time)
                    der_read = eut.get_settings().get(param)
                    if der_read is not None:
                        ts.log('  --> Readback value is %0.3f' % eut.get_settings().get(param))
                    else:
                        ts.log('  --> Readback value is %s' % eut.get_settings().get(param))

                    if daq is not None:
                        verify_val = iop.datalogging.get_measurement_total(data=daq.data_capture_read(),
                                                                           type_meas=meas, log=True)
                        ts.log('  Verification value is: %f.' % verify_val)
                        ts.log('  Returning %s to %f.' % (param, final_val))
                    eut.set_settings(params={param: val})
                    ts.sleep(wait_time)

                # Supported control mode functions
                if settings.get('np_supported_modes') is not None:
                    ctrl_dict = {}
                    ctrl_dict['max_w'] = True
                    ctrl_dict['fixed_w'] = False
                    ctrl_dict['fixed_var'] = True
                    ctrl_dict['fixed_pf'] = False
                    ctrl_dict['volt_var'] = True
                    ctrl_dict['freq_watt'] = False
                    ctrl_dict['dyn_react_curr'] = True
                    ctrl_dict['lv_trip'] = False
                    ctrl_dict['hv_trip'] = True
                    ctrl_dict['watt_var'] = False
                    ctrl_dict['volt_watt'] = True
                    ctrl_dict['scheduled'] = False
                    ctrl_dict['lf_trip'] = True
                    ctrl_dict['hf_trip'] = False
                    try:
                        eut.set_configuration(params={'np_supported_modes': ctrl_dict})
                    except Exception as e:
                        ts.log_warning('TEST FAILURE: EUT Failed to change the supported modes. %s' % e)
                    ts.log('Set control mode functions:')
                    print_params(ctrl_dict)
                    ts.log('--> Readback of control mode functions:')
                    print_params(eut.get_settings().get('np_supported_modes'))
                    ts.log('-' * 10)

                    if daq is not None:
                        # todo - add electrical tests of the control functions
                        # configure operating modes
                        # determine if the mode is operational with an electrical test
                        pass

                    ctrl_dict = {}
                    ctrl_dict['max_w'] = False
                    ctrl_dict['fixed_w'] = True
                    ctrl_dict['fixed_var'] = False
                    ctrl_dict['fixed_pf'] = True
                    ctrl_dict['volt_var'] = False
                    ctrl_dict['freq_watt'] = True
                    ctrl_dict['dyn_react_curr'] = False
                    ctrl_dict['lv_trip'] = True
                    ctrl_dict['hv_trip'] = False
                    ctrl_dict['watt_var'] = True
                    ctrl_dict['volt_watt'] = False
                    ctrl_dict['scheduled'] = True
                    ctrl_dict['lf_trip'] = False
                    ctrl_dict['hf_trip'] = True
                    try:
                        eut.set_configuration(params={'np_supported_modes': ctrl_dict})
                    except Exception as e:
                        ts.log_warning('TEST FAILURE: EUT Failed to change the supported modes. %s' % e)

                    ts.log('Set control mode functions:')
                    print_params(ctrl_dict)
                    ts.log('--> Readback of control mode functions:')
                    print_params(eut.get_settings().get('np_supported_modes'))
                    ts.log('-' * 10)

                    if daq is not None:
                        # todo - add electrical tests of the control functions
                        # configure operating modes
                        # determine if the mode is operational with an electrical test
                        pass

                    ctrl_dict = {}
                    ctrl_dict['max_w'] = True
                    ctrl_dict['fixed_w'] = True
                    ctrl_dict['fixed_var'] = True
                    ctrl_dict['fixed_pf'] = True
                    ctrl_dict['volt_var'] = True
                    ctrl_dict['freq_watt'] = True
                    ctrl_dict['dyn_react_curr'] = True
                    ctrl_dict['lv_trip'] = True
                    ctrl_dict['hv_trip'] = True
                    ctrl_dict['watt_var'] = True
                    ctrl_dict['volt_watt'] = True
                    ctrl_dict['scheduled'] = True
                    ctrl_dict['lf_trip'] = True
                    ctrl_dict['hf_trip'] = True
                    try:
                        eut.set_configuration(params={'np_supported_modes': ctrl_dict})
                    except Exception as e:
                        ts.log_warning('TEST FAILURE: EUT Failed to change the supported modes. %s' % e)
                    ts.log('Set control mode functions:')
                    print_params(ctrl_dict)
                    ts.log('--> Readback of control mode functions:')
                    print_params(eut.get_settings().get('np_supported_modes'))

                else:
                    ts.log_warning('DER Settings does not include np_control_modes')
            else:
                ts.log_warning('DER settings not supported')
        else:
            ts.log('Skipping DER settings test')

        if monitoring_test:
            '''
            6.6 Monitoring information test

            a) Set the operating conditions of the DER to the values specified in the "Operating Point A" column in
               Table 43.
            b) Wait not less than 30 s, then read from the DER each monitoring information, and verify that the
               reported values match the operating conditions as identified.
            c) Change the operating conditions of the DER as specified in the "Operating Point B" column 16 in Table 43.
            d) Repeat step b).
            
            Table 43 — Monitoring information test levels
            ____________________________________________________________________________________________________________
            Monitoring          Operating               Operating               Criteria
            information         Point A                 Point B
            parameter                                
            ____________________________________________________________________________________________________________
            Active Power        20% to 30% of           90% to 100% of          Reported values match test operating
                                DER “active power       DER “active power       conditions within the accuracy 
                                rating at unity power   rating at unity power   requirements specified in Table 3 in 
                                factor.”                factor.”                IEEE Std 1547-2018.

            Reactive Power      20% to 30% of           90% to 100% of          Reported values match test operating
            (Injected)          DER “reactive power     DER “reactive power     conditions within the accuracy 
                                injected maximum        injected maximum        requirements specified in Table 3 in
                                rating.”                rating.”                IEEE Std 1547-2018.

            Reactive Power      20% to 30% of           90% to 100% of          Reported values match test operating
            (Absorbed)          DER “reactive power     DER “reactive power     conditions within the accuracy 
                                injected maximum        injected maximum        requirements specified in Table 3 in
                                rating.”                rating.”                IEEE Std 1547-2018.

            Voltage(s)          At or below             At or above 1.08 × (ac  Reported values match test operating
                                0.90 × (ac voltage      voltage nominal         conditions within the accuracy 
                                nominal rating).        rating).                requirements specified in Table 3 in
                                                                                IEEE Std 1547-2018.
                                                                                
            Frequency           At or below 57.2 Hz.    At or above 61.6 Hz.    Reported values match test operating
                                                                                conditions within the accuracy 
                                                                                requirements specified in Table 3 in 
                                                                                IEEE Std 1547-2018.
            
            Operational State   On: Conduct this test   Off: If supported by    Reported Operational State matches the
                                while the DER is        the DER, conduct this   device present condition for on and off 
                                generating.             test while capable of   states.
                                                        communicating but not
                                                        capable of generating.
            
            Connection Status   Connected: Conduct      Disconnected:           Reported Connection Status matches the
                                this test while the     Conduct this test while device present connection condition.
                                DER is generating.      permit service is
                                                        disabled.

            Alarm Status        Has alarms set.         No alarms set.          Reported Alarm Status matches the device
                                                                                present alarm condition for alarm and no
                                                                                alarm conditions. For test purposes 
                                                                                only, the DER manufacturer shall specify 
                                                                                at least one way an alarm condition that
                                                                                is supported in the protocol being 
                                                                                tested can be set and cleared.
            '''
            timeout_duration = 5
            if hasattr(eut, 'metering_post_time'):
                ts.log('Timeout duration extended %0.2f sec to account for the client metering post time' %
                       eut.metering_post_time)
                timeout_duration += eut.metering_post_time

            m = eut.get_monitoring()
            if m is not None:
                ts.log('-' * 30)
                ts.log('Monitoring Values:')
                print_params(m)
                '''
                ________________________________________________________________________________________________________
                Monitoring          Operating               Operating               Criteria
                information         Point A                 Point B
                parameter                                
                ________________________________________________________________________________________________________
                Active Power        20% to 30% of           90% to 100% of          Reported values match test operating
                                    DER “active power       DER “active power       conditions within the accuracy 
                                    rating at unity power   rating at unity power   requirements specified in Table 3 in 
                                    factor.”                factor.”                IEEE Std 1547-2018.
                '''

                if ts.param_value('iop_params.mon.monitor_p') == 'Yes':
                    ts.log('Starting Monitoring Assessment. Active Power reported from the EUT is: %s W' %
                           (m.get('mn_w') * 1.e3))
                    accuracy = 5.  # percent
                    ts.log('')
                    ts.log('**** Active Power Monitoring Test ****')
                    for setpoint in [0.25, 0.95]:  # test_pts (pu)
                        setpoint_pct = setpoint * 100.
                        ts.log_debug('    ****Configuring Experiment. Executing: p_lim = %s' % setpoint)
                        try:
                            eut.set_p_lim(params={"p_lim_mode_enable": True, "p_lim_w": setpoint})
                        except Exception as e:
                            ts.log_warning('TEST FAILURE: EUT Failed to change p_lim_mode. %s' % e)
                        ts.sleep(2)
                        inaccurate_measurement = True
                        timeout = timeout_duration
                        test_pass_fail = 'FAIL'
                        while inaccurate_measurement and timeout > 0:
                            timeout -= 1
                            power_measured = eut.get_monitoring().get("mn_w")*1000.
                            value = 100.*(power_measured/p_rated)  # percentage
                            # ts.log_debug('    ****Returned Value: %s %%' % value)
                            ts.log('    EUT Active Power is currently %0.1f%% Prated, waiting another %0.1f sec' %
                                   (value, timeout))
                            if setpoint_pct - accuracy <= value <= setpoint_pct + accuracy:  # +/- accuracy in pct
                                ts.log('    EUT has recorded power +/- %s%% as required by IEEE 1547-2018.' % accuracy)
                                ts.log('    Returning EUT to rated power.')
                                test_pass_fail = 'PASS'
                                inaccurate_measurement = False
                            else:
                                ts.log('    EUT outside the IEEE 1547-2018 requirements. Bounds = [%0.1f, %0.1f], '
                                       'Value = %0.1f' % (setpoint_pct - accuracy, setpoint_pct + accuracy, value))
                                ts.sleep(1)
                        ts.log('RESULT = %s' % test_pass_fail)

                    ts.log_debug('    ****Resetting Function p_lim')
                    try:
                        eut.set_p_lim(params={"p_lim_mode_enable": False, "p_lim_w": 1.})
                    except Exception as e:
                        ts.log_warning('TEST FAILURE: EUT Failed to change p_lim_mode. %s' % e)


                '''
                ________________________________________________________________________________________________________
                Monitoring          Operating               Operating               Criteria
                information         Point A                 Point B
                parameter                                
                ________________________________________________________________________________________________________
                Reactive Power      20% to 30% of           90% to 100% of          Reported values match test operating
                (Injected)          DER “reactive power     DER “reactive power     conditions within the accuracy 
                                    injected maximum        injected maximum        requirements specified in Table 3 in
                                    rating.”                rating.”                IEEE Std 1547-2018.
    
                Reactive Power      20% to 30% of           90% to 100% of          Reported values match test operating
                (Absorbed)          DER “reactive power     DER “reactive power     conditions within the accuracy 
                                    injected maximum        injected maximum        requirements specified in Table 3 in
                                    rating.”                rating.”                IEEE Std 1547-2018.
                '''

                if ts.param_value('iop_params.mon.monitor_q') == 'Yes':
                    accuracy = 5.
                    ts.log('Starting Monitoring Assessment. Reactive Power reported from the EUT is: %s' %
                           eut.get_monitoring().get('mn_var'))
                    ts.log('')
                    ts.log('**** Reactive Power Monitoring Test ****')
                    for excitation in ['inj', 'abs']:
                        for setpoint in [0.25, 0.95]:
                            crp = False
                            try:
                                if not eut.get_nameplate().get('np_supported_modes').get('fixed_var'):
                                    # jump down to except to set vars with PF
                                    raise Exception('This DER does not include the fixed var function. Using CPF.')
                                ts.log_debug('     ****Configuring Experiment. Executing: CRP = %s' % setpoint)
                                eut.set_const_q(params={"const_q_mode_enable": True,
                                                        "const_q_mode_excitation": excitation,
                                                        "const_q": abs(100.*setpoint)})
                                ts.log_debug('     ****New CRP = %s' % eut.get_const_q())
                                crp = True
                            except Exception as e:  # fallback plan if CRP doesn't work
                                ts.log_warning('Unable to use CRP: %s' % e)
                                pf = math.sqrt(1. - (setpoint ** 2))
                                if excitation == 'abs':
                                    setpoint *= -1  # invert sign for abs for the DNP3 devices
                                ts.log_debug('     ****Configuring Experiment. Executing: Const PF = %s' % setpoint)
                                eut.set_const_pf(params={"const_pf_mode_enable": True, "const_pf_abs": pf,
                                                         "const_pf_excitation": excitation})
                            ts.sleep(2)
                            inaccurate_measurement = True
                            timeout = timeout_duration
                            test_pass_fail = 'FAIL'
                            while inaccurate_measurement and timeout > 0:
                                timeout -= 1
                                value = 1.0e5*(eut.get_monitoring().get("mn_var")/var_max) # percentage
                                # ts.log_debug('    ****Returned Value: %s' % value)
                                ts.log('    EUT Reactive Power is currently %0.1f%%, waiting another %0.1f sec' %
                                       (value, timeout))
                                if excitation == 'inj':
                                    sign = 1
                                else:
                                    sign = -1
                                setpoint_pct = setpoint * 100. * sign
                                if setpoint_pct - accuracy <= value <= setpoint_pct + accuracy:  # +/- accuracy in pct
                                    ts.log('    EUT has recorded value of +/- %s%% as required by IEEE 1547-2018.' %
                                           accuracy)
                                    test_pass_fail = 'PASS'
                                    inaccurate_measurement = False
                                else:
                                    ts.log('    EUT outside the IEEE 1547-2018 requirements. Bounds = [%0.1f, %0.1f], '
                                           'Value = %0.1f' % (setpoint_pct - accuracy, setpoint_pct + accuracy, value))
                                    ts.sleep(1)
                            ts.log('RESULT = %s' % test_pass_fail)

                    ts.log_debug('    ****Resetting Function **** ')
                    if crp:
                        eut.set_const_q(params={"const_q_mode_enable": False})
                    else:
                        eut.set_const_pf(params={"const_pf_mode_enable": False})

                '''
                ________________________________________________________________________________________________________
                Monitoring          Operating               Operating               Criteria
                information         Point A                 Point B
                parameter                                
                ________________________________________________________________________________________________________
                Voltage(s)          At or below             At or above 1.08 × (ac  Reported values match test operating
                                    0.90 × (ac voltage      voltage nominal         conditions within the accuracy 
                                    nominal rating).        rating).                requirements specified in Table 3 in
                                                                                    IEEE Std 1547-2018. (+/-1% Vnom)
                '''
                if ts.param_value('iop_params.mon.monitor_v') == 'Yes':
                    accuracy = 1.
                    ts.log('Starting Monitoring Assessment. Voltage reported from the EUT is: %s' %
                           eut.get_monitoring().get('mn_v'))
                    ts.log('')
                    ts.log('**** Voltage Monitoring Test ****')
                    for setpoint in [89., 109.]:  # pu
                        v_grid = setpoint * 0.01 * v_nom  # V
                        if grid is not None:
                            grid.voltage(v_grid)
                        ts.log_debug('****Configuring Experiment. Setting grid voltage to %0.2f V' % v_grid)
                        ts.sleep(2)
                        inaccurate_measurement = True
                        timeout = timeout_duration
                        test_pass_fail = 'FAIL'
                        while inaccurate_measurement and timeout > 0:
                            timeout -= 1
                            if grid is not None:
                                voltages = grid.meas_voltage()
                            else:
                                voltages = [v_grid, v_grid, v_grid]
                            meas_volt_mean_pct = ((sum(voltages)/len(voltages))/v_nom)*100.
                            eut_volt = list(eut.get_monitoring().get("mn_v"))
                            for v in eut_volt:
                                if v is None:
                                    ts.log_warning('EUT voltage data includes nulls (%s). Check ACType.' % eut_volt)
                            # ts.log_debug('voltages: %s, vnom = %s' % (eut_volt, v_nom))
                            eut_volt_mean_pct = ((sum(eut_volt)/len(eut_volt))/v_nom)*100.
                            ts.log('    EUT-reported voltage is currently %0.1f%%, real voltage = %s%%, '
                                   'waiting another %0.1f sec' % (eut_volt_mean_pct, meas_volt_mean_pct, timeout))
                            if meas_volt_mean_pct - accuracy <= eut_volt_mean_pct <= meas_volt_mean_pct + accuracy:
                                ts.log('    EUT has recorded value of +/- %s%% as required by IEEE 1547-2018.' % accuracy)
                                test_pass_fail = 'PASS'
                                inaccurate_measurement = False
                            else:
                                ts.log('    EUT outside the IEEE 1547-2018 requirements. Bounds = [%0.1f, %0.1f], '
                                       'Value = %0.1f' % (meas_volt_mean_pct - accuracy, meas_volt_mean_pct + accuracy,
                                                          eut_volt_mean_pct))
                                ts.sleep(1)
                        ts.log('RESULT = %s' % test_pass_fail)
                    if grid is not None:
                        grid.voltage(v_nom)

                '''
                ________________________________________________________________________________________________________
                Monitoring          Operating               Operating               Criteria
                information         Point A                 Point B
                parameter                                
                ________________________________________________________________________________________________________
                Frequency           At or below 57.2 Hz.    At or above 61.6 Hz.    Reported values match test operating
                                                                                    conditions within the accuracy 
                                                                                    requirements specified in Table 3 in 
                                                                                    IEEE Std 1547-2018. (10 mHz)
                '''
                if ts.param_value('iop_params.mon.monitor_f') == 'Yes':
                    accuracy = 0.01  # 10 mHz
                    ts.log('Starting Monitoring Assessment. Frequency reported from the EUT is: %s' %
                           eut.get_monitoring().get('mn_hz'))
                    ts.log('')
                    ts.log('**** Frequency Monitoring Test ****')
                    for setpoint in [57., 61.8]:
                        if grid is not None:
                            grid.freq(setpoint)
                        ts.log_debug('****Configuring Experiment. Setting grid frequency to %s Hz' % setpoint)
                        ts.sleep(2)
                        inaccurate_measurement = True
                        timeout = timeout_duration
                        test_pass_fail = 'FAIL'
                        while inaccurate_measurement and timeout > 0:
                            timeout -= 1
                            eut_freq = eut.get_monitoring().get("mn_hz")
                            ts.log('    EUT-reported freq is currently %0.3f Hz, real freq = %0.3f Hz, '
                                   'waiting another %0.1f sec' % (eut_freq, setpoint, timeout))
                            if setpoint - accuracy <= eut_freq <= setpoint + accuracy:
                                ts.log('    EUT has recorded value of +/- %s%% as required by IEEE 1547-2018.' %
                                       accuracy)
                                test_pass_fail = 'PASS'
                                inaccurate_measurement = False
                            else:
                                ts.log('    EUT outside the IEEE 1547-2018 requirements. Bounds = [%0.3f, %0.3f], '
                                       'Value = %0.3f' % (setpoint - accuracy, setpoint + accuracy, eut_freq))
                                ts.sleep(1)
                        ts.log('RESULT = %s' % test_pass_fail)
                    if grid is not None:
                        grid.freq(60.)

                '''
                ________________________________________________________________________________________________________
                Monitoring          Operating               Operating               Criteria
                information         Point A                 Point B
                parameter                                
                ________________________________________________________________________________________________________
            
                Operational State   On: Conduct this test   Off: If supported by    Reported Operational State matches 
                                    while the DER is        the DER, conduct this   the device present condition for on 
                                    generating.             test while capable of   and off states.
                                                            communicating but not
                                                            capable of generating.
                '''
                if ts.param_value('iop_params.mon.monitor_st') == 'Yes':
                    ts.log('Starting Monitoring Assessment. State reported from the EUT is: %s' %
                           eut.get_monitoring().get('mn_st'))
                    ts.log('')
                    ts.log('**** Operational State Monitoring Test ****')
                    for state in [True, False]:
                        conn_mode = False
                        try:
                            eut.set_conn(params={'conn': state})
                            conn_mode = True
                        except Exception as e:
                            ts.log_warning('Could not test operation state using connect/disconnect. %s' % e)
                            eut.set_es_permit_service(params={'es_permit_service': state})
                        ts.log_debug('****Configuring Experiment. Setting EUT Operational State to %s' % state)
                        ts.sleep(2)
                        inaccurate_measurement = True
                        timeout = timeout_duration
                        test_pass_fail = 'FAIL'
                        while inaccurate_measurement and timeout > 0:
                            timeout -= 1
                            eut_conn = eut.get_monitoring().get('mn_st')
                            ts.log('    EUT-reported connection = %s, State setting = %s, waiting another %0.1f sec' %
                                   (eut_conn, state, timeout))
                            if eut_conn == state:
                                test_pass_fail = 'PASS'
                                inaccurate_measurement = False
                            else:
                                ts.log('    EUT Operational State did not match per IEEE 1547-2018 requirements.')
                                ts.sleep(1)
                        ts.log('RESULT = %s' % test_pass_fail)
                    if conn_mode:
                        eut.set_conn(params={'conn': True})
                    else:
                        eut.set_es_permit_service(params={'es_permit_service': True})

                '''
                ________________________________________________________________________________________________________
                Monitoring          Operating               Operating               Criteria
                information         Point A                 Point B
                parameter                                
                ________________________________________________________________________________________________________
                Connection Status   Connected: Conduct      Disconnected:           Reported Connection Status matches 
                                    this test while the     Conduct this test while the device present connection 
                                    DER is generating.      permit service is       condition.
                                                            disabled.
                '''
                if ts.param_value('iop_params.mon.monitor_conn') == 'Yes':
                    ts.log('Starting Monitoring Assessment. Connection Status reported from the EUT is: %s' %
                           eut.get_monitoring().get('mn_conn'))
                    ts.log('')
                    ts.log('**** Connection Status Monitoring Test ****')
                    for conn in [True, False]:
                        conn_mode = False
                        try:
                            eut.set_conn(params={'conn': conn})
                            conn_mode = True
                        except Exception as e:
                            ts.log_warning('Could not test operation state using connect/disconnect. %s' % e)
                            eut.set_es_permit_service(params={'es_permit_service': conn})
                        ts.log_debug('****Configuring Experiment. Setting EUT connection status to %s' % conn)
                        ts.sleep(2)
                        inaccurate_measurement = True
                        timeout = timeout_duration
                        test_pass_fail = 'FAIL'
                        while inaccurate_measurement and timeout > 0:
                            timeout -= 1
                            eut_conn = eut.get_monitoring().get('mn_conn')
                            ts.log('    EUT-reported Status = %s, Connection Status = %s, waiting another %0.1f sec' %
                                   (eut_conn, conn, timeout))
                            if eut_conn == conn:
                                test_pass_fail = 'PASS'
                                inaccurate_measurement = False
                            else:
                                ts.log('    EUT Connection State did not match per IEEE 1547-2018 requirements.')
                                ts.sleep(1)
                        ts.log('RESULT = %s' % test_pass_fail)
                    if conn_mode:
                        eut.set_conn(params={'conn': True})
                    else:
                        eut.set_es_permit_service(params={'es_permit_service': True})

                '''
                ________________________________________________________________________________________________________
                Monitoring          Operating               Operating               Criteria
                information         Point A                 Point B
                parameter                                
                ________________________________________________________________________________________________________
                Alarm Status        Has alarms set.         No alarms set.          Reported Alarm Status matches the 
                                                                                    device present alarm condition for 
                                                                                    alarm and no alarm conditions. For 
                                                                                    test purposes only, the DER 
                                                                                    manufacturer shall specify at least 
                                                                                    one way an alarm condition that
                                                                                    is supported in the protocol being 
                                                                                    tested can be set and cleared.
                '''
                if ts.param_value('iop_params.mon.monitor_alrm') == 'Yes':
                    ts.log('')
                    ts.log('**** Alarm Status Monitoring Test ****')
                    for error in [True, False]:
                        if error:
                            if grid is not None:
                                ts.log_debug('Setting grid voltage to v_nom * 1.25 to trigger overvoltage alarm.')
                                grid.voltage(v_nom * 1.25)  # configure a high voltage error state
                                ts.log_debug('Waiting 5 sec to allow alarm to be enabled.')
                                ts.sleep(5.)
                        else:
                            if grid is not None:
                                grid.voltage(v_nom)  # disable a high voltage error state
                        ts.log_debug('****Configuring Experiment. Setting EUT error to %s' % error)
                        ts.sleep(2)
                        inaccurate_measurement = True
                        timeout = timeout_duration
                        test_pass_fail = 'FAIL'
                        while inaccurate_measurement and timeout > 0:
                            timeout -= 1
                            # over voltage alarm isn't supported in DNP3
                            eut_error = eut.get_monitoring().get('mn_alrm').get('mn_alm_over_volt')
                            ts.log('    EUT-reported Status = %s, Error Status = %s, waiting another %0.1f sec' %
                                   (eut_error, error, timeout))
                            if eut_error == error:
                                test_pass_fail = 'PASS'
                                inaccurate_measurement = False
                            else:
                                ts.log('    EUT Overvoltage Alarm did not match per IEEE 1547-2018 requirements.')
                                ts.sleep(1)
                        ts.log('RESULT = %s' % test_pass_fail)
                    if grid is not None:
                        grid.voltage(v_nom)  # disable an error state

            else:
                ts.log_warning('DER measurements testing not supported')
        else:
            ts.log('Skipping DER monitoring test')

        # ########### Spot checks for other functionality ###############

        # Test Const PF functionality
        if ts.param_value('spot_checks.cpf') == 'Yes':
            ts.log('')
            ts.log('********* Constant PF Spot Check *********')
            for pf in [(0.90, 'inj'), (-0.90, 'abs'), (0.85, 'inj')]:
                ts.log('Test PF Read: %s' % eut.get_const_pf())
                ts.log('Test PF Write: %s' % eut.set_const_pf(params={"const_pf_mode_enable": True,
                                                                         # "const_pf_abs": pf[0],
                                                                         "const_pf_inj": pf[0],
                                                                         "const_pf_excitation": pf[1]}))
                ts.sleep(wait_time)
                ts.log('Test PF Read: %s' % eut.get_const_pf())
                mn_var = eut.get_monitoring().get("mn_var")
                ts.log('Measured reactive power: %s kVar' % mn_var)
                ts.log('DER reactive power is %0.2f%% of var max' % (1.e5 * (mn_var / var_max)))
                ts.log('----')
            ts.log('Disabling PF')
            eut.set_const_pf(params={"const_pf_mode_enable": False})
            ts.log('Test PF Read: %s' % eut.get_const_pf())
        else:
            ts.log('Skipping CPF Spot Check')

        # Volt-Var
        if ts.param_value('spot_checks.vv') == 'Yes':
            ts.log('')
            ts.log('********* VV Spot Check *********')
            vv_data = eut.get_qv()
            # ts.log('Test VV Read: %s' % vv_data)
            print_params(vv_data)

            params = {'qv_mode_enable': True, 'qv_vref': v_nom, 'qv_vref_auto_mode': False,
                      'qv_vref_olrt': 1.0, 'qv_curve_v_pts': [0.95, 0.99, 1.01, 1.05],
                      'qv_curve_q_pts': [1., 0., 0., -1.],  'qv_olrt': 5.}
            ts.log('VV Write:')
            print_params(params)
            eut.set_qv(params=params)
            ts.sleep(wait_time)
            vv_data = eut.get_qv()
            ts.log('VV Readback:')
            print_params(vv_data)
            ts.log('----')

            params = {'qv_mode_enable': True, 'qv_curve_v_pts': [0.93, 0.98, 1.02, 1.08],
                      'qv_curve_q_pts': [0.3, 0., 0., -0.5]}
            ts.log('VV Write:')
            print_params(params)
            eut.set_qv(params=params)
            ts.sleep(wait_time)
            vv_data = eut.get_qv()
            ts.log('VV Readback:')
            print_params(vv_data)
            ts.log('----')

            ts.log('Disabling VV...')
            params = {'qv_mode_enable': False}
            print_params(params)
            eut.set_qv(params=params)
            ts.sleep(wait_time)
            vv_data = eut.get_qv()
            ts.log('VV Readback:')
            print_params(vv_data)
        else:
            ts.log('Skipping VV Spot Check')

        # Watt-Var
        if ts.param_value('spot_checks.wv') == 'Yes':
            ts.log('')
            ts.log('********* WV Spot Check *********')
            wv_data = eut.get_qp()
            # ts.log_debug('WV Read: %s' % wv_data)
            print_params(wv_data)
            ts.log('----')

            params = {'qp_mode_enable': True,
                      'qp_curve_p_gen_pts': [0.2, 0.5, 1.0],
                      'qp_curve_q_gen_pts': [0., 0., -0.44],
                      'qp_curve_p_load_pts': [-0.2, -0.5, -1.0],
                      'qp_curve_q_load_pts': [0., 0., 0.44]}
            ts.log("       New Points:")
            ts.log("       'qp_curve_p_gen_pts': [0.2, 0.5, 1.0]")
            ts.log("       'qp_curve_q_gen_pts': [0., 0., -0.44]")
            ts.log("       'qp_curve_p_load_pts': [-0.2, -0.5, -1.0]")
            ts.log("       'qp_curve_q_load_pts': [0., 0., 0.44]")
            eut.set_qp(params=params)
            ts.sleep(wait_time)
            ts.log("Readback:")
            wv_data = eut.get_qp()
            print_params(wv_data)
            ts.log('----')

            params = {'qp_mode_enable': True,
                      'qp_curve_p_gen_pts': [0.1, 0.6, 1.0],
                      'qp_curve_q_gen_pts': [0., -0.1, -0.25],
                      'qp_curve_p_load_pts': [-0.1, -0.6, -1.0],
                      'qp_curve_q_load_pts': [0., 0.1, 0.25]}
            ts.log("       New Points:")
            ts.log("       'qp_curve_p_gen_pts': [0.1, 0.6, 1.0]")
            ts.log("       'qp_curve_q_gen_pts': [0., -0.1, -0.25]")
            ts.log("       'qp_curve_p_load_pts': [-0.1, -0.6, -1.0]")
            ts.log("       'qp_curve_q_load_pts': [0., 0.1, 0.25]")
            eut.set_qp(params=params)
            ts.sleep(wait_time)
            ts.log("Readback:")
            wv_data = eut.get_qp()
            print_params(wv_data)
            ts.log('----')

            ts.log('Disabling WV...')
            eut.set_qp(params={'qp_mode_enable': False})
        else:
            ts.log('Skipping WV Spot Check')

        # Test Const Q functionality
        if ts.param_value('spot_checks.crp') == 'Yes':
            ts.log('')
            ts.log('********* CRP Spot Check *********')
            ts.log('CRP Read: %s' % eut.get_const_q())
            for q in [0.25, 0.59, 0.87, 0.45]:
                for excite in ['inj', 'abs']:
                    params = {"const_q_mode_enable": True, "const_q_mode_excitation": excite, "const_q": q}
                    ts.log('CRP Write:')
                    print_params(params)
                    eut.set_const_q(params=params)
                    ts.sleep(wait_time)
                    readback = eut.get_const_q()
                    ts.log('CRP Read:')
                    print_params(readback)

                    mn_var = eut.get_monitoring().get("mn_var")
                    # ts.log_debug('mn_var: %s' % mn_var)
                    # ts.log_debug('var_max: %s' % var_max)
                    ts.log('Reactive Power is currently %0.3f%% of var max' % (1e5 * (mn_var / var_max)))
                    ts.log('-' * 10)
            eut.set_const_q(params={"const_q_mode_enable": False})
        else:
            ts.log('Skipping CRP Spot Check')

        # Volt-Watt
        if ts.param_value('spot_checks.vw') == 'Yes':
            ts.log('')
            ts.log('********* VW Spot Check *********')
            vw_data = eut.get_pv()
            ts.log('VW Read:')
            print_params(vw_data)

            params = {'pv_mode_enable': True, 'pv_curve_v_pts': [1.03, 1.05],
                      'pv_curve_p_pts': [1.0, 0.2], 'pv_olrt': 5.}
            ts.log('VW Write: %s' % eut.set_pv(params=params))
            ts.sleep(wait_time)
            vw_data = eut.get_pv()
            # ts.log_debug('VW Read: %s' % vw_data)
            ts.log('VW Readback')
            print_params(vw_data)
            ts.log('-' * 10)

            params = {'pv_mode_enable': True, 'pv_curve_v_pts': [1.05, 1.08],
                      'pv_curve_p_pts': [1.0, 0.5]}
            ts.log('VW Write: %s' % eut.set_pv(params=params))
            ts.sleep(wait_time)
            vw_data = eut.get_pv()
            # ts.log_debug('VW Read: %s' % vw_data)
            ts.log('VW Readback')
            print_params(vw_data)
            ts.log('-' * 10)

            ts.log('Disabling VW...')
            eut.set_pv(params={'pv_mode_enable': False})
            vw_data = eut.get_pv()
            ts.log('VW Readback:')
            print_params(vw_data)
        else:
            ts.log('Skipping VW Spot Check')

        # Overvoltage Trip and Undervoltage Trip
        if ts.param_value('spot_checks.vt') == 'Yes':
            ts.log('')
            ts.log('********* Overvoltage VT Spot Check *********')
            ts.log('OV Trip Test OV Read: %s' % eut.get_ov())
            ts.log('-' * 10)
            params = {'ov_trip_v_pts': [1.10, 1.20], 'ov_trip_t_pts': [13, 0.16]}
            ts.log('OV Trip Test Write: %s' % eut.set_ov(params=params))
            ts.sleep(wait_time)
            ts.log('OV Trip Test Readback: %s' % eut.get_ov())
            ts.log('-' * 10)
            params = {'ov_trip_v_pts': [1.17, 1.25], 'ov_trip_t_pts': [15, 1.2]}
            ts.log('OV Trip Test Write: %s' % eut.set_ov(params=params))
            ts.sleep(wait_time)
            ts.log('OV Trip Test Readback: %s' % eut.get_ov())

            ts.log('')
            ts.log('********* Undervoltage VT Spot Check *********')
            ts.log('UV Trip Test Read: %s' % eut.get_uv())
            ts.log('-' * 10)
            params = {'uv_trip_v_pts': [0.88, 0.50], 'uv_trip_t_pts': [21.0, 2.0]}
            ts.log('UV Trip Test Write: %s' % eut.set_uv(params=params))
            ts.sleep(wait_time)
            ts.log('UV Trip Test Readback: %s' % eut.get_uv())
            ts.log('-' * 10)
            params = {'uv_trip_v_pts': [0.86, 0.55], 'uv_trip_t_pts': [20.0, 3.0]}
            ts.log('UV Trip Test Write: %s' % eut.set_uv(params=params))
            ts.sleep(wait_time)
            ts.log('UV Trip Test Readback: %s' % eut.get_uv())
        else:
            ts.log('Skipping VT Spot Check')

        # Overfrequency Trip and Underfrequency Trip
        if ts.param_value('spot_checks.ft') == 'Yes':
            ts.log('')
            ts.log('********* Overfrequency FT Spot Check *********')
            ts.log('OF Trip Test Read: %s' % eut.get_of())
            ts.log('-' * 10)
            params = {'of_trip_f_pts': [61.8, 62.0], 'of_trip_t_pts': [299, 5]}
            ts.log('OF Trip Test Write: %s' % eut.set_of(params=params))
            ts.sleep(wait_time)
            ts.log('OF Trip Test Read: %s' % eut.get_of())
            ts.log('-' * 10)
            params = {'of_trip_f_pts': [61.5, 63.8], 'of_trip_t_pts': [384, 0.5]}
            ts.log('OF Trip Test Write: %s' % eut.set_of(params=params))
            ts.sleep(wait_time)
            ts.log('OF Trip Test Read: %s' % eut.get_of())

            ts.log('')
            ts.log('********* Underfrequency FT Spot Check *********')
            ts.log('UF Trip Test Read: %s' % eut.get_uf())
            ts.log('-' * 10)
            params = {'uf_trip_f_pts': [59.2, 58.5], 'uf_trip_t_pts': [100, 10]}
            ts.log('UF Trip Test Write: %s' % eut.set_uf(params=params))
            ts.sleep(wait_time)
            ts.log('UF Trip Test Read: %s' % eut.get_uf())
            ts.log('-' * 10)
            params = {'uf_trip_f_pts': [59.6, 57.8], 'uf_trip_t_pts': [299, 5]}
            ts.log('UF Trip Test Write: %s' % eut.set_uf(params=params))
            ts.sleep(wait_time)
            ts.log('UF Trip Test Read: %s' % eut.get_uf())
        else:
            ts.log('Skipping FT Spot Check')

        # Frequency Droop
        if ts.param_value('spot_checks.fw') == 'Yes':
            ts.log('')
            ts.log('********* Freq Droop Spot Check *********')
            ts.log('FW Read: %s' % eut.get_pf())
            ts.log('-' * 10)
            params = {'pf_mode_enable': True, 'pf_dbof': 0.02, 'pf_dbuf': 0.02,
                      'pf_kof': 0.05, 'pf_kuf': 0.05, 'pf_olrt': 5.}
            ts.log('FW Write:')
            print_params(params)
            eut.set_pf(params=params)
            ts.sleep(wait_time)
            pf_read = eut.get_pf()
            ts.log('FW Read:')
            print_params(pf_read)

            ts.log('-' * 10)
            params = {'pf_mode_enable': True, 'pf_dbof': 0.036, 'pf_dbuf': 0.036,
                      'pf_kof': 0.08, 'pf_kuf': 0.08, 'pf_olrt': 5.}
            ts.log('FW Write:')
            print_params(params)
            eut.set_pf(params=params)
            ts.sleep(wait_time)
            pf_read = eut.get_pf()
            ts.log('FW Read:')
            print_params(pf_read)

            ts.log('-' * 10)
            ts.log('Disabling FW...')
            eut.set_pf(params={'pf_mode_enable': False})
            pf_read = eut.get_pf()
            ts.log('FW Read:')
            print_params(pf_read)
        else:
            ts.log('Skipping FW Spot Check')

        # ES Permit Service
        if ts.param_value('spot_checks.es') == 'Yes':
            ts.log('')
            ts.log('********* ES Spot Check *********')
            es_readback = eut.get_es_permit_service()
            ts.log('ES Read:')
            print_params(es_readback)
            ts.log('-' * 10)

            params = {'es_permit_service': True, 'es_v_low': 0.917, 'es_v_high': 1.05,
                      'es_f_low': 59.5, 'es_f_high': 60.1, 'es_randomized_delay': 300, 'es_delay': 300,
                      'es_ramp_rate': 300}
            ts.log('ES Write:')
            print_params(params)
            eut.set_es_permit_service(params=params)
            ts.sleep(wait_time)
            es_readback = eut.get_es_permit_service()
            ts.log('ES Read:')
            print_params(es_readback)

            ts.log('-' * 10)
            params = {'es_permit_service': True, 'es_v_low': 0.88, 'es_v_high': 1.06,
                      'es_f_low': 59.9, 'es_f_high': 61.0, 'es_randomized_delay': 600, 'es_delay': 1,
                      'es_ramp_rate': 1000}
            ts.log('ES Write:')
            print_params(params)
            eut.set_es_permit_service(params=params)
            ts.sleep(wait_time)
            es_readback = eut.get_es_permit_service()
            ts.log('ES Read:')
            print_params(es_readback)

            ts.log('-' * 10)
            ts.log('Disabling ES...')
            params = {'es_permit_service': False}
            eut.set_es_permit_service(params=params)
            ts.sleep(wait_time)
            es_readback = eut.get_es_permit_service()
            ts.log('ES Read:')
            print_params(es_readback)
        else:
            ts.log('Skipping ES Spot Check')

        # Voltage Momentary Cessation
        if ts.param_value('spot_checks.cte') == 'Yes':
            ts.log('')
            ts.log('********* Momentary Cessation / Cease to Energize Spot Check *********')
            ts.log('OV MC Test Read: %s' % eut.get_ov_mc())
            ts.log('-' * 10)
            params = {'ov_mc_v_pts': [1.10, 1.20], 'ov_mc_t_pts': [13, 0.16]}
            ts.log('OV MC Test Write: %s' % eut.set_ov_mc(params=params))
            ts.sleep(wait_time)
            ts.log('OV MC Test Read: %s' % eut.get_ov_mc())
            ts.log('-' * 10)
            params = {'ov_mc_v_pts': [1.15, 1.25], 'ov_mc_t_pts': [15, 1.2]}
            ts.log('OV MC Test Write: %s' % eut.set_ov_mc(params=params))
            ts.sleep(wait_time)
            ts.log('OV MC Test Read: %s' % eut.get_ov_mc())

            ts.log('-' * 10)
            ts.log('UV MC Test Read: %s' % eut.get_uv_mc())
            ts.log('-' * 10)
            params = {'uv_mc_v_pts': [0.88, 0.50], 'uv_mc_t_pts': [21.0, 2.0]}
            ts.log('UV MC Test Write: %s' % eut.set_uv_mc(params=params))
            ts.sleep(wait_time)
            ts.log('UV MC Test Read: %s' % eut.get_uv_mc())
            ts.log('-' * 10)
            params = {'uv_mc_v_pts': [0.86, 0.55], 'uv_mc_t_pts': [20.0, 3.0]}
            ts.log('UV MC Test Write: %s' % eut.set_uv_mc(params=params))
            ts.sleep(wait_time)
            ts.log('UV MC Test Read: %s' % eut.get_uv_mc())
        else:
            ts.log('Skipping CTE Spot Check')

        # Test limit active power functionality
        if ts.param_value('spot_checks.lap') == 'Yes':
            ts.log('')
            ts.log('********* LAP Spot Check *********')
            ts.log('LAP Read: %s' % eut.get_p_lim())
            ts.log('-' * 10)
            for p in [0.25, 0.59, 0.87, 0.45]:
                ts.log('LAP Write: %s' % eut.set_p_lim(params={"p_lim_mode_enable": True, "p_lim_w": p}))
                ts.sleep(wait_time)
                ts.log('LAP Readback: %s' % eut.get_p_lim())
                mn_w = eut.get_monitoring().get("mn_w")
                # ts.log('mn_w: %s' % mn_w)
                # ts.log('w_max: %s' % w_max)
                ts.log('Active Power is %0.3f%% of nameplate capacity' % (1e5 * (mn_w / w_max)))
                ts.log('-' * 10)
            ts.sleep(wait_time)
            ts.log('Disabling LAP...')
            eut.set_p_lim(params={"p_lim_mode_enable": False, "p_lim_w": 1.})
            ts.sleep(wait_time)
            ts.log('LAP Readback: %s' % eut.get_p_lim())
        else:
            ts.log('Skipping LAP Spot Check')

        # Connect/Disconnect
        if ts.param_value('spot_checks.conn') == 'Yes':
            ts.log('********* Connect/Disconnect Spot Check *********')
            ts.log('Conn/Disconn Read: %s' % eut.get_conn())
            ts.log('Conn/Disconn Write: %s' % eut.set_conn(params={'conn': False}))
            ts.sleep(wait_time)
            ts.log('Conn/Disconn Read: %s' % eut.get_conn())
            mn_w = eut.get_monitoring().get("mn_w")
            ts.log('Active Power is %0.3f%% of nameplate capacity' % (1e5 * (mn_w / w_max)))
            ts.log('-' * 10)
            ts.log('Conn/Disconn Write: %s' % eut.set_conn(params={'conn': True}))
            ts.sleep(wait_time)
            ts.log('Conn/Disconn Read: %s' % eut.get_conn())
            mn_w = eut.get_monitoring().get("mn_w")
            ts.log('Active Power is %0.3f%% of nameplate capacity' % (1e5 * (mn_w / w_max)))
        else:
            ts.log('Skipping Connect/Disconnect Spot Check')

        return script.RESULT_COMPLETE

    except script.ScriptFail as e:
        reason = str(e)
        if reason:
            ts.log_error(reason)

    finally:
        if daq is not None:
            daq.close()
        if pv is not None:
            pv.close()
        if grid is not None:
            if v_nom is not None:
                grid.voltage(v_nom)
            grid.close()
        if chil is not None:
            chil.close()
        if eut is not None:
            eut.close()
            if eut.close() != 'No Agent':
                try:
                    if 'DNP' in str(type(eut)):
                        eut.stop_agent()
                except Exception as e:
                    ts.log('Did not stop server agent, if one was running. Error: %s' % e)
        if result_summary is not None:
            result_summary.close()

    return result


def run(test_script):

    try:
        global ts
        ts = test_script
        rc = 0
        result = script.RESULT_COMPLETE

        ts.log_debug('')
        ts.log_debug('**************  Starting %s  **************' % (ts.config_name()))
        ts.log_debug('Script: %s %s' % (ts.name, ts.info.version))
        ts.log_active_params()

        result = test_run()

        ts.result(result)
        if result == script.RESULT_FAIL:
            rc = 1

    except Exception as e:
        ts.log_error('Test script exception: %s' % traceback.format_exc())
        rc = 1

    sys.exit(rc)

info = script.ScriptInfo(name=os.path.basename(__file__), run=run, version='1.0.0')

info.param_group('iop_params', label='Test Parameters')
info.param('iop_params.print_comm_map', label='Print communication map of EUT', default='No', values=['Yes', 'No'])
info.param('iop_params.configuration_test', label='Run Configuration Test?', default='No', values=['Yes', 'No'])
info.param('iop_params.monitoring_test', label='Run Monitoring Test?', default='Yes', values=['Yes', 'No'])

info.param_group('iop_params.mon', label='Monitoring Tests', active='iop_params.monitoring_test', active_value='Yes')
info.param('iop_params.mon.monitor_p', label='Power Monitoring Test?', default='Yes', values=['Yes', 'No'])
info.param('iop_params.mon.monitor_q', label='Reactive Power Monitoring Test?', default='Yes', values=['Yes', 'No'])
info.param('iop_params.mon.monitor_v', label='Voltage Monitoring Test?', default='Yes', values=['Yes', 'No'])
info.param('iop_params.mon.monitor_f', label='Frequency Monitoring Test?', default='Yes', values=['Yes', 'No'])
info.param('iop_params.mon.monitor_st', label='Operational State Monitoring Test?', default='Yes', values=['Yes', 'No'])
info.param('iop_params.mon.monitor_conn', label='Connnection Status Monitoring Test?', default='Yes',
           values=['Yes', 'No'])
info.param('iop_params.mon.monitor_alrm', label='Alarm Status Monitoring Test?', default='Yes', values=['Yes', 'No'])

info.param_group('spot_checks', label='Grid-Support Function Spot Checks')
info.param('spot_checks.cpf', label='Constant Power Factor (CPF)', default='No', values=['Yes', 'No'])
info.param('spot_checks.vv', label='Active Power-Reactive Power (VV)', default='No', values=['Yes', 'No'])
info.param('spot_checks.wv', label='Active Power-Reactive Power (WV)', default='No', values=['Yes', 'No'])
info.param('spot_checks.crp', label='Constant Reactive Power (CRP)', default='No', values=['Yes', 'No'])
info.param('spot_checks.vw', label='Voltage-Active Power (VW) Mode', default='No', values=['Yes', 'No'])
info.param('spot_checks.vt', label='Voltage Trip (VT)', default='No', values=['Yes', 'No'])
info.param('spot_checks.ft', label='Frequency Trip (FT)', default='No', values=['Yes', 'No'])
info.param('spot_checks.fw', label='Frequency Droop (FW)', default='No', values=['Yes', 'No'])
info.param('spot_checks.es', label='Enter Service (ES)', default='No', values=['Yes', 'No'])
info.param('spot_checks.cte', label='Cease to Energize (CTE)', default='No', values=['Yes', 'No'])
info.param('spot_checks.lap', label='Limit Maximum Active Power (LAP)', default='No', values=['Yes', 'No'])
info.param('spot_checks.conn', label='Connect/Disconnect', default='No', values=['Yes', 'No'])

# EUT general parameters
info.param_group('eut', label='EUT Parameters', glob=True)
info.param('eut.wait_time', label='Wait time required for DER writes to go into effect.', default=5.0)
info.param('eut.p_rated', label='Output power rating (W)', default=10000.0)
info.param('eut.p_min', label='Minimum power rating (W)', default=100.0)
info.param('eut.s_rated', label='Output apparent power rating (VA)', default=10000.0)
info.param('eut.var_rated', label='Output var rating (vars)', default=4400.0)
info.param('eut.v_nom', label='Nominal AC voltage (V)', default=120.0)


der1547.params(info)
hil.params(info)
das.params(info)
pvsim.params(info)
gridsim.params(info)


def script_info():

    return info


if __name__ == "__main__":

    # stand alone invocation
    config_file = None
    if len(sys.argv) > 1:
        config_file = sys.argv[1]

    params = None

    test_script = script.Script(info=script_info(), config_file=config_file, params=params)

    run(test_script)


