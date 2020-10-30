from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as md
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import matplotlib.gridspec as gridspec

if __name__ == '__main__':
    times, data = [], []
    with open('thermocycling_temps.dat', 'r') as f:
        f.readline()    # Remove title line
        for l in f.readlines():
            d = l.strip().split(', ')
            times.append(datetime.fromtimestamp((float(d[0]))))
            dat = []
            dat.append(float(d[1]))
            dat.append(float(d[2]))
            dat.append(float(d[3]))
            data.append(dat)

    print(data)

    fig = Figure()
    FigureCanvas(fig)
    gs = gridspec.GridSpec(2, 1, height_ratios=[2, 1])
    fig.subplots_adjust(bottom=0.15, right=0.78)

    ax = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax)

    ax.plot(times, [d[0] for d in data], label='T_freezer')
    ax.plot(times, [d[1] for d in data], label='T_sens')

    ax2.plot(times, [d[2] for d in data], color='C2', label='Hum_sens')

    xfmt = md.DateFormatter('%d %H:%M')
    ax2.xaxis.set_major_formatter(xfmt)
    plt.setp(ax.xaxis.get_majorticklabels(), visible=False)
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=-45, ha='left')

    ax.grid()
    ax2.grid()
    ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left')
    ax2.legend(bbox_to_anchor=(1.01, 1), loc='upper left')
    ax.set_title('Thermal cycling {}'.format(times[0].strftime("%Y-%m-%d, %H:%M")))
    ax.set_ylabel('T [°C]')
    ax2.set_ylabel('rel. Humidity [%]')

    fig.savefig('temps.pdf')
