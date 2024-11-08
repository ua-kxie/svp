"""
IEEE 1547.1-2020 Section 5.10 Unintentional islanding

The unintentional islanding test given in 5.10.2 may be used for any EUT. EUT that use conducted
permissive signals for unintentional islanding shall follow the procedure 5.10.3. EUT that have a
permissive hardware input shall follow the procedure in 5.10.4. Reverse-power or minimum import power
flow protection shall be tested in accordance with 5.10.5. EUT may support multiple methods and shall be
tested for each of the methods supported.

Full compliance is achieved by meeting the criteria of 5.10.2 or 5.10.5. Partial compliance is achieved by
meeting the criteria of 5.10.3 or 5.10.4, because those methods either require additional equipment beyond
what is tested in the type test or installed on the EPS. More information can be found in 8.1.2 on treatment
of full and partial compliance during DER evaluation and commissioning.

In order to facilitate faster test times, default time settings longer than 2.5 seconds may be reduced to as
low as 2.5 seconds for the purposes of these tests, and enter service delay settings may be adjusted to any
convenient value.

Initial Script: 8-27-20, jjohns2@sandia.gov

"""

import sys
import os
import traceback
from svpelab import hil
from svpelab import das
from svpelab import pvsim
from svpelab import der
from svpelab import der1547
from svpelab import p1547
import script
import time
import pprint


def find_rlc(p_utility, q_utility, r_set, l_set, c_set):
    """
    Proportional controllers for adjusting the resistance and capacitance values in the RLC load bank

    :param p_utility: utility/source active power in watts
    :param q_utility: utility/source reactive power in var
    :param r_set: prior resistor % change
    :param l_set: prior inductor % change
    :param c_set: prior capacitor % change
    :return:
    """
    # TODO Look into those calculation to make sure it fits our Simulated testbench
    smoothing_factor = 0.50  # only move a small percentage of the desired change for stability
    cap = c_set + (6./1300. * q_utility) * smoothing_factor
    res = r_set + (50.5/11700. * p_utility) * smoothing_factor

    return res, l_set, cap


def set_grid_support_functions(eut, cat, cat2, test_params):
    """
    Configure EUT for experiment

    :param eut: EUT object
    :param cat: Category A or B
    :param cat2: Category I, II, or III
    :param test_params: test parameters for the UI test
    :return: None
    """

    '''
    Adjusting the constant power factor according to table 13 (CAT A) or 14 (CAT B)
    '''
    if test_params['pf'] is not None:
        if test_params['pf'] < 0:
            eut.set_const_pf(params={
                'const_pf_mode_enable': True,
                'const_pf_excitation': 'abs',
                'const_pf_abs': test_params['pf'],
                'const_pf_olrt': 1.0
            })
        else:
            eut.set_const_pf(params={
                'const_pf_mode_enable': True,
                'const_pf_excitation': 'inj',
                'const_pf_inj': test_params['pf'],
                'const_pf_olrt': 1.0
            })

    '''
    Adjusting the constant reactive power according to table 13 (CAT A) or 14 (CAT B)
    '''
    if test_params['q_fixed'] is not None:
        if test_params['q_fixed'] < 0:
            eut.set_const_q(params={
                'const_q_mode_enable': True,
                'const_q_excitation': 'inj',
                'const_q': test_params['q_fixed'],
                'const_q_olrt': 1.0
            })
        else:
            eut.set_const_q(params={
                'const_q_mode_enable': True,
                'const_q_excitation': 'abs',
                'const_q': test_params['q_fixed'],
                'const_q_olrt': 1.0
            })
    '''
    Table 15 shows the voltage and frequency trip levels and clearing time settings to be used for the
    unintentional islanding tests. If the EUT is capable of operating at wider voltage and frequency trip
    settings, then such settings shall be used. The EUT may have additional voltage and frequency trip
    settings for self-protection, and such settings may remain enabled in the EUT.

            Table 15 —Voltage and frequency trip settings for unintentional islanding testing
    |--------------------------------------------------------------------------------------------------------
    | Trip           |             Category I and Category II       |            Category III               |
    | Function       | Voltage (p.u.)       | Clearing time (s)     | Voltage (p.u.) | Clearing time (s)    |
    ---------------------------------------------------------------------------------------------------------
        OV2                 1.2                     0.16                    1.2                 0.16
        OV1                 1.2                     13                      1.2                 13
        UV1                 0                       21                      0                   50
        UV2                 0                       2                       0                   21
    ---------------------------------------------------------------------------------------------------------
                       Frequency (Hz)      Clearing time (s)       Frequency (Hz)          Clearing time (s)
        OF2                 66                      1000                    66                  1000
        OF1                 66                      1000                    66                  1000
        UF1                 50                      1000                    50                  1000
        UF2                 50                      1000                    50                  1000
    ---------------------------------------------------------------------------------------------------------
    '''

    if cat2 == 'CAT_I' or cat2 == 'CAT_II':
        eut.set_ov(params={'ov_trip_v_pts': [1.2, 1.2], 'ov_trip_t_pts': [0.16, 13]})
        eut.set_uv(params={'uv_trip_v_pts': [0., 0.], 'uv_trip_t_pts': [21, 2]})
        eut.set_of(params={'of_trip_f_pts': [66., 66.], 'of_trip_t_pts': [1000, 1000]})
        eut.set_uf(params={'uf_trip_f_pts': [50., 50.], 'uf_trip_t_pts': [1000, 1000]})
    elif cat2 == 'CAT_III':
        eut.set_ov(params={'ov_trip_v_pts': [1.2, 1.2], 'ov_trip_t_pts': [0.16, 13]})
        eut.set_uv(params={'uv_trip_v_pts': [0., 0.], 'uv_trip_t_pts': [50, 21]})
        eut.set_of(params={'of_trip_f_pts': [66., 66.], 'of_trip_t_pts': [1000, 1000]})
        eut.set_uf(params={'uf_trip_f_pts': [50., 50.], 'uf_trip_t_pts': [1000, 1000]})
    else:
        eut.set_ov(params={'ov_trip_v_pts': [1.2, 1.1], 'ov_trip_t_pts': [0.16, 13]})
        eut.set_uv(params={'uv_trip_v_pts': [0.88, 0.1], 'uv_trip_t_pts': [21.0, 2.0]})
        eut.set_of(params={'of_trip_f_pts': [66., 66.], 'of_trip_t_pts': [1000, 1000]})
        eut.set_uf(params={'uf_trip_f_pts': [50., 50.], 'uf_trip_t_pts': [1000, 1000]})

    '''
    Table 16 shows the most aggressive settings for the voltage–active power function to be used in
    these tests. The P2 setting is intentionally set to a low but nonzero value so that the tester can
    differentiate between when the unit stops operating due to unintentional islanding operation versus
    power being reduced to zero due to this function response. Testing of a storage system configured
    with these settings is applicable to this type test.

    Table 16 — Voltage–active power (VW) settings for unintentional islanding testing
    |-------------------------------------------------------------------------------
    | Setting        |             Most aggressive       |            Default      |
    --------------------------------------------------------------------------------
                                                 Voltage (p.u.)                    
         V1                             1.05                            1.06
         V2                             1.06                            1.10
    --------------------------------------------------------------------------------
                                                 Active power (p.u.)
         P1                             1.0                             1.0
         P2                             0.2                             0.2
    --------------------------------------------------------------------------------
                                                 Response time (s)
    Open Loop Response Time             0.5                             10
    --------------------------------------------------------------------------------
    '''
    if test_params['vw'] == 'Default':
        eut.set_pv(params={'pv_mode_enable': True, 'pv_curve_v_pts': [1.06, 1.10],
                           'pv_curve_p_pts': [1., 0.2], 'pv_olrt': 10.})
    elif test_params['vw'] == 'MA':
        eut.set_pv(params={'pv_mode_enable': True, 'pv_curve_v_pts': [1.05, 1.06],
                           'pv_curve_p_pts': [1., 0.2], 'pv_olrt': 0.5})
    else:
        eut.set_pv(params={'pv_mode_enable': False})

    '''
    Table 17 shows the settings for the voltage-reactive power function to be used in these tests. The
    autonomously adjusted reference voltage (VRef) capability of the DER is not enabled for this testing
    since the fastest time constant is 300 s, far longer than any response that would affect unintentional
    islanding operation. The values in this table are for VRef = 1.00 p.u. VRef may be adjusted during the
    power balance setup of the test, as needed, so that the testing is started in the center of the VV
    curve. If the EUT has a wider range of capability than the settings in Table 17, such wider settings
    may be used.

    Table 17 — Voltage–reactive power (VV) settings for unintentional islanding testing Setting Category A
    |-------------------------------------------------------------------------------------------------
    | Setting           |                  Category A          |                 Category B             |
    |                   | Most aggressive      | Default       | Most aggressive      | Default         |
    --------------------------------------------------------------------------------------------------
                                                 Voltage (p.u.)                    
    | V1                | 0.98                 | 0.9           | 0.98                  | 0.92           
    | V2                | 1.00                 | 1.0           | 1.00                  | 0.98           
    | V3                | 1.00                 | 1.0           | 1.00                  | 1.02          
    | V4                | 1.02                 | 1.1           | 1.02                  | 1.08           
    --------------------------------------------------------------------------------------------------
                                                 Reactive power (p.u.)
    | Q1                | 0.25                 | 0.25           | 0.44                  | 0.44           
    | Q2                | 0.00                 | 0              | 0                     | 0   
    | Q3                | 0.00                 | 0              | 0                     | 0   
    | Q4                | -0.25                | -0.25          | -0.44                 | -0.44     
    --------------------------------------------------------------------------------------------------
                                                 Response time (s)
    Open Loop Rsp Time  | 1.00                 | 10            | 1                     | 5        
    --------------------------------------------------------------------------------
    '''
    if cat == 'CAT_A':
        if test_params['vv'] == 'Default':
            eut.set_qv(params={'qv_mode_enable': True, 'qv_vref': 1., 'qv_vref_auto_mode': 'Off',
                               'qv_curve_v_pts': [0.9, 1., 1., 1.1],
                               'qv_curve_q_pts': [0.25, 0., 0., -0.25], 'qv_olrt': 10.})
        elif test_params['vv'] == 'MA':
            eut.set_qv(params={'qv_mode_enable': True, 'qv_vref': 1., 'qv_vref_auto_mode': 'Off',
                               'qv_curve_v_pts': [0.98, 1., 1., 1.02],
                               'qv_curve_q_pts': [0.25, 0., 0., -0.25], 'qv_olrt': 1.})
        else:
            eut.set_qv(params={'qv_mode_enable': False})
    else:
        if test_params['vv'] == 'Default':
            eut.set_qv(params={'qv_mode_enable': True, 'qv_vref': 1., 'qv_vref_auto_mode': 'Off',
                               'qv_curve_v_pts': [0.92, 0.98, 1.02, 1.08],
                               'qv_curve_q_pts': [0.44, 0., 0., -0.44], 'qv_olrt': 5.})
        elif test_params['vv'] == 'MA':
            eut.set_qv(params={'qv_mode_enable': True, 'qv_vref': 1., 'qv_vref_auto_mode': 'Off',
                               'qv_curve_v_pts': [0.98, 1., 1., 1.02],
                               'qv_curve_q_pts': [0.44, 0., 0., -0.44], 'qv_olrt': 1.})
        else:
            eut.set_qv(params={'qv_mode_enable': False})

    '''

    Table 18 shows the settings for the active power-reactive power function to be used in these tests.

                            Table 18 — Active power–reactive power settings
    |-------------------------------------------------------------------------------------------------
    | Setting           |                  Category A          |                 Category B             |
    |                   | Most aggressive      | Default       | Most aggressive      | Default         |
    --------------------------------------------------------------------------------------------------
                                                 Active power (p.u.)                    
    | P1                | 0.2                  | 0.2           | 0.2                  | 0.2          
    | P2                | 0.8                  | 0.5           | 0.9                  | 0.5          
    | P3                | 0.9                  | 1.0           | 1.0                  | 1.0    
    |-------------------------------------------------------------------------------------------------
                                                 Reactive power (p.u.)
    | Q1                | 0.44                 | 0.0           | 0.44                 | 0.0           
    | Q1                | 0.44                 | 0.0           | 0.44                 | 0.0           
    | Q1                | -0.25                | -0.25         | -0.44                | -0.44           
    |-------------------------------------------------------------------------------------------------

    '''
    if cat == 'CAT_A':
        if test_params['wv'] == 'Default':
            eut.set_qp(params={'qp_mode_enable': True, 'qp_curve_p_gen_pts': [0.2, 0.5, 1.0],
                               'qp_curve_q_gen_pts': [0., 0., -0.25]})
        elif test_params['wv'] == 'MA':
            eut.set_qp(params={'qp_mode_enable': True, 'qp_curve_p_gen_pts': [0.2, 0.8, 0.9],
                               'qp_curve_q_gen_pts': [0.44, 0.44, -0.25]})
        else:
            eut.set_pv(params={'qp_mode_enable': False})
    else:
        if test_params['wv'] == 'Default':
            eut.set_qp(params={'qp_mode_enable': True, 'qp_curve_p_gen_pts': [0.2, 0.5, 1.0],
                               'qp_curve_q_gen_pts': [0., 0., -0.44]})
        elif test_params['wv'] == 'MA':
            eut.set_qp(params={'qp_mode_enable': True, 'qp_curve_p_gen_pts': [0.2, 0.9, 1.0],
                               'qp_curve_q_gen_pts': [0.44, 0.44, -0.44]})
        else:
            eut.set_qp(params={'qp_mode_enable': False})

    '''
    Table 19 shows the settings for the frequency-droop function to be used in these tests. Least
    aggressive, default, and most aggressive settings are used in the test matrix in Table 13 and Table
    14.

                        Table 19 —Frequency-droop (FW) settings for unintentional islanding testing
    |---------------------------------------------------------------------------------------------------------------
    | Setting        |             Category I and Category II       |            Category III               
    |                | Least aggressive | Default | Most aggressive | Least aggressive | Default | Most aggressive 
    ----------------------------------------------------------------------------------------------------------------
        dbOF, dbUF          1.0            0.036        0.017               1.0         0.036       0.017
        kOF, kUF            0.05            0.05        0.03                0.05        0.05        0.02
        T_response (s)      0               5             1                 10          5           0.2
    ----------------------------------------------------------------------------------------------------------------
    '''
    if cat2 == 'CAT_I' or cat2 == 'CAT_II':
        if test_params['fw'] == 'la':
            eut.set_pf(params={'pf_mode_enable': True, 'pf_dbof': 1.0, 'pf_dbuf': 1.0,
                               'pf_kof': 0.05, 'pf_kuf': 0.05, 'pf_olrt': 0.})
        elif test_params['fw'] == 'Default':
            eut.set_pf(params={'pf_mode_enable': True, 'pf_dbof': 0.036, 'pf_dbuf': 0.036,
                               'pf_kof': 0.05, 'pf_kuf': 0.05, 'pf_olrt': 5.})
        else:  # ma
            eut.set_pf(params={'pf_mode_enable': True, 'pf_dbof': 0.017, 'pf_dbuf': 0.017,
                               'pf_kof': 0.03, 'pf_kuf': 0.03, 'pf_olrt': 1.})
    else:
        if test_params['fw'] == 'la':
            eut.set_pf(params={'pf_mode_enable': True, 'pf_dbof': 1.0, 'pf_dbuf': 1.0,
                               'pf_kof': 0.05, 'pf_kuf': 0.05, 'pf_olrt': 10.})
        elif test_params['fw'] == 'Default':
            eut.set_pf(params={'pf_mode_enable': True, 'pf_dbof': 0.036, 'pf_dbuf': 0.036,
                               'pf_kof': 0.05, 'pf_kuf': 0.05, 'pf_olrt': 5.})
        else:  # ma
            eut.set_pf(params={'pf_mode_enable': True, 'pf_dbof': 0.017, 'pf_dbuf': 0.017,
                               'pf_kof': 0.02, 'pf_kuf': 0.02, 'pf_olrt': 0.2})


