import time
import logging

from basil.dut import Dut
from weiss_labevent import WeissLabEvent

OUTFILE_TEMPS = 'thermocycling_temps.dat'
OUTFILE_TIMES = 'thermocycling_times.dat'

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
fmt = '%(asctime)s - %(levelname)-7s %(message)s'
logging.basicConfig(format=fmt, filename='thermocycling_test.log', filemode='w', level=logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter(fmt))
logging.root.addHandler(sh)

def log_temps():
    t_freezer = freezer.get_temperature()
    for _ in range(10):
        t_sens = dut['Thermohygrometer'].get_temperature(channel=0)
        humidity = dut['Thermohygrometer'].get_humidity(channel=0)

        if t_sens is None or humidity is None:
            continue

        if t_sens < 100. and t_sens > -90. and humidity <= 100. and humidity >= 0.:
            break
    else:
        logging.error('Sensirion measurement could not be evaluated: T = {0}, rel. Hum. = {1}'.format(t_sens, humidity))
        t_sens = t_freezer
        humidity = 0.0

    logging.info('T_freezer = {0}, T_sens = {1}, Hum = {2}'.format(t_freezer, t_sens, humidity))

    with open(OUTFILE_TEMPS, 'a') as f:
        f.write('{0}, T_freezer = {1}, T_sens = {2}, Hum = {3}\n'.format(time.time(), t_freezer, t_sens, humidity))

    return t_freezer, t_sens, humidity

if __name__ == '__main__':

    with open(OUTFILE_TEMPS, 'w') as f:
        pass
    with open(OUTFILE_TIMES, 'w') as f:
        pass

    dut = Dut('sensirionEKH4_pyserial.yaml')
    dut.init()

    freezer = WeissLabEvent('192.168.10.2')
    freezer.init()

    logging.info('Starting run, setting start temperature to 20C...')
    freezer.start_manual_mode()
    freezer.go_to_temperature(20)

    total_time_start = time.time()
    try:
        for cycle in range(1, 21):
            this_cycle_time_start = time.time()
            logging.info('Starting cycle {}'.format(cycle))
            
            freezer.set_temperature(-42)
            for _ in range(3600):
                t_freezer, t_sens, humidity = log_temps()
                if t_sens < -39.5:
                    logging.info('Target temperature reached on device!')
                    break
                time.sleep(1)

            freezer.set_temperature(62)
            for _ in range(3600):
                t_freezer, t_sens, humidity = log_temps()
                if t_sens > 59.5:
                    logging.info('Target temperature reached on device!')
                    break
                time.sleep(1)

            freezer.set_temperature(-42)
            for _ in range(3600):
                t_freezer, t_sens, humidity = log_temps()
                if t_sens < 20.5:
                    break
                time.sleep(1)

            this_cycle_time = time.time() - this_cycle_time_start
            logging.info('Cycle {0} completed in {1}s'.format(cycle, this_cycle_time))

            with open(OUTFILE_TIMES, 'a') as f:
                f.write('{0}\n'.format(this_cycle_time))
    except Exception as e:
        freezer.set_temperature(20)
        raise e

    total_time = time.time() - total_time_start
    logging.info('Completed all 20 cycles in {}s'.format(total_time))
