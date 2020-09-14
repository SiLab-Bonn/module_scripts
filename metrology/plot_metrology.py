import os
import csv
import numpy as np

# This import registers the 3D projection, but is otherwise unused.
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 unused import

import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.ticker import LinearLocator, FormatStrFormatter
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

in_file = ''
module_name = 'ASD 15-4-C10'
method = 'ZW RFM'
origin = 'top left'


def get_data(infile):
    class uniqueList(list):
        def append_unique(self, val):
            if val not in self:
                self.append(val)

    if infile.split('.')[-1] == 'csv':
        with open(infile, 'r') as csv_file:
            reader = csv.reader(csv_file, delimiter=',', dialect=csv.excel)
            x, y, z_x0, z_x1, z_x2, z_x3 = uniqueList(), uniqueList(), [], [], [], []
            for row in reader:
                x.append_unique(float(row[0]))
                y.append_unique(float(row[1]))
                z_x0.append(float(row[2]))

                x.append_unique(float(row[3]))
                y.append_unique(float(row[4]))
                z_x1.append(float(row[5]))

                x.append_unique(float(row[6]))
                y.append_unique(float(row[7]))
                z_x2.append(float(row[8]))

                x.append_unique(float(row[9]))
                y.append_unique(float(row[10]))
                z_x3.append(float(row[11]))

        x = np.array(x)
        y = np.array(y)
        X, Y = np.meshgrid(x, y)
        Z = np.array([z_x0, z_x1, z_x2, z_x3]).T
    elif infile.split('.')[-1] == 'xyz':
        with open(infile, 'r') as f:
            all_values = []
            x, y = uniqueList(), uniqueList()
            for line in f.readlines():
                vals = [float(v) for v in line.split(' ')]
                vals[0] = round(vals[0], 0)
                vals[1] = round(vals[1], 0)
                x.append_unique(vals[1])
                y.append_unique(vals[0])
                all_values.append(vals)

        z = np.zeros((len(x), len(y)))
        for vals in all_values:
            z[np.where(np.array(x) == vals[1]), np.where(np.array(y) == vals[0])] = vals[2]

        min_x = min(x)
        min_y = min(y)
        min_z = np.min(z)
        x = [v - min_x for v in x]
        y = [v - min_y for v in y]
        X, Y = np.meshgrid(np.array(x), np.array(y))
        Z = (z - min_z) * 1e3

        Z = Z.T

        # Correct tilt along y-axis
        # n = np.cross(Y - X, Z - X)
        # nn = n / np.linalg.norm(n)
        # angles = np.abs(np.arcsin(nn))
        # print(angles)

    print(X.shape)
    print(Y.shape)
    print(Z.shape)
    return X, Y, Z


def plot_title_page(X, Y, Z, pdf):
    fig = Figure()
    FigureCanvas(fig)
    ax = fig.add_subplot(111)
    ax.axis('off')

    text = 'Metrology measurement for module'
    ax.text(0.01, 0.9, text, fontsize=10)
    ax.text(0.3, 0.8, module_name, fontsize=12)
    text = 'done with {0}.'.format(method)
    ax.text(0.01, 0.7, text, fontsize=10)

    z_max = np.max(Z)
    x_zmax = X[0][np.where(Z == z_max)[1]][0]
    y_zmax = Y[np.where(Z == z_max)[0][0]][0]

    text = 'Origin is {}.'.format(origin)
    ax.text(0.01, 0.6, text)
    text = 'Max elevation is {0}$\mu$m at (x={1}mm, y={2}mm)'.format(z_max, x_zmax, y_zmax)
    ax.text(0.01, 0.5, text)

    pdf.savefig(fig)

def plot_surface(X, Y, Z, pdf, projections=True, live=True):
    fig = plt.figure(figsize=plt.figaspect(0.5))
    ax = plt.axes(projection='3d')
    
    cs = ax.plot_surface(X, Y, Z, rstride=1, cstride=1, cmap='coolwarm', edgecolor='none')

    if projections:
        ax.contour(X, Y, Z, zdir='x', offset=ax.get_xlim()[0], cmap='viridis')
        ax.contour(X, Y, Z, zdir='y', offset=ax.get_ylim()[1], cmap='viridis')

    # Angle for PDF output
    ax.view_init(45, -15)

    # Set module to correct aspect ratio
    scaling = np.array([getattr(ax, 'get_{}lim'.format(dim))() for dim in 'xyz'])
    # ax.auto_scale_xyz(*[[np.min(scaling), np.max(scaling)]]*3)

    cb = fig.colorbar(cs, shrink=0.75, aspect=50, orientation='horizontal')
    cb.set_label('z [$\mu$m]')

    ax.set_xlabel('x [mm]')
    ax.set_ylabel('y [mm]')
    ax.set_zlabel('z [$\mu$m]')

    ax.set_title(module_name)

    if live:
        plt.show()

    pdf.savefig(fig, bbox_inches='tight')

def plot_wireframe(X, Y, Z, pdf, projections=True):
    # Plotting
    fig = plt.figure(figsize=plt.figaspect(0.5))
    ax = plt.axes(projection='3d')

    ax.plot_wireframe(X, Y, Z)

    if projections:
        ax.contour(X, Y, Z, zdir='x', offset=ax.get_xlim()[0], cmap='viridis')
        ax.contour(X, Y, Z, zdir='y', offset=ax.get_ylim()[1], cmap='viridis')

    # Angle for PDF output
    ax.view_init(45, -15)

    # Set module to correct aspect ratio
    scaling = np.array([getattr(ax, 'get_{}lim'.format(dim))() for dim in 'xyz'])
    # ax.auto_scale_xyz(*[[np.min(scaling), np.max(scaling)]]*3)

    ax.set_xlabel('x [mm]')
    ax.set_ylabel('y [mm]')
    ax.set_zlabel('z [$\mu$m]')

    ax.set_title(module_name)

    pdf.savefig(fig, bbox_inches='tight')


def plot_contour(X, Y, Z, pdf):
    # Plotting
    fig = plt.figure()
    ax = plt.axes()

    # Plot wireframe in PDF output
    cs = ax.contour(Y, X, Z)
    ax.clabel(cs, inline=1, fontsize=10)

    # ax.set_xlim(np.max(X), np.min(X))
    plt.gca().invert_yaxis()

    cb = fig.colorbar(cs, shrink=0.75, orientation='horizontal')

    ax.set_xlabel('y [mm]')
    ax.set_ylabel('x [mm]')
    cb.set_label('z [$\mu$m]')

    ax.set_title(module_name)

    pdf.savefig(fig)


if __name__ == '__main__':
    X, Y, Z = get_data(in_file)
    pdf = PdfPages(os.path.join(os.path.dirname(in_file), '_'.join(os.path.split(in_file)[-1].split('.')[0:-1]) + '.pdf'))
    plot_title_page(X, Y, Z, pdf)
    plot_surface(X, Y, Z, pdf, live=True)
    plot_wireframe(X, Y, Z, pdf)
    plot_contour(X, Y, Z, pdf)

    pdf.close()
