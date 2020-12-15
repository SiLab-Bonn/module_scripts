import os
import time
import logging
import yaml

from slack import WebClient
from basil.dut import Dut

from bdaq53.system.periphery import BDAQ53Periphery
from bdaq53.scans.scan_analog import AnalogScan
from bdaq53.scans.tune_global_threshold import GDACTuning
from bdaq53.scans.scan_disconnected_bumps_threshold import BumpConnThrShScan

LOGFILE = 'thermocycling_connectivity.log'
OUTFILE_TEMPS = 'thermocycling_connectivity_temps.dat'

T_MIN = -40         # Minimum temperature
T_MAX = 60          # Maximum temperature
WAIT_TIME = 2 * 60  # Wait time at target temperature

CYCLE_START = 1

TESTBENCH = '/home/silab/git/bdaq53/bdaq53/testbench.yaml'

scan_configuration = {
    'start_column': 0,
    'stop_column': 400,
    'start_row': 0,
    'stop_row': 192,

    # Start threshold scan at injection setting where a fraction of min_response of the selected
    # pixels see the fraction of hits min_hits
    'min_response': 0.001,
    'min_hits': 0.05,
    # Stop threshold scan at injection setting where a fraction of max_response of the selected
    # pixels see the fraction of hits max_hits
    'max_response': 0.995,
    'max_hits': 0.95,

    'n_injections': 100,

    'VCAL_MED': 200,
    'VCAL_HIGH_start': 200,         # Start value of injection
    'VCAL_HIGH_stop': 4095,         # Maximum injection, can be None
    'VCAL_HIGH_step_fine': 50,      # Step size during threshold scan
    'VCAL_HIGH_step_coarse': 100,    # Step when seaching start

    'bias_voltage_forward': +1,     # Be careful!
    'bias_voltage_reverse': -50,
    'bias_current_limit': 10e-6,

    'maskfile': None,
}

tuning_configuration = {
    'maskfile': None,
    'use_default_chip_configuration': True
}

tuning_configuration_sync = {
    'VCAL_MED': 500,
    'VCAL_HIGH': 1100,

    'chip': {'registers': {'IBIASP1_SYNC': 38,
                           'IBIASP2_SYNC': 10,
                           'IBIAS_SF_SYNC': 100
                           }
             }
}

tuning_configuration_lin_diff = {
    'VCAL_MED': 500,
    'VCAL_HIGH': 1500,

    'chip': {'registers': {'PA_IN_BIAS_LIN': 30,
                           'LDAC_LIN': 50,
                           'PRMP_DIFF': 20,
                           }
             }
}

# Logging setup
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
fmt = '%(asctime)s - %(levelname)-7s %(message)s'
logging.basicConfig(format=fmt, filename=LOGFILE, filemode='w', level=logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter(fmt))
sh.setLevel(logging.DEBUG)
logging.root.addHandler(sh)

def notify(message):
    global bench

    with open(os.path.expanduser(bench['notifications']['slack_token']), 'r') as token_file:
        token = token_file.read().strip()

    try:
        slack = WebClient(token)
        for user in bench['notifications']['slack_users']:
            slack.chat_postMessage(channel=user, text=message, username='BDAQ53 Bot', icon_emoji=':robot_face:')
    except Exception as e:
        logging.error('Notification error: {0}'.format(e))

def acquire_temperatures():
    global dut

    t_chamber = dut['Climatechamber'].get_temperature()
    setpoint = dut['Climatechamber'].get_temperature_setpoint()
    t_sens = dut['Thermohygrometer'].get_temperature(channel=0)
    h_sens = dut['Thermohygrometer'].get_humidity(channel=0)
    t_mod = dut['Thermohygrometer'].get_temperature(channel=1)
    h_mod = dut['Thermohygrometer'].get_humidity(channel=1)
    t_air = dut['Thermohygrometer'].get_temperature(channel=3)
    h_air = dut['Thermohygrometer'].get_humidity(channel=3)

    try:
        logging.debug('T_ch = {0:1.2f}, T_sns = {1:1.2f}, Hum_sns = {2:1.2f}, T_mod = {3:1.2f}, H_mod = {4:1.2f}, T_air = {5:1.2f}, H_air = {6:1.2f}'.format(t_chamber, t_sens, h_sens, t_mod, h_mod, t_air, h_air))
        with open(OUTFILE_TEMPS, 'a') as f:
            f.write('{0}, {1}, {2:1.2f}, {3:1.2f}, {4:1.2f}, {5:1.2f}, {6:1.2f}, {7:1.2f}, {8:1.2f}\n'.format(time.time(), setpoint, t_chamber, t_sens, h_sens, t_mod, h_mod, t_air, h_air))
    except TypeError:
        logging.debug('T_ch = {0:1.2f}, T_sns = {1}, H_sns = {2}, T_mod = {3}, H_mod = {4}, T_air = {5}, Hum_air = {6}'.format(t_chamber, t_sens, h_sens, t_mod, h_mod, t_air, h_air))
        with open(OUTFILE_TEMPS, 'a') as f:
            f.write('{0}, {1}, {2:1.2f}, {3}, {4}, {5}, {6}, {7}, {8}\n'.format(time.time(), setpoint, t_chamber, t_sens, h_sens, t_mod, h_mod, t_air, h_air))

    return t_chamber, t_sens, h_sens, t_mod, h_mod, t_air, h_air

