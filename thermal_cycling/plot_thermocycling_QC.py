from datetime import datetime
import time
import signal
import numpy as np
import os

import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import matplotlib.gridspec as gridspec

time_str = None  # time of file: 'YYYYmmdd_HHMMSS'/ latest when None
plot_frequently = False  # if plot should be repeated regularly
plot_interval = 30  # minimal time between each plot in seconds

FILEPATH = os.path.dirname(os.path.abspath(__file__))
DATAPATH = os.path.join(FILEPATH, 'output_data')
if time_str is None:
    file_times = [f[:15] for f in os.listdir(DATAPATH) if f.endswith('_thermocycling_temps.dat')]
    times = [time.mktime(datetime.strptime(s, "%Y%m%d_%H%M%S").timetuple()) for s in file_times]
    time_str = file_times[np.argmax(times)]
TEMPSFILE = os.path.join(DATAPATH, time_str + '_thermocycling_temps.dat')


class DelayedKeyboardInterrupt(object):
    def __enter__(self):
        self.signal_received = False
        self.old_handler = signal.signal(signal.SIGINT, self.handler)

    def handler(self, sig, frame):
        self.signal_received = (sig, frame)

    def __exit__(self, type, value, traceback):
        signal.signal(signal.SIGINT, self.old_handler)
        if self.signal_received:
            self.old_handler(*self.signal_received)


def plot():
    with open(TEMPSFILE, 'r') as f:
        l = f.readline()    # Remove title line
        names = [n.strip() for n in l.split(',')[1:]]
        times = {name: [] for name in names}
        data = {name: [] for name in names}
        times['dp'] = []
        data['dp'] = []
        for l in f.readlines():
            d = l.strip().split(',')
            ts = datetime.fromtimestamp((float(d[0])))
            printdp = True
            for name, value in zip(names, d[1:]):
                if name == 'dew_point':
                    dp = float(value.strip())
                else:
                    if 'None' not in value:
                        times[name].append(ts)
                        v = float(value.strip())
                        data[name].append(v)
                    elif name in ['t_air2', 't_sens', 'h_air2', 'h_sens']:
                        printdp = False
            if printdp:
                times['dp'].append(ts)
                data['dp'].append(dp)

    fig = Figure()
    FigureCanvas(fig)
    gs = gridspec.GridSpec(2, 1, height_ratios=[2, 1])
    fig.subplots_adjust(bottom=0.15, right=0.78)

    ax = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax)

    ax.plot(times['t_setp'], data['t_setp'], label='T_setpoint', color='gray')
    ax.plot(times['t_chamber'], data['t_chamber'], label='T_chamber', color='C0')
    ax.plot(times['t_sens'], data['t_sens'], label='T_sens', color='C1')
    ax.plot(times['t_mod'], data['t_mod'], label='T_mod', color='C2')
    ax.plot(times['t_mod2'], data['t_mod2'], label='T_mod_2', color='C4')
    ax.plot(times['t_air'], data['t_air'], label='T_air', color='C5')
    ax.plot(times['t_air2'], data['t_air2'], label='T_air_2', color='C6')
    ax.plot(times['dp'], data['dp'], label='Dew Point', color='C3')

    ax2.plot(times['h_sens'], data['h_sens'], color='C1', label='Hum_sens')
    ax2.plot(times['h_mod'], data['h_mod'], color='C2', label='Hum_mod')
    ax2.plot(times['h_mod2'], data['h_mod2'], color='C4', label='Hum_mod_2')
    # ax2.plot(times['h_air'], data['h_air'], color='C5', label='Hum_air')
    ax2.plot(times['h_air2'], data['h_air2'], color='C6', label='Hum_air_2')

    xfmt = md.DateFormatter('%d %H:%M')
    ax2.xaxis.set_major_formatter(xfmt)
    plt.setp(ax.xaxis.get_majorticklabels(), visible=False)
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=-45, ha='left')

    ax.grid()
    ax2.grid()
    ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left')
    ax2.legend(bbox_to_anchor=(1.01, 1), loc='upper left')
    ax.set_title('Thermal cycling {}'.format(times['t_setp'][0].strftime("%Y-%m-%d, %H:%M")))
    ax.set_ylabel('T [°C]')
    ax2.set_ylabel('rel. Humidity [%]')

    fig.savefig(os.path.join(DATAPATH, time_str + '_temps.pdf'))
    fig.savefig(os.path.join(FILEPATH, 'temps.pdf'))


if __name__ == '__main__':
    plot()

    last_time = time.time()
    while plot_frequently:
        with DelayedKeyboardInterrupt():
            plot()
        cur_time = time.time()
        if cur_time - last_time < plot_interval:
            time.sleep(plot_interval - (cur_time - last_time))
        else:
            time.sleep(1)
        last_time = cur_time
