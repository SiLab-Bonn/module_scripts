import time
import logging
import numpy as np
import os

from basil.dut import Dut
from slack import WebClient

time_str = time.strftime('%Y%m%d_%H%M%S_')
FILEPATH = os.path.dirname(os.path.abspath(__file__))
OUTPATH = os.path.join(FILEPATH, 'output_data')
if not os.path.exists(OUTPATH):
    os.makedirs(OUTPATH)

PERIPHERYFILE = os.path.join(FILEPATH, 'thermocycling_QC.yaml')
LOGFILE = os.path.join(OUTPATH, time_str + 'thermocycling.log')
OUTFILE_TEMPS = os.path.join(OUTPATH, time_str + 'thermocycling_temps.dat')

cycles = np.array([
    (2, (-45, 40), 2 * 60),
    (1, (-55, 60), 2 * 60)
], dtype=[('n_cycles', 'i'), ('temps', 'O'), ('wait_time', 'f')])

starting_temperature = 20
starting_dew_point = -25
minimal_starting_time = 1 * 60 * 60
maximal_starting_time = 3 * 60 * 60
save_data_on_startup = True

t_sens = 't_mod2'  # temperature sensor which has reach set temperature
air_sens = ['air2', 'sens', 'chamber']  # sensors (without t_/h_) measuring air temperature (used to calculate dew point)
mod_sens = ['mod', 'mod2']  # sensors (without t_/h_) that measure temps of modules (used for interlocking)
interlock_dp = 'dew_point'  # name of the value which stores the dew point used for interlocking
min_interlock_distance = 5  # how much the interlock dew point must be under lowest module temperature

notify_on_slack = False
slack_token = "~/slack_api_token"
slack_users = []


def setup_sensors():
    return np.array([
        ('t_chamber', 't_ch', dut['Climatechamber'].get_temperature, {}),
        ('t_setp', 't_sp', dut['Climatechamber'].get_temperature_setpoint, {}),
        ('t_sens', 't_s', dut['Thermohygrometer2'].get_temperature, {}),
        ('t_mod', 't_m', dut['Thermohygrometer'].get_temperature, {'channel': 2}),
        ('t_air', 't_a', dut['Thermohygrometer'].get_temperature, {'channel': 3}),
        ('t_mod2', 't_o', dut['Thermohygrometer'].get_temperature, {'channel': 0}),
        ('t_air2', 't_t', dut['Thermohygrometer3'].get_temperature, {}),
        ('h_sens', 'h_s', dut['Thermohygrometer2'].get_humidity, {}),
        ('h_mod', 'h_m', dut['Thermohygrometer'].get_humidity, {'channel': 2}),
        ('h_air', 'h_a', dut['Thermohygrometer'].get_humidity, {'channel': 3}),
        ('h_mod2', 'h_m2', dut['Thermohygrometer'].get_humidity, {'channel': 0}),
        ('h_air2', 'h_a2', dut['Thermohygrometer3'].get_humidity, {}),
        ('d_sens', None, dut['Thermohygrometer2'].get_dew_point, {}),
        ('d_mod', None, dut['Thermohygrometer'].get_dew_point, {'channel': 2}),
        ('d_air', None, dut['Thermohygrometer'].get_dew_point, {'channel': 3}),
        ('d_mod2', None, dut['Thermohygrometer'].get_dew_point, {'channel': 0}),
        ('d_air2', None, dut['Thermohygrometer3'].get_dew_point, {}),
        (interlock_dp, 'dp', lambda: None, {})  # has to be change afterwards
    ], dtype=[('name', 'U50'), ('short', 'U50'), ('f', 'O'), ('kwargs', 'O')])
    # short names are used in log file (when None, it does not get printed there)


# Logging setup
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
fmt = '%(asctime)s - %(levelname)-7s %(message)s'
logging.basicConfig(format=fmt, filename=LOGFILE, filemode='w', level=logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter(fmt))
logging.root.addHandler(sh)


def acquire_temperatures(save_data=True):
    temperatures = {s['name']: s['f'](**s['kwargs']) for s in sensors}
    temperatures[interlock_dp] = get_dew_point(temperatures)

    if save_data:
        logging.info(", ".join([f'{key.capitalize()} = {value:1.2f}' if value is not None else f'{key.capitalize()} = None'
                                for key, value in zip(sensors['short'], temperatures.values()) if key != 'None']))
        with open(OUTFILE_TEMPS, 'a') as f:
            f.write('{0}, '.format(time.time())
                    + ', '.join([f'{value:1.2f}' if value is not None else 'None'
                                 for value in temperatures.values()])
                    + '\n')

    return temperatures


def get_temps(values, sensors):
    return [v for k, v in values.items() if k.startswith('t') and any(k.endswith(s) for s in sensors) and v is not None]


def get_humiditys(values, sensors):
    return [v for k, v in values.items() if k.startswith('h') and any(k.endswith(s) for s in sensors) and v is not None]


def get_dew_point(values):
    # Formula by Sensirion:
    # http://irtfweb.ifa.hawaii.edu/~tcs3/tcs3/Misc/Dewpoint_Calculation_Humidity_Sensor_E.pdf
    temps = get_temps(values, air_sens)
    humids = get_humiditys(values, air_sens)
    T = max(temps)
    RH = max(humids)
    if RH == 0:
        return float('nan')
    H = (np.log10(RH) - 2) / 0.4343 + (17.62 * T) / (243.12 + T)
    Dp = 243.12 * H / (17.62 - H)
    return Dp