def print_measurements(meas):
    """
    Print the UI measurements

    :param meas: daq measurements
    :return: None
    """

    ts.log('\tS3 voltages = [%0.1f, %0.1f, %0.1f] V and currents = [%0.1f, %0.1f, %0.1f] A' %
           (meas['AC_VRMS_SOURCE_1'], meas['AC_VRMS_SOURCE_2'], meas['AC_VRMS_SOURCE_3'],
            meas['AC_IRMS_SOURCE_1'], meas['AC_IRMS_SOURCE_2'], meas['AC_IRMS_SOURCE_3']))
    ts.log('\tSwitch S3 active powers = [%0.3f, %0.3f, %0.3f] W and reactive powers = [%0.3f, %0.3f, %0.3f] var' %
           (meas['AC_SOURCE_P']/3., meas['AC_SOURCE_P']/3., meas['AC_SOURCE_P']/3.,
            meas['AC_SOURCE_Q']/3., meas['AC_SOURCE_Q']/3., meas['AC_SOURCE_Q']/3.))
    ts.log('\tSwitch S2 active powers = [%0.3f, %0.3f, %0.3f] W and reactive powers = [%0.3f, %0.3f, %0.3f] var' %
           (meas['AC_P']/3., meas['AC_P']/3., meas['AC_P']/3.,
            meas['AC_Q']/3., meas['AC_Q']/3., meas['AC_Q']/3.))
    ts.log('\tActive powers = [[%0.3f, %0.3f, %0.3f] W and reactive powers = [%0.3f, %0.3f, %0.3f] var at '
           'resistive load' % (meas['AC_P_LOAD_R_1'], meas['AC_P_LOAD_R_2'], meas['AC_P_LOAD_R_3'],
                               meas['AC_Q_LOAD_R_1'], meas['AC_Q_LOAD_R_2'], meas['AC_Q_LOAD_R_3']))
    ts.log('\tActive powers = [%0.3f, %0.3f, %0.3f] W and reactive powers = [%0.3f, %0.3f, %0.3f] var at '
           'capacitive load' % (meas['AC_P_LOAD_C_1'], meas['AC_P_LOAD_C_2'], meas['AC_P_LOAD_C_3'],
                                meas['AC_Q_LOAD_C_1'], meas['AC_Q_LOAD_C_2'], meas['AC_Q_LOAD_C_3']))
    ts.log('\tActive powers = [%0.3f, %0.3f, %0.3f] W and reactive powers = [%0.3f, %0.3f, %0.3f] var at '
           'inductive load' % (meas['AC_P_LOAD_L_1'], meas['AC_P_LOAD_L_2'], meas['AC_P_LOAD_L_3'],
                               meas['AC_Q_LOAD_L_1'], meas['AC_Q_LOAD_L_2'], meas['AC_Q_LOAD_L_3']))


