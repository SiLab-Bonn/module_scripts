#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

'''
    This basic scan records an IV curve of the sensor of a module
    while making sure the chip is powered and configured.
'''

import os
import ast
import time
import yaml
import logging
import numpy as np
import tables as tb
from tqdm import tqdm

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

from basil.dut import Dut


OUTPUT_DIR = 'output_data'

scan_configuration = {
    'module_name': 'FBK 6092-27',
    'chip_type': 'rd53a',
    'hv_current_limit': 10e-6,
    'VBIAS_start': -1,
    'VBIAS_stop': -200,
    'VBIAS_step': -2,

    'samples': 5
}


class RawDataTable(tb.IsDescription):
    voltage = tb.Int32Col(pos=1)
    current = tb.Float64Col(pos=2)
    current_error = tb.Float64Col(pos=3)


class RunConfigTable(tb.IsDescription):
    attribute = tb.StringCol(64)
    value = tb.StringCol(512)


class ConfigDict(dict):
    def __init__(self, *args):
        for key, value in dict(*args).items():
            self.__setitem__(key, value)

    def __setitem__(self, key, val):
        # Change types on value setting
        key, val = self._type_cast(key, val)
        dict.__setitem__(self, key, val)

    def _type_cast(self, key, val):
        ''' Return python objects '''
        # Some data is in binary array representation (e.g. pytable data)
        # These must be convertet to string
        if isinstance(key, (bytes, bytearray)):
            key = key.decode()
        if isinstance(val, (bytes, bytearray)):
            val = val.decode()
        if 'chip_sn' in key:
            return key, val
        try:
            if isinstance(val, np.generic):
                return key, val.item()
            return key, ast.literal_eval(val)
        except (ValueError, SyntaxError):  # fallback to return the object
            return key, val