def temps_below_dp(values, sensors, min_distance):
    return not np.isnan(values[interlock_dp]) and any(v < values[interlock_dp] + min_distance for v in get_temps(values, sensors))


def wait_for_min_dew_point(distance, timeout=60 * 60, save_data=True):
    timestamp_start = time.time()
    values = acquire_temperatures(save_data=save_data)
    while temps_below_dp(values, mod_sens, distance):
        values = acquire_temperatures(save_data=save_data)
        if time.time() - timestamp_start > timeout:
            raise RuntimeError('Target dew point could not be reached within specified timeout!')
    logging.info('Target dew point reached!')


def check_interlock(values, distance=min_interlock_distance, sleep_time=.2, save_data=True):
    if temps_below_dp(values, mod_sens, distance):
        # whait at current temperature till all tempertures are stabilized and dew point is low again
        target = dut['Climatechamber'].get_temperature_setpoint()
        cur_temp = dut['Climatechamber'].get_temperature()
        dut['Climatechamber'].set_temperature(cur_temp)
        wait_for_min_dew_point(distance, save_data=save_data)
        dut['Climatechamber'].set_temperature(target)


def go_to_temperature(target, wait_time=0, overshoot=0, accuracy=1, timeout=60*60, save_data=True, interlock=True):
    set_target = target + overshoot

    dut['Climatechamber'].set_temperature(set_target)
    timestamp_start = time.time()
    while True:
        temps = acquire_temperatures(save_data=save_data)
        temps[interlock_dp] = get_dew_point(temps)
        if interlock:
            check_interlock(temps)
        if temps[t_sens] is not None and temps[t_sens] > (target - accuracy) and temps[t_sens] < (target + accuracy):
            logging.info('Target temperature reached on device!')
            break
        if time.time() - timestamp_start > timeout:
            raise RuntimeError('Target temperature could not be reached within specified timeout!')

    dut['Climatechamber'].set_temperature(target)
    if wait_time > 0:
        logging.info('Waiting for {0:1.0f}s at {1}°C...'.format(wait_time, target))
        timestamp_start = time.time()
        while True:
            temps = acquire_temperatures(save_data=save_data)
            temps[interlock_dp] = get_dew_point(temps)
            if interlock:
                check_interlock(temps, save_data=save_data)
            if temps[t_sens] is not None and (temps[t_sens] < (target - accuracy) or temps[t_sens] > (target + accuracy)):
                logging.warning(f'Temperature on device deviated too much: Target = {target}, T_sens = {temps[t_sens]:1.2f}')
            if time.time() - timestamp_start > wait_time:
                logging.info('Wait time over. Continuing...')
                break


def setup_slack():
    global slack
    if notify_on_slack:
        if os.path.isfile(os.path.expanduser(slack_token)):
            with open(os.path.expanduser(slack_token), 'r') as token_file:
                token = token_file.read().strip()
        else:
            token = slack_token
        slack = WebClient(token)


def notify(message):
    if notify_on_slack:
        for user in slack_users:
            slack.chat_postMessage(channel=user, text=message, username='Thermocycle Bot', icon_emoji=':robot_face:')


if __name__ == '__main__':

    setup_slack()
    notify("Starts thermal cycles!")

    dut = Dut(PERIPHERYFILE)
    dut.init()
    sensors = setup_sensors()

    with open(OUTFILE_TEMPS, 'w') as f:
        f.write('#Timestamp, ' + ', '.join([s['name'] for s in sensors] + [interlock_dp]) + ', ' + '\n')

    logging.info('Starting run, setting start temperature to 20C...')
    dut['Climatechamber'].start_manual_mode()
    dut['Climatechamber'].set_air_dryer(True)  # make sure air dryer is running to avoid condensation
    try:
        go_to_temperature(starting_temperature, wait_time=minimal_starting_time, save_data=save_data_on_startup)
        wait_for_min_dew_point(starting_temperature - starting_dew_point, timeout=maximal_starting_time - minimal_starting_time)
    except Exception:
        notify("Thermal cycling couldn't be started!")
        raise

    total_time_start = time.time()
    cur_temp = starting_temperature
    next_iter = 1
    try:
        for cycle in cycles:
            for n_iter in range(next_iter, cycle['n_cycles'] + next_iter):
                logging.info('Starting cycle {}'.format(n_iter))
                for next_temp in cycle['temps']:
                    if next_temp < cur_temp:
                        logging.info('Cooling to {}'.format(next_temp))
                        overshoot = -10
                    else:
                        logging.info('Heating to {}'.format(next_temp))
                        overshoot = +5
                    go_to_temperature(next_temp, wait_time=cycle['wait_time'], overshoot=overshoot)
            next_iter += cycle['n_cycles']
    except Exception:
        notify("An error occured during thermal cycling!")
        raise
    finally:
        logging.info('Closing up. Setting temperature to 20°C.')
        dut['Climatechamber'].set_temperature(20)

    go_to_temperature(20)
    total_time = time.time() - total_time_start
    logging.info('Completed {0} cycles in {1:1.2f}h'.format(next_iter - 1, total_time / 3600))
    dut['Climatechamber'].stop_manual_mode()
    notify("Thermal cycles are finished!")