def run_ui_test(phil, model_name, daq, test_num, t_trips, q_inc, high_freq_count, low_freq_count, result_summary,
                c_set, p_rated, q_rated, q_c):
    """
    Run single UI test

    :param phil: Power hardware-in-the-loop object
    :param model_name: name of the PHIL model
    :param daq: DAQ object
    :param test_num: number of the test
    :param t_trips: trip time dict with {q_inc, t_trip}
    :param q_inc: reactive power increment
    :param high_freq_count: number of over frequency islanding events
    :param low_freq_count: number of under frequency islanding events
    :param result_summary: summary file
    :param c_set: capacitor setpoint
    :return: t_trips, t_trip, high_freq_count, low_freq_count
    """

    # adjust reactive load
    ctrl_sigs = phil.get_control_signals(details=False)
    ctrl_sigs[17] = c_set * q_inc  # Capacitor Pot
    phil.set_control_signals(values=ctrl_sigs)
    if q_inc == 0.95:
        a = 0

    count = 0
    while count < 20:
        ts.sleep(1)
        count += 1
        daq.data_sample()
        diff = abs((daq.data_read()['AC_Q_S3_PU']) - (1 - q_inc)*q_c)
        ts.log(f'Waited {count} sec for load to adjust. desired reactive power is {q_inc*q_c} pu, load reactive power is'
               f' {q_c - daq.data_read()["AC_Q_S3_PU"]} and error between them is {diff}')
        if diff < 0.0075:
            break
        # else:
        #     ctrl_sigs = phil.get_control_signals(details=False)
        #     c_set = ctrl_sigs[17]
        #     ctrl_sigs[17] = (c_set * q_inc)*(1 - (daq.data_read()['AC_Q_S3_PU']) - (1 - q_inc)*q_c * 10.0)  # Capacitor Pot (6./1300. * q_utility) * smoothing_factor
        #     phil.set_control_signals(values=ctrl_sigs)
        if count >= 20:
            ts.log_error('Load did not adjust correctly')
            raise Exception
    '''
    2) With the EUT and load operating at stable conditions, record the voltage and current at switch
    S3. Record the active and reactive power at switch S3 on a net and per phase basis. Record
    the active and reactive power of the EUT, the resistive load, the capacitive load and the
    inductive loads on a net and per phase basis as well. These measurements may be done
    individually for the EUT, resistive load, capacitive load and inductive loads prior to operating
    the entire combined circuit.
    '''
    ts.sleep(2.)
    daq.data_sample()
    meas = daq.data_read()
    ts.log('Step e)2) Print system measurements:')
    print_measurements(meas)

    '''
    3) Open switch S3 and measure the time it takes for the EUT to cease to energize the island.
    This is the time from when S3 opens to when instantaneous voltage and EUT current in the
    island drops and remains below 0.05 p.u. Record this as the clearing time.
    '''
    ts.log('Step e)3) Opening switch s3')
    # waveform OpWrite configured to capture when S3 is opened
    ctrl_sigs[2] = 1  #3 = Islanding Test
    daq.waveform_record()
    phil.set_control_signals(values=ctrl_sigs)

    ts.log('Waiting 10 seconds to determine trip time and island frequency.')
    ts.sleep(11)

    # Get console data
    daq.waveform_stop_record()
    daq.data_sample()
    t_trip = daq.data_read()['TRIP_TIME']
    freq = daq.data_read()['ISLAND_FREQ']  # calculate fundamental frequency after S3 is open
    t_trips[q_inc] = t_trip  # append trip time in dict with reactive power increment value key
    ts.log('For reactive power setpoint %0.3f, the island frequency was %0.2f Hz and the trip time was %0.2f s' %
           (q_inc, freq, t_trip))

    # Complete data capture
    '''
    RTLab OpWriteFile Math using worst case scenario of 5.5 seconds, 8 signals and Ts = 40e-6
    Duration of acquisition in number of points: Npoints = Nbss = (Tend-Tstart)/(Ts*dec) = (5.5)/(0.000040*5) = 27500
   
    Nbss = number of samples per signal (signal = acquisition frame) 
    Acquisition frame duration: Tframe = Nbss * Ts * dec = 1000*0.000040*5 = 2 sec
   
    Number of buffers to be acquired: Nbuffers = Npoints / Nbss = (Tend - Tstart) / Tframe = 2.75
   
    Minimum file size: MinSize = Nbuffers x SizeBuf = [(Tend - Tstart) / Ts ] * (Nsig+1) * 8 * Nbss
        = (5.5/40e-6)*(8)*8*1000 = 8.8e10
   
    SizeBuf = 1/Nbuffers * {[(Tend - Tstart) / Ts ]*(Nsig+1)*8*Nbss} = [(5.5/40e-6)*(8)*8*1000]/16 = 1375000
    Size of one buffer in bytes (SizeBuf) = (Nsig+1) * 8 * Nbss (Minimum) = (7+1)*8*1000 = 64000
    '''
    ts.log('Waiting 1 seconds for Opal to save the waveform data.')
    ts.sleep(1)

    # test_filename = 'UI_Test_%s_Q%0.2f' % (test_num, q_inc)
    # ts.log('------------{}------------'.format(test_filename))
    # # Convert and save the .mat file that contains the phase jump start
    # ts.log('Processing waveform dataset')
    # ds = daq.waveform_capture_dataset()  # returns list of databases of waveforms (overloaded)
    # ui_wave = '%s.csv' % test_filename
    # ts.log('Saving file: %s' % ui_wave)
    # ds[0].to_csv(ts.result_file_path(ui_wave))
    # ts.result_file(ui_wave)



    '''
    If at any point at least three test instances show island frequency increasing above the
    fundamental frequency of the ac test source after S3 was opened and at least three instances
    show island frequency decreasing below the fundamental frequency of the ac test source after
    S3 was opened S3 was opened, the remaining 1% steps and step e)5) may be omitted.
    '''
    f_nom = ts.param_value('eut.f_nom')
    if freq > f_nom:
        high_freq_count += 1
    else:
        low_freq_count += 1

    # 'Test, Start Waveform, Reactive Power, Trip Time'
    result_summary.write('%s, %s\n' % (q_inc, t_trip))

    return t_trips, t_trip, high_freq_count, low_freq_count


def energize_system(ctrl_sigs, phil, daq, eut_startup_time, p_rated, pv, s_rated):
    """
    Power on amplifier and wait for EUT to start

    :param ctrl_sigs: control signals from Console
    :param phil: phil object
    :param daq: daq object
    :param eut_startup_time: maximum time to wait for EUT start up
    :param p_rated: power rating of EUT
    :return: None
    """
    ts.sleep(9)
    ctrl_sigs[2] = 0.  # close S3
    # ctrl_sigs[3] = 0.  # energize amplifier
    # if not ts.confirm('ABOUT TO ENERGIZE AMPLIFIER - OK?'):
    #     raise Exception
    phil.set_control_signals(values=ctrl_sigs)

    count = 0
    while count < eut_startup_time:
        ts.sleep(1)
        count += 1
        daq.data_sample()
        inv_p_pu = daq.data_read()['AC_P'] / p_rated
        ts.log('Waited %s sec for EUT to start. Inverter power is %0.4f pourcent of base inverter power.' % (count, inv_p_pu * 100))
        if inv_p_pu > 0.9:
            break
        else:
            ctrl_sigs[3] = 1.  # de-energize amplifier
            phil.set_control_signals(values=ctrl_sigs)
            if pv is not None:
                pv.power_set(s_rated, irradiance=1100)
                pv.power_on()
                ts.sleep(0.5)
                ts.log('Setting PV power to %0.2f W' % s_rated)
            time.sleep(2.0)
            ctrl_sigs[2] = 0.  # close S3
            ctrl_sigs[3] = 0.  # energize amplifier
            phil.set_control_signals(values=ctrl_sigs)
            ts.sleep(10.0)
            if pv is not None:
                pv.power_set(p_rated, irradiance=1000)
                pv.power_on()
                ts.sleep(0.5)
                ts.log('Setting PV power to %0.2f W' % p_rated)
        if count >= eut_startup_time:
            ts.log_error('EUT did not start.')
            raise Exception

    ts.sleep(10)  # time to allow the console measurements to settle