class SensorIVScan(object):
    scan_id = 'sensor_iv_scan'

    def __init__(self, scan_config, device_config=None):
        self.config = scan_config
        self.run_name = time.strftime("%Y%m%d_%H%M%S") + '_' + self.scan_id
        self.output_filename = os.path.join(OUTPUT_DIR, self.config['module_name'], self.run_name)
        self.log = logging.getLogger(self.__class__.__name__)

        if device_config is None:
            device_config = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'sensor_iv.yaml')
        self.devices = Dut(device_config)

    def init(self):
        self.devices.init()

        self.devices['Sourcemeter'].source_volt()
        self.devices['Sourcemeter'].set_voltage_range(1000)

        if not os.path.isdir(OUTPUT_DIR):
            os.mkdir(OUTPUT_DIR)
        if not os.path.isdir(os.path.dirname(self.output_filename)):
            os.mkdir(os.path.dirname(self.output_filename))

        self.h5_file = tb.open_file(self.output_filename + '.h5', mode='w', title=self.scan_id)
        self.h5_file.create_group(self.h5_file.root, 'configuration', 'Configuration')
        run_config_table = self.h5_file.create_table(self.h5_file.root.configuration, name='run_config', title='Run config', description=RunConfigTable)

        for key, value in {'scan_id': self.scan_id, 'run_name': self.run_name, 'module': self.config['module_name'], 'chip_type': self.config['chip_type']}.items():
            row = run_config_table.row
            row['attribute'] = key
            row['value'] = value
            row.append()
        scan_cfg_table = self.h5_file.create_table(self.h5_file.root.configuration, name='scan_config', title='Scan configuration', description=RunConfigTable)
        for key, value in self.config.items():
            row = scan_cfg_table.row
            row['attribute'] = key
            row['value'] = value
            row.append()
        self.raw_data_table = self.h5_file.create_table(self.h5_file.root, name='raw_data', title='Raw data', description=RawDataTable)

    def __enter__(self):
        self.init()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.devices.close()

    def start(self):
        try:
            self._scan()
        except KeyboardInterrupt:
            pass
        finally:
            self._ramp_hv_to(self.devices['Sourcemeter'], 0)
            self.devices['Sourcemeter'].off()
            self.h5_file.close()
            self.devices.close()
        invert = self.config['VBIAS_stop'] < 0
        plot(self.output_filename + '.h5', invert_x=invert)

    def _get_voltage(self):
        ret = self.devices['Sourcemeter'].get_voltage()
        if ',' in ret:
            return float(ret.split(',')[0])
        else:
            return float(ret)

    def _get_current(self):
        ret = self.devices['Sourcemeter'].get_current()
        if ',' in ret:
            return float(ret.split(',')[1])
        else:
            return float(ret)

    def _ramp_hv_to(self, dev, target, verbose=True):
        if not dev.get_on():
            dev.set_voltage(0)
            dev.on()

        start = int(self._get_voltage())
        target = int(target)

        if abs(start - target) > 10:
            stepsize = 2
        elif abs(start - target) > 100:
            stepsize = 10
        else:
            dev.set_voltage(target)
            return

        dev.source_volt()
        if abs(target) < 0.2:
            dev.set_voltage_range(0.2)
        elif abs(target) < 2:
            dev.set_voltage_range(2)
        elif abs(target) < 20:
            dev.set_voltage_range(20)
        elif abs(target) < 200:
            dev.set_voltage_range(200)
        else:
            dev.set_voltage_range(1000)

        voltage_step = stepsize if target > start else -1 * stepsize
        add = 1 if target > start else -1

        if verbose:
            self.log.info('Ramping bias voltage to {} V...'.format(target))
            pbar = tqdm(total=len(range(start, target + add, voltage_step)), unit=' V')
        for v in range(start, target + add, voltage_step):
            dev.set_voltage(v)
            if verbose:
                pbar.update(1)
            time.sleep(0.5)
        if verbose:
            pbar.close()
        dev.set_voltage(target)

    def _scan(self):
        '''
        Sensor IV scan main loop

        Parameters
        ----------
        VBIAS_start : int
            First bias voltage to scan
        VBIAS_stop : int
            Last bias voltage to scan. This value is included in the scan.
        VBIAS_step : int
            Stepsize to increase the bias voltage by in every step.
        '''

        module_name = self.config.get('module_name', 'module_0')
        VBIAS_start = self.config.get('VBIAS_start', 0)
        VBIAS_stop = self.config.get('VBIAS_stop', -5)
        VBIAS_step = self.config.get('VBIAS_step', -1)
        hv_current_limit = self.config.get('hv_current_limit', 1e-6)
        samples = self.config.get('samples', 1)

        try:
            self.devices['Sourcemeter'].off()
            self.devices['Sourcemeter'].set_voltage(0)
            self.devices['Sourcemeter'].set_current_limit(hv_current_limit)
            self.devices['Sourcemeter'].on()

            add = 1 if VBIAS_stop > 0 else -1
            pbar = tqdm(total=abs(VBIAS_stop), unit='Volt')

            last_v = 0
            for v_bias in range(VBIAS_start, VBIAS_stop + add, VBIAS_step):
                self.devices['Sourcemeter'].set_voltage(v_bias)

                # Wait until stable
                last_val = 0
                for _ in range(100):
                    val = self._get_current()
                    if abs(last_val - val) < abs(0.1 * val):
                        break
                    last_val = val
                else:
                    self.log.warning('Current is not stabilizing!')
                    break

                # Take 'samples' measurements and use mean as value
                c_arr = []
                for _ in range(samples):
                    c_arr.append(self._get_current())
                    time.sleep(0.1)
                current = np.mean(c_arr)
                row = self.raw_data_table.row
                row['voltage'] = v_bias
                row['current'] = current
                row['current_error'] = np.std(c_arr)
                row.append()
                self.raw_data_table.flush()
                pbar.update(abs(v_bias) - last_v)
                last_v = abs(v_bias)

                # Abort scan if in current limit
                if abs(current) >= hv_current_limit * 0.98:
                    self.log.error('Current limit reached. Aborting scan!')
                    break

            pbar.close()
            self.log.info('Scan finished')
        except Exception as e:
            self.log.error('An error occurred: %s' % e)
        finally:
            self._ramp_hv_to(self.devices['Sourcemeter'], 0)


def plot(data_file, invert_x=True, log_y=True, level='', text_color='#07529a'):
    with tb.open_file(data_file, 'r') as f:
        data = f.root.raw_data[:]
        run_config = ConfigDict(f.root.configuration.run_config[:])

    x, y, yerr = [], [], []
    for d in data:
        x.append(d[0])
        y.append(abs(d[1]))
        yerr.append(d[2])

    fig = Figure()
    FigureCanvas(fig)
    ax = fig.add_subplot(111)

    fig.subplots_adjust(top=0.85)
    y_coord = 0.92

    chip_type = run_config['chip_type']
    fig.text(0.1, y_coord, '{0} {1}'.format(chip_type, level), fontsize=12, color=text_color, transform=fig.transFigure)
    identifier = run_config['module']
    fig.text(0.65, y_coord, 'Module: {0}'.format(identifier), fontsize=12, color=text_color, transform=fig.transFigure)

    ax.errorbar(x, y, yerr=yerr, linestyle='none', marker='.', color='C0')

    ax.set_title('Sensor IV curve', color=text_color)
    ax.set_xlabel('Bias voltage [V]')
    ax.set_ylabel('Leakage current [A]')
    ax.grid()

    if invert_x:
        ax.invert_xaxis()
    if log_y:
        ax.set_yscale('log')

    fig.savefig(data_file[:-3] + '.pdf')


if __name__ == '__main__':
    with SensorIVScan(scan_config=scan_configuration) as scan:
        scan.start()

    # plot()
