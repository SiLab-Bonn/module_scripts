from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import matplotlib.gridspec as gridspec

if __name__ == '__main__':
    times = {'t_setp': [], 't_chamber': [], 't_sens': [], 'h_sens': []}
    data = {'t_setp': [], 't_chamber': [], 't_sens': [], 'h_sens': []}
    with open('thermocycling_temps.dat', 'r') as f:
        f.readline()    # Remove title line
        for l in f.readlines():
            d = l.strip().split(',')
            ts = datetime.fromtimestamp((float(d[0])))

            times['t_setp'].append(ts)
            data['t_setp'].append(float(d[1].strip()))
            times['t_chamber'].append(ts)
            data['t_chamber'].append(float(d[2].strip()))
            
            t_sens = d[3].strip()
            if 'None' not in t_sens:
                times['t_sens'].append(ts)
                data['t_sens'].append(float(t_sens))
            h_sens = d[4].strip()
            if 'None' not in h_sens:
                times['h_sens'].append(ts)
                data['h_sens'].append(float(h_sens))

    fig = Figure()
    FigureCanvas(fig)
    gs = gridspec.GridSpec(2, 1, height_ratios=[2, 1])
    fig.subplots_adjust(bottom=0.15, right=0.78)

    ax = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax)

    ax.plot(times['t_setp'], data['t_setp'], label='T_setpoint', color='gray')
    ax.plot(times['t_chamber'], data['t_chamber'], label='T_chamber', color='C0')
    ax.plot(times['t_sens'], data['t_sens'], label='T_sens', color='C1')

    ax2.plot(times['h_sens'], data['h_sens'], color='C2', label='Hum_sens')

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

    fig.savefig('temps.pdf')