# The following EUT functions are required for the UI test:
# eut.get_ui()
# eut.set_ui()
# eut.set_p_lim()
# eut.set_ov()  # Overvoltage trip
# eut.set_uv()  # Undervoltage trip
# eut.set_of()  # Overfrequency trip
# eut.set_uf()  # Underfrequency trip
# eut.set_pv()  # P(V) or Volt-Watt
# eut.set_qv()  # Q(V) or VV
# eut.set_qp()  # Q(P) or Watt-Var
# eut.set_pf()  # P(f) or Freq-Watt/Freq-Droop

# ctrl_sigs[0] = Control Signal #1 = Test Num
# ctrl_sigs[1] = Control Signal #2 = SubTest Num
# ctrl_sigs[2] = Control Signal #3 = Islanding Test
# ctrl_sigs[3] = Control Signal #4 = Ametek Output
# ctrl_sigs[4] = Control Signal #5 = Inv VLL
# ctrl_sigs[5] = Control Signal #6 = Inv VAmax
# ctrl_sigs[6] = Control Signal #7 = V Trans. Gain
# ctrl_sigs[7] = Control Signal #8 = Phase Comp. (Deg)
# ctrl_sigs[8] = Control Signal #9 = Resistors Pot
# ctrl_sigs[9] = Control Signal #10 = Res Man Test
# ctrl_sigs[10] = Control Signal #11 = PR Cust. Test
# ctrl_sigs[11] = Control Signal #12 = Rinternal Pot
# ctrl_sigs[12] = Control Signal #13 = Rinternal Manual Test
# ctrl_sigs[13] = Control Signal #14 = PL Custom Test
# ctrl_sigs[14] = Control Signal #15 = Inductor Pot
# ctrl_sigs[15] = Control Signal #16 = Inductor Manual Test
# ctrl_sigs[16] = Control Signal #17 = QL Custom Test
# ctrl_sigs[17] = Control Signal #18 = Capacitor Pot
# ctrl_sigs[18] = Control Signal #19 = Cap Man Test
# ctrl_sigs[19] = Control Signal #20 = QC Cust. Test


