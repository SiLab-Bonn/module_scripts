import time
import logging

from basil.dut import Dut

LOGFILE = 'thermocycling.log'
OUTFILE_TEMPS = 'thermocycling_temps.dat'

N_CYCLES = 20       # Amount of cycles to perform
T_MIN = -40         # Minimum temperature
T_MAX = 60          # Maximum temperature
WAIT_TIME = 2 * 60  # Wait time at target temperature

# Logging setup
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
fmt = '%(asctime)s - %(levelname)-7s %(message)s'
logging.basicConfig(format=fmt, filename=LOGFILE, filemode='w', level=logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter(fmt))
logging.root.addHandler(sh)

def acquire_temperatures():
    t_chamber = dut['Climatechamber'].get_temperature()
    setpoint = dut['Climatechamber'].get_temperature_setpoint()
    t_sens = dut['Thermohygrometer'].get_temperature(channel=0)
    h_sens = dut['Thermohygrometer'].get_humidity(channel=0)
    t_mod = dut['Thermohygrometer'].get_temperature(channel=1)
    h_mod = dut['Thermohygrometer'].get_humidity(channel=1)
    t_air = dut['Thermohygrometer'].get_temperature(channel=3)
    h_air = dut['Thermohygrometer'].get_humidity(channel=3)

    try:
        logging.info('T_ch = {0:1.2f}, T_sns = {1:1.2f}, Hum_sns = {2:1.2f}, T_mod = {3:1.2f}, H_mod = {4:1.2f}, T_air = {5:1.2f}, H_air = {6:1.2f}'.format(t_chamber, t_sens, h_sens, t_mod, h_mod, t_air, h_air))
        with open(OUTFILE_TEMPS, 'a') as f:
            f.write('{0}, {1}, {2:1.2f}, {3:1.2f}, {4:1.2f}, {5:1.2f}, {6:1.2f}, {7:1.2f}, {8:1.2f}\n'.format(time.time(), setpoint, t_chamber, t_sens, h_sens, t_mod, h_mod, t_air, h_air))
    except TypeError:
        logging.info('T_ch = {0:1.2f}, T_sns = {1}, H_sns = {2}, T_mod = {3}, H_mod = {4}, T_air = {5}, Hum_air = {6}'.format(t_chamber, t_sens, h_sens, t_mod, h_mod, t_air, h_air))
        with open(OUTFILE_TEMPS, 'a') as f:
            f.write('{0}, {1}, {2:1.2f}, {3}, {4}, {5}, {6}, {7}, {8}\n'.format(time.time(), setpoint, t_chamber, t_sens, h_sens, t_mod, h_mod, t_air, h_air))

    return t_chamber, t_sens, h_sens, t_mod, h_mod, t_air, h_air

def go_to_temperature(target, wait_time=0, overshoot=False, accuracy=1, timeout=30*60):
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
    with open(OUTFILE_TEMPS, 'w') as f:
        pass

    dut = Dut('thermocycling.yaml')
    dut.init()

    logging.info('Starting run, setting start temperature to 20C...')
    dut['Climatechamber'].start_manual_mode()
    dut['Climatechamber'].set_air_dryer(True) # make sure air dryer is running to avoid condensation
    go_to_temperature(20, wait_time=3*60*60)  # wait 3h at 20°C to make sure the air is dry

    # Reset data file
    with open(OUTFILE_TEMPS, 'w') as f:
        f.write('#Timestamp, T_setpoint, T_chamber, T_sens, Hum_sens, T_mod, Hum_mod, T_air, Hum_air\n')

    total_time_start = time.time()
    try:
        for cycle in range(1, N_CYCLES + 1):
            logging.info('Starting cycle {}'.format(cycle))
            logging.info('Cooling to {}'.format(T_MIN))
            go_to_temperature(T_MIN, wait_time=WAIT_TIME, overshoot=True)
            logging.info('Heating to {}'.format(T_MAX))
            go_to_temperature(T_MAX, wait_time=WAIT_TIME, overshoot=True)
    finally:
        logging.info('Closing up. Setting temperature to 20°C.')
        dut['Climatechamber'].set_temperature(20)

    go_to_temperature(20)
    total_time = time.time() - total_time_start
    logging.info('Completed {0} cycles in {1:1.2f}h'.format(N_CYCLES, total_time / 3600))
    dut['Climatechamber'].stop_manual_mode()