def go_to_temperature(target, wait_time=0, overshoot=False, accuracy=1, timeout=30*60):
    global dut

    if overshoot:
        if target > 0:
            set_target = target + 5
        else:
            set_target = target - 10
    else:
        set_target = target

    dut['Climatechamber'].set_temperature(set_target)
    timestamp_start = time.time()
    while True:
        _, t_sens, _, _, _, _, h_air = acquire_temperatures()
        # TODO interlock on air humidity?
        if t_sens is not None and t_sens > (target - accuracy) and t_sens < (target + accuracy):
            logging.info('Target temperature reached on device!')
            break
        if time.time() - timestamp_start > timeout:
            raise RuntimeError('Target temperature could not be reached within specified timeout!')

    dut['Climatechamber'].set_temperature(target)
    if wait_time > 0:
        logging.info('Waiting for {0:1.0f}s at {1}°C...'.format(wait_time, target))
        timestamp_start = time.time()
        while True:
            _, t_sens, _, _, _, _, h_air = acquire_temperatures()
            # TODO interlock on air humidity?
            if t_sens is not None and (t_sens < (target - accuracy) or t_sens > (target + accuracy)):
                logging.warning('Temperature on device deviated too much: Target = {0}, T_sens = {1:1.2f}'.format(target, t_sens))
            if time.time() - timestamp_start > wait_time:
                logging.info('Wait time over. Continuing...')
                break

if __name__ == '__main__':
    with open(TESTBENCH) as f:
        bench = yaml.safe_load(f)

    if not os.path.isfile(OUTFILE_TEMPS):
        # Reset data file
        with open(OUTFILE_TEMPS, 'w') as f:
            f.write('#Timestamp, T_setpoint, T_chamber, T_sens, Hum_sens, T_mod, Hum_mod, T_air, Hum_air\n')

    dut = Dut('thermocycling.yaml')
    dut.init()

    logging.info('Starting run, setting start temperature to 20C...')
    dut['Climatechamber'].start_manual_mode()
    dut['Climatechamber'].set_air_dryer(True) # make sure air dryer is running to avoid condensation
    go_to_temperature(20, wait_time=3*60*60)  # wait 3h at 20°C to make sure the air is dry

    # Make sure chip is powered off before starting cycle
    periphery = BDAQ53Periphery()
    periphery.init()
    periphery.power_off_module(next(iter(bench['modules'])))
    periphery.close()

    total_time_start = time.time()
    try:
        cycle = CYCLE_START
        while True:
            logging.info('Starting cycle {}'.format(cycle))
            notify('Starting cycle {}'.format(cycle))
            logging.info('Cooling to {}'.format(T_MIN))
            go_to_temperature(T_MIN, wait_time=WAIT_TIME, overshoot=True)
            logging.info('Heating to {}'.format(T_MAX))
            go_to_temperature(T_MAX, wait_time=WAIT_TIME, overshoot=True)
            logging.info('Resetting temperature to 20C')
            go_to_temperature(20, wait_time=15*60)

            logging.info('Starting bump connectivity scans for cycle {}...'.format(cycle))
            notify('Starting bump connectivity scans for cycle {}...'.format(cycle))
            try:
                with AnalogScan(scan_config={'use_default_chip_configuration': True}) as scan:
                    scan.start()

                tuning_configuration['start_column'] = scan_configuration['start_column']
                tuning_configuration['stop_column'] = scan_configuration['stop_column']
                tuning_configuration['start_row'] = scan_configuration['start_row']
                tuning_configuration['stop_row'] = scan_configuration['stop_row']

                for key in tuning_configuration:
                    tuning_configuration_sync[key] = tuning_configuration[key]
                    tuning_configuration_lin_diff[key] = tuning_configuration[key]

                if tuning_configuration_sync['stop_column'] > 128:
                    tuning_configuration_sync['stop_column'] = 128
                if tuning_configuration_sync['start_column'] < 128:
                    with GDACTuning(scan_config=tuning_configuration_sync) as global_tuning:
                        global_tuning.start()
                    tuning_configuration_lin_diff['use_default_chip_configuration'] = False

                if tuning_configuration_lin_diff['start_column'] < 128:
                    tuning_configuration_lin_diff['start_column'] = 128
                if tuning_configuration_lin_diff['stop_column'] > 128:
                    with GDACTuning(scan_config=tuning_configuration_lin_diff) as global_tuning:
                        global_tuning.start()

                with BumpConnThrShScan(scan_config=scan_configuration) as disconn_bumps_scan:
                    disconn_bumps_scan.start()
            except RuntimeError:
                logging.error('Bump connectivity scan failed for cycle {}!'.format(cycle))
                notify('ERROR: Bump connectivity scan failed for cycle {}!'.format(cycle))
                break
            finally:
                periphery = BDAQ53Periphery()
                periphery.init()
                periphery.power_off_module(next(iter(bench['modules'])))
                periphery.close()

            cycle += 1
    except KeyboardInterrupt:
        logging.error('Scan stopped manually!')
    finally:
        logging.info('Closing up. Setting temperature to 20°C.')
        dut['Climatechamber'].set_temperature(20)

    go_to_temperature(20)
    total_time = time.time() - total_time_start
    logging.info('Completed {0} cycles in {1:1.2f}h'.format(cycle, total_time / 3600))
    dut['Climatechamber'].stop_manual_mode()