def test_run():

    result = script.RESULT_PASS
    phil = None
    daq = None
    pv = None
    eut = None
    result_summary = None
    dataset_filename = None
    ds = None
    result_params = None

    try:
        open_proj = ts.param_value('hil_config.open')
        compilation = ts.param_value('hil_config.compile')
        stop_sim = ts.param_value('hil_config.stop_sim')
        load = ts.param_value('hil_config.load')
        execute = ts.param_value('hil_config.execute')
        model_name = ts.param_value('hil_config.model_name')

        test_nums = str(ts.param_value('ui.test_num')).split(',')
        test_num = []
        for t in test_nums:
            try:
                test_num.append(int(t))
            except ValueError as e:
                ts.log_error('Invalid test numbers: %s' % e)
                raise

        n_iter = ts.param_value('ui.n_iter')
        eut_startup_time = ts.param_value('ui_startup.eut_startup_time')

        v_ll = ts.param_value('eut.v_ll')
        v_nom = ts.param_value('eut.v_nom')
        s_rated = ts.param_value('eut.s_rated')
        p_rated = s_rated
        phase_comp = ts.param_value('ui.phase_comp')
        v_tranducer_scale = ts.param_value('ui.transducer_gain')

        cat = ts.param_value('eut.cat')
        cat2 = ts.param_value('eut.cat2')
        var_rated = ts.param_value('eut.var_rated')
        phases = ts.param_value('eut.phases')

        '''
        a) Test circuit configuration:
        
            1) The test circuit shall be configured as shown in Figure 7 using only the number of phases
            required for EUT operation. The connection of the neutral conductor to the EUT is only
            required when the EUT has a neutral connection. If the EUT does not have an equipment
            ground connection, then GND is not required to be connected to the EUT. The neutral
            connection shall be unaffected by the operation of switch S3 or S2. Switches S2 and S3 shall
            be gang-operated and multi-pole. The grounding of the load and ac test source shall be
            unaffected by the position of switch S3. Switch S2 is not required but is permitted.
            
            2) Connect the EUT according to the instructions and specifications provided by the
            manufacturer. If the EUT manufacturer requires an external or separate transformer, the
            transformer is to be included in the test configuration between the EUT and RLC load
            components.
            
            3) The ac test source voltage is set to EUT nominal voltage ± 5% and nominal frequency.
        '''

        # initialize the hardware in the loop
        phil = hil.hil_init(ts)

        """
        A separate module has been create for the 1547.1 Standard
        """
        active_function = p1547.ActiveFunction(ts=ts, functions=['UI'], script_name='UI',
                                               criteria_mode=[False, False, False])
        ts.log_debug("1547.1 Library configured for %s" % active_function.get_script_name())

        # initialize the pv
        pv = pvsim.pvsim_init(ts, support_interfaces={'hil': phil})
        if pv is not None:
            pv.power_set(1.00*p_rated, irradiance=1100)
            pv.power_on()
            ts.sleep(0.5)
            ts.log('Setting PV power to %0.2f W' % p_rated)



        # initialize the das
        das_points = active_function.get_sc_points()
        daq = das.das_init(ts, sc_points=das_points['sc'], support_interfaces={'hil': phil, 'pvsim': pv})
        ts.sleep(0.5)
        active_function.set_daq(daq)

        # initialize the der
        eut = der1547.der1547_init(ts, support_interfaces={'hil': phil})
        eut.config()
        ts.sleep(0.5)

        ts.log_debug('ui = %s' % eut.get_ui())

        # result params
        result_params = active_function.get_rslt_param_plot()
        # open result summary file
        result_summary_filename = 'result_summary.csv'
        result_summary = open(ts.result_file_path(result_summary_filename), 'a+')
        ts.result_file(result_summary_filename)
        result_summary.write('Test, Start Waveform, Reactive Power, Trip Time\n')

        '''
        b) EUT settings:
            1) Commanded active power operating mode, as described in Table 12, shall be used for UI
            testing.
            
                                                 Table 12 - EUT active power modes
        |----------------------------------------------------------------------------------------------------------
        | EUT active-power mode     | Description
        |----------------------------------------------------------------------------------------------------------
        | Tracking                  | For EUT operating with an input power tracking capability, the input source
        |                           | power is adjusted so that the EUT operates at the desired EUT output power
        |                           | level.
        |----------------------------------------------------------------------------------------------------------
        | Commanded                 | In this case, the EUT is set to a commanded active output power level. The
        |                           | input source power shall be set capable of delivering at least 125% active
        |                           | power in case the EUT needs to increase output active power that may occur
        |                           | during these tests. If the EUT is not capable of operating at a specified power
        |                           | level, then it shall be operated at its closest nonzero power level capability.
        -----------------------------------------------------------------------------------------------------------
        '''


        '''
        
            2) These tests shall be run for each of the test cases shown in Table 13 or Table 14, depending
            upon EUT category. The power levels in the tables are listed on a per unit basis with a
            tolerance of ± 0.05 p.u. and are listed in the generator frame of reference. The PEUT, QEUT
            operating points of the EUT are chosen to be spread out over a range of the active and
            reactive power capabilities defined in 5.2 of IEEE Std 1547-2018.
            
            Test cases 7A and 8A as well as voltage-active power (VW) functions are not required for
            Category A equipment shown in Table 13. However, if the EUT does support those functions
            then they shall be included in the unintentional islanding testing.


                    Table 13 — Balanced load unintentional islanding test matrix for Category A
    |-------------------------------------------------------------------------------------------------------------------
    | Test | EUT power level (p.u.) | Reactive power mode    | Active power mode | Initial RLC load (p.u.) | Effective
    | case |                        |                        | settings          |                         | quality 
    |      |                        |                        |                   |                         | factor 
    |      | -----------------------------------------------------------------------------------------------------------
    |      | PEUT       | QEUT      | Mode/setting | Resp    | VW      | FW      | PR+PL+PC | QC   | QL    | QF
    |      |            |           |              | time    |         |         |          |      |       |
    |-------------------------------------------------------------------------------------------------------------------
    | 1A   | 1.00       | 0.00      | Constant PF  | n/a     | Default | Default |  –1.00   | 1.00 | –1.00 | 1.00
    |-------------------------------| p.f. = 1.00  |--------------------------------------------------------------------
    | 2A   | 0.50       | 0.00      |              | n/a     | Default | Default |  –0.50   | 0.50 | –0.50 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 3A   | 0.90       | –0.25     | p.f. = –0.96 | n/a     | Off     | LA      |  –0.90   | 0.90 | –0.65 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 4A   | 0.90       | 0.44      | p.f. = 0.90  | n/a     | Off     | LA      |  –0.90   | 0.46 | –0.90 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 5A   | 1.00       | 0.00      | VV MA        | 1       | MA      | MA      |  –1.00   | 1.00 | –1.00 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 6A   | 0.50       | 0.00      | VV Default   | 10      | MA      | MA      |  –0.50   | 0.50 | –0.50 | 1.00    
    |-------------------------------------------------------------------------------------------------------------------
    | 7A   | 0.50       | 0.00      | WV Default   | n/a     | MA      | MA      |  –0.50   | 0.50 | –0.50 | 1.00    
    |-------------------------------------------------------------------------------------------------------------------
    | 8A   | 1.00       | 0.00      | WV MA        | n/a     | MA      | MA      |  –1.00   | 1.00 | –1.00 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 9A   | 0.90       | –0.25     | Const Q=-0.25| n/a     | MA      | MA      |  –0.90   | 0.90 | –0.65 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 10A   | 0.50      | 0.44      | Const Q=0.44 | n/a     | MA      | MA      |  –0.50   | 0.06 | –0.50 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | NOTE—LA = least aggressive; MA = most aggressive. As indicated in Table 16 through Table 19.
    |-------------------------------------------------------------------------------------------------------------------
    | a (p.u.) is per unit of the EUT kVA rating.
    | b Effective quality factor is provided for information only to help readers compare these test requirements with 
    | earlier versions of this standard. See Annex D for details.
    |-------------------------------------------------------------------------------------------------------------------

        '''
        cat_a_tests = {'1A': {'p_eut': 1., 'q_eut': 0., 'pf': 1., 'vv': None, 'wv': None, 'q_fixed': None,
                              't_resp': None, 'vw': 'Default', 'fw': 'Default',
                              'pr_pl_pc': -1., 'qc': 1., 'ql': -1., 'qf': 1.},
                       '2A': {'p_eut': 0.5, 'q_eut': 0., 'pf': 1., 'vv': None, 'wv': None, 'q_fixed': None,
                              't_resp': None, 'vw': 'Default', 'fw': 'Default',
                              'pr_pl_pc': -0.5, 'qc': 0.5, 'ql': -0.5, 'qf': 1.},
                       '3A': {'p_eut': 0.9, 'q_eut': -0.25, 'pf': -0.96, 'vv': None, 'wv': None, 'q_fixed': None,
                              't_resp': None, 'vw': None, 'fw': 'LA',
                              'pr_pl_pc': -0.90, 'qc': 0.90, 'ql': -0.65, 'qf': 1.},
                       '4A': {'p_eut': 0.9, 'q_eut': 0.44, 'pf': 0.90, 'vv': None, 'wv': None, 'q_fixed': None,
                              't_resp': None, 'vw': None, 'fw': 'LA',
                              'pr_pl_pc': -0.90, 'qc': 0.46, 'ql': -0.90, 'qf': 1.},
                       '5A': {'p_eut': 1.0, 'q_eut': 0., 'pf': None, 'vv': 'MA', 'wv': None, 'q_fixed': None,
                              't_resp': 1., 'vw': 'MA', 'fw': 'MA',
                              'pr_pl_pc': -1., 'qc': 1., 'ql': -1., 'qf': 1.},
                       '6A': {'p_eut': 0.5, 'q_eut': 0., 'pf': None, 'vv': 'Default', 'wv': None, 'q_fixed': None,
                              't_resp': 10., 'vw': 'MA', 'fw': 'MA',
                              'pr_pl_pc': -0.5, 'qc': 0.5, 'ql': -0.5, 'qf': 1.},
                       '7A': {'p_eut': 0.5, 'q_eut': 0., 'pf': None, 'vv': None, 'wv': 'Default', 'q_fixed': None,
                              't_resp': None, 'vw': 'MA', 'fw': 'MA',
                              'pr_pl_pc': -0.5, 'qc': 0.5, 'ql': -0.5, 'qf': 1.},
                       '8A': {'p_eut': 1., 'q_eut': 0., 'pf': None, 'vv': None, 'wv': 'MA', 'q_fixed': None,
                              't_resp': None, 'vw': 'MA', 'fw': 'MA',
                              'pr_pl_pc': -1., 'qc': 1., 'ql': -1., 'qf': 1.},
                       '9A': {'p_eut': 0.9, 'q_eut': -0.25, 'pf': None, 'vv': None, 'wv': None, 'q_fixed': -0.25,
                              't_resp': None, 'vw': 'MA', 'fw': 'MA',
                              'pr_pl_pc': -0.9, 'qc': 0.9, 'ql': -0.65, 'qf': 1.},
                       '10A': {'p_eut': 0.5, 'q_eut': 0.44, 'pf': None, 'vv': None, 'wv': None, 'q_fixed': 0.44,
                              't_resp': None, 'vw': 'MA', 'fw': 'MA',
                              'pr_pl_pc': -0.5, 'qc': 0.06, 'ql': -0.5, 'qf': 1.},
                       }

        '''

                    Table 13 — Balanced load unintentional islanding test matrix for Category B
    |-------------------------------------------------------------------------------------------------------------------
    | Test | EUT power level (p.u.) | Reactive power mode    | Active power mode | Initial RLC load (p.u.) | Effective
    | case |                        |                        | settings          |                         | quality 
    |      |                        |                        |                   |                         | factor 
    |      | -----------------------------------------------------------------------------------------------------------
    |      | PEUT       | QEUT      | Mode/setting | Resp    | VW      | FW      | PR+PL+PC | QC   | QL    | QF
    |      |            |           |              | time    |         |         |          |      |       |
    |-------------------------------------------------------------------------------------------------------------------
    | 1B   | 1.00       | 0.00      | p.f. = 1.00  | n/a     | Default | Default |  –1.00   | 1.00 | –1.00 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 2B   | 0.50       | 0.00      | p.f. = 1.00  | n/a     | Default | Default |  –0.50   | 0.50 | –0.50 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 3B   | 0.90       | –0.25     | p.f. = –0.90 | n/a     | Off     | LA      |  –0.90   | 0.90 | –0.46 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 4B   | 0.90       | 0.44      | p.f. = 0.90  | n/a     | Off     | LA      |  –0.90   | 0.46 | –0.90 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 5B   | 1.00       | 0.00      | VV MA        | 1       | MA      | MA      |  –1.00   | 1.00 | –1.00 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 6B   | 0.50       | 0.00      | VV Default   | 10      | MA      | MA      |  –0.50   | 0.50 | –0.50 | 1.00    
    |-------------------------------------------------------------------------------------------------------------------
    | 7B   | 0.50       | 0.00      | WV Default   | n/a     | MA      | MA      |  –0.50   | 0.50 | –0.50 | 1.00    
    |-------------------------------------------------------------------------------------------------------------------
    | 8B   | 1.00       | 0.00      | WV MA        | n/a     | MA      | MA      |  –1.00   | 1.00 | –1.00 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 9B   | 0.50       | –0.44     | Const Q=-0.44| n/a     | MA      | MA      |  –0.90   | 0.50 | –0.06 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | 10B   | 0.50      | 0.44      | Const Q=0.44 | n/a     | MA      | MA      |  –0.50   | 0.06 | –0.50 | 1.00
    |-------------------------------------------------------------------------------------------------------------------
    | NOTE—LA = least aggressive; MA = most aggressive. As indicated in Table 16 through Table 19.
    |-------------------------------------------------------------------------------------------------------------------
    | a (p.u.) is per unit of the EUT kVA rating.
    | b Effective quality factor is provided for information only to help readers compare these test requirements with 
    | earlier versions of this standard. See Annex D for details.
    |-------------------------------------------------------------------------------------------------------------------
        '''

        cat_b_tests = {'1B': {'p_eut': 1., 'q_eut': 0., 'pf': 1., 'vv': None, 'wv': None, 'q_fixed': None,
                              't_resp': None, 'vw': 'Default', 'fw': 'Default',
                              'pr_pl_pc': -1., 'qc': 1., 'ql': -1., 'qf': 1.},
                       '2B': {'p_eut': 0.5, 'q_eut': 0., 'pf': 1., 'vv': None, 'wv': None, 'q_fixed': None,
                              't_resp': None, 'vw': 'Default', 'fw': 'Default',
                              'pr_pl_pc': -0.5, 'qc': 0.5, 'ql': -0.5, 'qf': 1.},
                       '3B': {'p_eut': 0.9, 'q_eut': -0.44, 'pf': -0.90, 'vv': None, 'wv': None, 'q_fixed': None,
                              't_resp': None, 'vw': None, 'fw': 'LA',
                              'pr_pl_pc': -0.90, 'qc': 0.90, 'ql': -0.46, 'qf': 1.},
                       '4B': {'p_eut': 0.9, 'q_eut': 0.44, 'pf': 0.90, 'vv': None, 'wv': None, 'q_fixed': None,
                              't_resp': None, 'vw': None, 'fw': 'LA',
                              'pr_pl_pc': -0.90, 'qc': 0.46, 'ql': -0.90, 'qf': 1.},
                       '5B': {'p_eut': 1.0, 'q_eut': 0., 'pf': None, 'vv': 'MA', 'wv': None, 'q_fixed': None,
                              't_resp': 1., 'vw': 'MA', 'fw': 'MA',
                              'pr_pl_pc': -1., 'qc': 1., 'ql': -1., 'qf': 1.},
                       '6B': {'p_eut': 0.5, 'q_eut': 0., 'pf': None, 'vv': 'Default', 'wv': None, 'q_fixed': None,
                              't_resp': 10., 'vw': 'MA', 'fw': 'MA',
                              'pr_pl_pc': -0.5, 'qc': 0.5, 'ql': -0.5, 'qf': 1.},
                       '7B': {'p_eut': 0.5, 'q_eut': 0., 'pf': None, 'vv': None, 'wv': 'Default', 'q_fixed': None,
                              't_resp': None, 'vw': 'MA', 'fw': 'MA',
                              'pr_pl_pc': -0.5, 'qc': 0.5, 'ql': -0.5, 'qf': 1.},
                       '8B': {'p_eut': 0.93, 'q_eut': 0.176, 'pf': None, 'vv': None, 'wv': 'MA', 'q_fixed': None,
                              't_resp': None, 'vw': 'MA', 'fw': 'MA',
                              'pr_pl_pc': -0.93, 'qc': 0.754, 'ql': -0.93, 'qf': 1.},
                       '9B': {'p_eut': 0.5, 'q_eut': -0.44, 'pf': None, 'vv': None, 'wv': None, 'q_fixed': -0.44,
                              't_resp': None, 'vw': 'MA', 'fw': 'MA',
                              'pr_pl_pc': -0.9, 'qc': 0.5, 'ql': -0.06, 'qf': 1.},
                       '10B': {'p_eut': 0.5, 'q_eut': 0.44, 'pf': None, 'vv': None, 'wv': None, 'q_fixed': 0.44,
                               't_resp': None, 'vw': 'MA', 'fw': 'MA',
                               'pr_pl_pc': -0.5, 'qc': 0.06, 'ql': -0.5, 'qf': 1.},
                       }

        '''
        c) Establish a balanced load condition for each test case.
        
        Operate the EUT and adjust the RLC load components so that active, PS3, and reactive, QS3, power
        flow through each phase measured at switch S3 is less than 2% of the EUT rated power on a
        steady-state basis. Initial settings of the EUT and RLC load components for each test case are
        shown in Table 13 and Table 14. These settings are sufficient to get close to the balanced power
        requirement, and the EUT settings are not further adjusted. The RLC load components are then
        adjusted to achieve a balance between generation and load active and reactive powers such that the
        following two conditions are met:
                    ǀPS3ǀ = ǀPEUT + PR + PC + PLǀ <= 0.02 p.u.
                    ǀQS3ǀ = ǀQEUT + QR + QC + QLǀ <= 0.02 p.u.
        
        Multiphase voltages shall be balanced to within 5% of each other.
        
        AC test source voltage and/or frequency and EUT power may be adjusted to meet the power
        balance requirements so long as the resulting EUT power levels remain within 0.05 p.u. of the
        values in Table 13 or Table 14. The order in which adjustments are made is not specified in this
        procedure.
        '''

        for test_number in test_num:
            if cat == 'CAT_A':
                test = str(test_number) + 'A'
                test_params = cat_a_tests[test]
                q_rated = abs(test_params['q_eut'])
            else:
                test = str(test_number) + 'B'
                test_params = cat_b_tests[test]  # This is completed by the RT-Lab Code
                q_rated = abs(test_params['q_eut'])
                # p_rated = test_params['p_eut']

            if compilation == 'Yes':
                ts.sleep(1)
                ts.log("    Model ID: {}".format(phil.compile_model().get("modelId")))
            if stop_sim == 'Yes':
                ts.sleep(1)
                ts.log("    {}".format(phil.stop_simulation()))

            ts.log('Stop time set to %s' % phil.set_stop_time(phil.hil_stop_time))

            if load == 'Yes':
                ts.sleep(1)
                ts.log("    {}".format(phil.load_model_on_hil()))
            if execute == 'Yes':
                ts.log("    {}".format(phil.start_simulation()))
                daq.data_capture(True)  # Start RMS data capture
                daq.waveform_config()


            # setting up the eut

            # if eut is not None:
            #     if test_params['pf'] is not None:
            #         if test_params['pf'] < 0:
            #             eut.set_const_pf({
            #                 'const_pf_mode_enable': True,
            #                 'const_pf_excitation' : 'inj',
            #                 'const_pf_inj' : test_params['pf']
            #             })
            #         else:
            #             eut.set_const_pf({
            #                 'const_pf_mode_enable': True,
            #                 'const_pf_excitation': 'abs',
            #                 'const_pf_abs': test_params['pf']
            #             })
            #     if test_params['vv'] is not None:
            #         if test_params['VV'] == 'Default':
            #             eut.set_qv({
            #                 'qv_mode_enable': True,
            #                 'qv_curve_v_pts': [0.92, 0.98, 1.02, 1.08],
            #                 'qv_curve_q_pts': [0.44, 0.0, 0.0, -0.44],
            #                 'qv_olrt': test_params['t_resp']
            #             })
            #         elif test_params['VV'] == 'Default':
            #             eut.set_qv({
            #                 'qv_mode_enable': True,
            #                 'qv_curve_v_pts': [0.98, 1.0, 1.0, 1.02],
            #                 'qv_curve_q_pts': [0.44, 0.0, 0.0, -0.44],
            #                 'qv_olrt': test_params['t_resp']
            #             })
            #     if test_params['wv'] is not None:
            #         if test_params['Default']:
            #             eut.set_qp({
            #                 'qp_mode_enable': True,
            #                 'qp_curve_p_gen_pts': [0.2, 0.5, 1.0],
            #                 'qp_curve_q_gen_pts': [0.0, 0.0, -0.44],
            #             })
            #         elif test_params['MA']:
            #             eut.set_qp({
            #                 'qp_mode_enable': True,
            #                 'qp_curve_p_gen_pts': [0.2, 0.9, 1.0],
            #                 'qp_curve_q_gen_pts': [0.44, 0.44, -0.44],
            #             })
            #     if test_params['q_fixed'] is not None:
            #         eut.set_const_q({
            #
            #         })
            #
            #     if test_params['vw'] is not None:
            #
            #     if test_params['fw'] is not None:


            # Set test number to initialize the RLC parameter based on Table 12 or 13 - done with test num update
            ctrl_sigs = phil.get_control_signals(details=False)
            # ts.log_debug('Control signals on load: %s' % str(ctrl_sigs))
            ctrl_sigs[0] = float(test_number)  # test num
            ctrl_sigs[4] = v_ll  # set line-line voltage
            ctrl_sigs[5] = s_rated  # set EUT apparent power
            ctrl_sigs[7] = 0  # degrees, must be determined beforehand
            ctrl_sigs[17] = 100  # cap pot
            ctrl_sigs[8] = 100  # r pot
            ts.log_debug('ctrl_sigs: %s' % ctrl_sigs)
            energize_system(ctrl_sigs, phil, daq, eut_startup_time, p_rated, pv, s_rated)

            '''
            Set the grid support functions before verifying the RLC tuning
            '''
            p_rated = test_params['p_eut'] * p_rated
            if pv is not None:
                pv.power_set(1.00 * p_rated, irradiance=1000)
                pv.power_on()
                ts.sleep(0.5)
                ts.log('Setting PV power to %0.2f W' % p_rated)
            set_grid_support_functions(eut, cat, cat2, test_params)

            # get PS3 and QS3
            daq.data_sample()
            meas = daq.data_read()
            # ts.log_debug(pprint.pformat(meas))
            ps3_pu = meas['AC_P_S3_PU']
            qs3_pu = meas['AC_Q_S3_PU']

            v_out_of_band = True
            # tune RLC to get target P/Q levels through switch 3
            c = 0
            while not(-0.02 < ps3_pu < 0.02) or not(-0.02 < qs3_pu < 0.02) or v_out_of_band:
                # calculations to determine RLC adjustments
                daq.data_sample()
                meas = daq.data_read()
                p_load = meas['AC_P_LOAD']
                q_load = meas['AC_Q_LOAD']
                p_utility = meas['AC_SOURCE_P']
                q_utility = meas['AC_SOURCE_Q']

                # Adjust
                ctrl_sigs = phil.get_control_signals()
                ts.log_debug('ctrl_sigs: %s' % ctrl_sigs)
                r_set = ctrl_sigs[8]
                l_set = ctrl_sigs[14]
                c_set = ctrl_sigs[17]
                ts.log_debug('Prior p_load = %s W, q_load = %s var, p_utility = %s W, q_utility = %s var, '
                             'RLC = [%s, %s, %s]%%' % (p_load, q_load, p_utility, q_utility,
                                                                r_set, l_set, c_set))
                ts.log_debug('Prior p_load = %0.3f W, q_load = %0.3f var, p_utility = %0.3f W, q_utility = %0.3f var, '
                             'RLC = [%0.3f, %0.3f, %0.3f]%%' % (p_load, q_load, p_utility, q_utility,
                                                                r_set, l_set, c_set))

                r, l, c = find_rlc(p_utility, q_utility, r_set, l_set, c_set)
                # ts.log('Setting R to change %0.3f%%, L to change %0.3f%%, C to change %0.3f%%' % (r, l, c))
                ctrl_sigs[8] = r  # Resistors Pot
                ctrl_sigs[14] = l  # Inductor Pot
                ctrl_sigs[17] = c  # Capacitor Pot
                phil.set_control_signals(values=ctrl_sigs)

                ts.sleep(5)  # wait to see how changes affect P/Q
                daq.data_sample()
                meas = daq.data_read()
                ps3_pu = meas['AC_P_S3_PU']
                qs3_pu = meas['AC_Q_S3_PU']
                p_load = meas['AC_P_LOAD']
                q_load = meas['AC_Q_LOAD']
                p_utility = meas['AC_SOURCE_P']
                q_utility = meas['AC_SOURCE_Q']
                v1 = meas['AC_VRMS_1']/v_nom
                v2 = meas['AC_VRMS_2']/v_nom
                v3 = meas['AC_VRMS_3']/v_nom
                ts.log_debug('New p_load = %0.3f W, q_load = %0.3f var, p_utility = %0.3f W, q_utility = %0.3f var, '
                             'RLC = [%0.3f, %0.3f, %0.3f]%%' % (p_load, q_load, p_utility, q_utility, r, l, c))
                ts.log('After changes to RLC, the S3 P = %0.4f pu and Q = %0.4f pu.' % (ps3_pu, qs3_pu))

                # Verify the voltage are within 5% of each other
                v_delta = [abs(v1-v2), abs(v2-v3), abs(v1-v3)]
                if v_delta[0] > 0.05 or v_delta[1] > 0.05 or v_delta[2] > 0.5:
                    ts.log('Voltages are out of band: V1-V2 = %0.4f V2-V3 = %0.4f V1-V3 = %0.4f' %
                           (v_delta[0], v_delta[1], v_delta[2]))
                    v_out_of_band = True
                else:
                    ts.log('Voltages are in band: V1-V2 = %0.4f V2-V3 = %0.4f V1-V3 = %0.4f' %
                           (v_delta[0], v_delta[1], v_delta[2]))
                    v_out_of_band = False

                ts.log_debug('WHILE LOOP LOGIC: not(-0.02 < ps3_pu < 0.02) = %s' % (not(-0.02 < ps3_pu < 0.02)))
                ts.log_debug('WHILE LOOP LOGIC: not(-0.02 < qs3_pu < 0.02) = %s' % (not(-0.02 < qs3_pu < 0.02)))
                ts.log_debug('WHILE LOOP LOGIC: v_out_of_band = %s' % (v_out_of_band))

            ts.log_debug('\t\t TARGET \t Value')
            ts.log_debug('EUT P \t\t %0.5f \t\t %0.5f' % (test_params['p_eut'], meas['AC_P']/p_rated))
            ts.log_debug('EUT Q \t\t %0.5f \t\t %0.5f' % (test_params['q_eut'], meas['AC_Q']/p_rated))
            ts.log_debug('PR+PL+PC \t %0.5f \t\t %0.5f' % (test_params['pr_pl_pc'], meas['AC_P_LOAD_PU']))
            ts.log_debug('QC \t\t %0.5f \t\t %0.5f' % (test_params['qc'], meas['QC']))
            ts.log_debug('QL \t\t %0.5f \t\t %0.5f' % (test_params['ql'], meas['QL']))
            ts.log_debug('QF \t\t %0.5f \t\t %0.5f' % (test_params['qf'], meas['QUALITY_FACTOR']))

            '''
            d) Verify the test setup can sustain an island.
            
            1) Disable the unintentional islanding protection in the EUT.
            '''
            ts.log(15 * '-' + 'STEP D: VERIFY TEST SETUP CAN ISLAND' + 15 * '-')
            ts.log('This EUT supports the following Unintentional Islanding modes: %s' %
                   eut.get_ui()['ui_capability_er'])
            ts.log('Step d)1): Disabling the UI on EUT')
            eut.set_ui(params={'ui_mode_enable': 0.0})

            '''
            2) Operate the EUT and RLC load under the conditions established in step c) for any one of the
            test cases in Table 13 or Table 14 as appropriate for the EUT Category.
            
            3) With the EUT and load operating at stable conditions, record the voltage and current at switch
            S3. Record the active and reactive power at switch S3, switch S2, the resistive load, the
            capacitive load and the inductive load on a net and per phase basis.
            '''
            ts.sleep(2.)
            ts.log('Step d)3): Recording power measurements at switches and loads.')
            daq.data_sample()
            meas = daq.data_read()
            print_measurements(meas)

            '''
            4) Open switch S3. If, after 10 s, the island circuit remains energized, the test setup is considered
            verified. Measure and record the voltage and frequency of the islanding operation.
            '''
            UI_data_counter = 0
            ctrl_sigs = phil.get_control_signals()
            ts.log('Step d)4): Opening switch S3 to verify the EUT will island for 10 seconds.')
            ctrl_sigs[2] = 1  # open S3 switch (for islanding test execution)
            daq.waveform_record()
            phil.set_control_signals(values=ctrl_sigs)
            UI_data_counter += 1
            UI_data_mapping = {UI_data_counter: f'd4_pretest_q_{1.0}'}
            start = time.time()
            end = start + 10
            ts.log('Step d)4): Measuring voltage and frequency of the island.')
            while time.time() < end:
                daq.data_sample()
                meas = daq.data_read()
                ts.log('\tVoltage = [%0.2f, %0.2f, %0.2f] and frequency = [%0.3f, %0.3f, %0.3f] of island at EUT' %
                       (meas['AC_VRMS_1'], meas['AC_VRMS_2'], meas['AC_VRMS_3'],
                        meas['AC_FREQ_PCC'], meas['AC_FREQ_PCC'], meas['AC_FREQ_PCC']))
                ts.log('\tIslanded for %s seconds' % (time.time() - start))
            daq.waveform_stop_record()
            '''
            5) De-energize the island.
            '''
            ts.log('Step d)5): De-energizing the island.')
            # ctrl_sigs[3] = 1.  # de-energize amplifier
            phil.set_control_signals(values=ctrl_sigs)
            # phil.stop_simulation()

            '''
            6) Enable the unintentional islanding protection in the EUT.
            '''
            # phil.start_simulation()
            # ts.sleep(10)
            ts.log('Step d)6): Enable the unintentional islanding protection in the EUT.')
            eut.set_ui(params={'ui_mode_enable': 1.0})
            ts.log('EUT settings: %s' % eut.get_ui())

            '''
            e) Clearing time tests.
            
            1) Operate the EUT and load under the conditions established in step c) for each one of the test
            cases in Table 13 or Table 14 as appropriate for the EUT Category.
            '''
            ts.log(15*'-' + 'STEP E: CLEARING TIME TESTS' + 15*'-')
            ts.log('Step e)1): Running test cases from Table 13 or 14.')
            energize_system(ctrl_sigs, phil, daq, eut_startup_time, p_rated, pv, s_rated)

            '''
            e)4) The test is to be repeated with the reactive load (either capacitive or inductive) adjusted in 1%
            increments from 95% to 105% of the initial balanced load value determined in step c). 
            '''
            # This requires clearing times be calculated while the script is running.  It is suggested that this
            # be completed with logic in the RT-Lab simulation

            ts.sleep(2.)  # wait
            # ctrl_sigs[2] = 1.  # open S3
            # phil.set_control_signals(values=ctrl_sigs)

            counter = 0
            high_freq_count = 0
            low_freq_count = 0
            t_trips = {}
            for q_inc in [1.0, 0.99, 0.98, 0.97, 0.96, 0.95, 1.01, 1.02, 1.03, 1.04, 1.05]:
                ts.log('Running step e)4) with reactive power setpoint = %0.3f' % q_inc)
                counter += 1
                t_trips, t_trip, high_freq_count, low_freq_count = \
                    run_ui_test(phil, model_name, daq, test_num, t_trips, q_inc, high_freq_count,
                                low_freq_count, result_summary, c, s_rated, q_rated, test_params['qc'])
                UI_data_counter += 1
                UI_data_mapping[UI_data_counter] = f'e4_test_q_{q_inc}'

                ''' 
                e)4) If clearing times are still increasing at the 95% or 105% points, additional 1% increments 
                shall be taken until clearing times begin decreasing.
                '''
                min_unreached = True
                q_min = 0.95

                while min_unreached:
                    if q_inc == q_min or (0.75 <= q_min < 0.95):
                        if t_trip > t_trips[round(q_min+0.01, 2)]:  # must run a lower q_inc test
                            # ctrl_sigs[3] = 1.  # de-energize amplifier
                            phil.set_control_signals(values=ctrl_sigs)
                            # re-energize system and wait for EUT to start for next q_inc
                            energize_system(ctrl_sigs, phil, daq, eut_startup_time, p_rated, pv, s_rated)
                            counter += 1
                            t_trips, t_trip, high_freq_count, low_freq_count = \
                                run_ui_test(phil, model_name, daq, test_num, t_trips, q_min, high_freq_count,
                                            low_freq_count, result_summary, c, s_rated, q_rated, test_params['qc'])
                            UI_data_counter += 1
                            UI_data_mapping[UI_data_counter] = f'e4_test_dec_q_{q_inc}'
                            if t_trip < t_trips[round(q_min, 2)]:
                                min_unreached = False
                            else:
                                q_min -= 0.01
                        else:
                            ts.log(f'Trip times might be equal ({str(t_trip == t_trips[round(q_min+0.01, 2)])}) or '
                                   f'reactive power min lim was reached ({q_min} pu)')
                            break
                    else:
                        break

                max_unreached = True
                q_max = 1.05
                while max_unreached:
                    if q_inc == q_max or (1.05 < q_max <= 1.25):
                        if t_trip > t_trips[round(q_max-0.01, 2)]:  # must run a lower q_inc test
                            # ctrl_sigs[3] = 1.  # de-energize amplifier
                            phil.set_control_signals(values=ctrl_sigs)
                            # re-energize system and wait for EUT to start for next q_inc
                            energize_system(ctrl_sigs, phil, daq, eut_startup_time, p_rated, pv, s_rated)
                            counter += 1
                            t_trips, t_trip, high_freq_count, low_freq_count = \
                                run_ui_test(phil, model_name, daq, test_num, t_trips, q_max, high_freq_count,
                                            low_freq_count, result_summary, c, s_rated, q_rated, test_params['qc'])
                            UI_data_counter += 1
                            UI_data_mapping[UI_data_counter] = f'e4_test_inc_q_{q_inc}'
                            if t_trip < t_trips[round(q_max, 2)]:
                                max_unreached = False
                            else:
                                q_max += 0.01
                        else:
                            ts.log(f'Trip times might be equal ({str(t_trip == t_trips[round(q_min + 0.01, 2)])}) or '
                                   f'reactive power max lim was reached ({q_max} pu)')
                            break
                    else:
                        break

                # ctrl_sigs[3] = 1.  # de-energize amplifier
                phil.set_control_signals(values=ctrl_sigs)
                # re-energize system and wait for EUT to start for next q_inc
                energize_system(ctrl_sigs, phil, daq, eut_startup_time, p_rated, pv, s_rated)

            '''
            5) After reviewing the results of the previous step, the 1% setting increments that yielded the
            three longest clearing times shall be subjected to two additional test iterations. If the three
            longest clearing times occur at nonconsecutive 1% load setting increments, the additional two
            iterations shall be run for all load settings in between.
            '''
            t_trips_sorted = [(q, t) for q, t in sorted(t_trips.items(), key=lambda item: item[1])]
            trips_repeats = t_trips_sorted[-3:]
            trips_repeats.sort(key=lambda x: x[0])
            q_repeats = [int(round(100 * (trip[0] - 1))) for trip in trips_repeats]
            cons_bool = sorted(q_repeats) == list(range(min(q_repeats), max(q_repeats)+1))
            if cons_bool is False:
                q_repeats = list(range(min(q_repeats), max(q_repeats)+1))

            for q_inc in q_repeats:
                q_inc = (q_inc/100)+1
                #first iteration
                counter += 1
                t_trips, t_trip, high_freq_count, low_freq_count = \
                    run_ui_test(phil, model_name, daq, test_num, t_trips, q_inc, high_freq_count,
                                low_freq_count, result_summary, c, s_rated, q_rated, test_params['qc'])
                UI_data_counter += 1
                UI_data_mapping[UI_data_counter] = f'e5_retest_q_{q_inc}_1'
                # ctrl_sigs[3] = 1.  # de-energize amplifier
                phil.set_control_signals(values=ctrl_sigs)
                # re-energize system and wait for EUT to start for next q_inc
                energize_system(ctrl_sigs, phil, daq, eut_startup_time, p_rated, pv, s_rated)

                # second iteration
                counter += 1
                t_trips, t_trip, high_freq_count, low_freq_count = \
                    run_ui_test(phil, model_name, daq, test_num, t_trips, q_inc, high_freq_count,
                                low_freq_count, result_summary, c, s_rated, q_rated, test_params['qc'])
                UI_data_counter += 1
                UI_data_mapping[UI_data_counter] = f'e5_retest_q_{q_inc}_2'
                # ctrl_sigs[3] = 1.  # de-energize amplifier
                phil.set_control_signals(values=ctrl_sigs)
                # re-energize system and wait for EUT to start for next q_inc
                energize_system(ctrl_sigs, phil, daq, eut_startup_time, p_rated, pv, s_rated)

            daq.data_capture(False)




            ts.log(f"Matlab waveform UI_data file order:{UI_data_mapping}")
            ts.log('Sampling RMS complete')
            rms_dataset_filename = str(test_num) + "_RMS.csv"
            ds = daq.data_capture_dataset()
            ts.log('Saving file: %s' % rms_dataset_filename)
            ds.to_csv(ts.result_file_path(rms_dataset_filename))
            # lib_1547 = p1547.module_1547(ts=ts, aif='VV', imbalance_angle_fix=imbalance_fix)
            # ts.log_debug('1547.1 Library configured for %s' % lib_1547.get_test_name())
            result_params = {
                'plot.title': rms_dataset_filename.split('.csv')[0],
                'plot.x.title': 'Time (sec)',
                'plot.x.points': 'TIME',
                'plot.y.points': 'AC_V_1',  # 'AC_V_2', 'AC_V_3',
                'plot.y.title': 'Voltage (V)',
                'plot.y2.points': 'AC_I_1',  # 'AC_I_2', 'AC_I_3',
                'plot.y2.title': 'Current (A)',
                # 'plot.%s_TARGET.min_error' % y: '%s_TARGET_MIN' % y,
                # 'plot.%s_TARGET.max_error' % y: '%s_TARGET_MAX' % y,
                }
            ts.result_file(rms_dataset_filename, params=result_params)

        result = script.RESULT_COMPLETE

    except script.ScriptFail as e:
        reason = str(e)
        if reason:
            ts.log_error(reason)
    finally:
        if phil is not None:
            if phil.model_state() == 'Model Running':
                if daq is not None:
                    daq.device.close()
                phil.stop_simulation()
            phil.close()
            if 'UI_data_mapping' in locals() or 'UI_data_mapping' in globals():
                daq.waveform_capture_dataset(UI_data_counter, UI_data_mapping)
        if daq is not None:
            daq.close()
        if pv is not None:
            pv.close()
        if eut is not None:
            eut.close()
        # if dataset_filename is not None and ds is not None and result_params is not None:
        #     ts.log('Saving file: %s' % dataset_filename)
        #     ds.to_csv(ts.result_file_path(dataset_filename))
        #     ts.result_file(dataset_filename, params=result_params)
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

        ts.svp_version(required='1.5.9')

        result = test_run()

        ts.result(result)
        if result == script.RESULT_FAIL:
            rc = 1

    except Exception as e:
        ts.log_error('Test script exception: %s' % traceback.format_exc())
        rc = 1

    sys.exit(rc)


info = script.ScriptInfo(name=os.path.basename(__file__), run=run, version='1.0.0')
# Data acquisition
info.param_group('hil_config', label='HIL Configuration')
info.param('hil_config.open', label='Open Project?', default="Yes", values=["Yes", "No"])
info.param('hil_config.compile', label='Compilation needed?', default="Yes", values=["Yes", "No"])
info.param('hil_config.stop_sim', label='Stop the simulation before loading/execution?',
           default="Yes", values=["Yes", "No"])
info.param('hil_config.load', label='Load the model to target?', default="Yes", values=["Yes", "No"])
info.param('hil_config.execute', label='Execute the model on target?', default="Yes", values=["Yes", "No"])
info.param('hil_config.model_name', label='Model Name', default="Phase_Jump_A_B_A")

info.param_group('ui', label='IEEE 1547.1 unintentionnal islanding Configuration')
info.param('ui.test_num', label='Comma-seperated Test Numbers (1-10)', default='1,2,3,4')
info.param('ui.n_iter', label='Number of Iterations', default=5)
info.param('ui.phase_comp', label='Phase compensation(deg)', default=0.)
info.param('ui.transducer_gain', label='PHIL transducer gain', default=43.1)

info.param_group('ui_startup', label='IEEE 1547.1 Unintentionnal islanding Startup Time', glob=True)
info.param('ui_startup.eut_startup_time', label='EUT Startup Time (s)', default=85, glob=True)

info.param_group('eut', label='EUT Parameters', glob=True)
info.param('eut.phases', label='Phases', default='Single Phase', values=['Single phase', 'Split phase', 'Three phase'])
info.param('eut.cat', label='Alphabetic Category', default='CAT_A', values=['CAT_A', 'CAT_B'])
info.param('eut.cat2', label='Numeric Category', default='CAT_I', values=['CAT_I', 'CAT_II', 'CAT_III'])
info.param('eut.f_nom', label='Nominal frequency (Hz)', default=60.0)
info.param('eut.s_rated', label='Apparent power rating (VA)', default=24000.0)
info.param('eut.v_ll', label='Line-to-line EUT voltage (V)', default=480.)
info.param('eut.v_nom', label='Line-to-neutral EUT voltage (V)', default=277.2)
# info.param('eut.p_rated', label='Output power rating (W)', default=8000.0)
# info.param('eut.p_min', label='Minimum Power Rating(W)', default=1000.)
# info.param('eut.var_rated', label='Output var rating (vars)', default=2000.0)

hil.params(info)
das.params(info)
pvsim.params(info)
der1547.params(info)


def script_info():
    
    return info


if __name__ == "__main__":

    # stand alone invocation
    config_file = None
    if len(sys.argv) > 1:
        config_file = sys.argv[1]

    params = None

    test_script = script.Script(info=script_info(), config_file=config_file, params=params)
    test_script.log('log it')

    run(test_script)



