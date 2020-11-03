import os
import csv
import xlrd
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
module_name = 'ASD 15-3-C4'
method = 'Mitutoyo Measuring Microscope'
# method = 'ZW RFM'
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

    elif infile.split('.')[-1] == 'xlsx':
        workbook = xlrd.open_workbook(infile)
        worksheet = workbook.sheet_by_index(0)

        x, y = [], []
        Z = np.zeros((11, 4), dtype=float)
        for col in range(1, 12):
            y.append(worksheet.cell_value(1, col))

            for row in range(2, 6):
                if col == 1:
                    x.append(worksheet.cell_value(row, 0))

                Z[col - 1, row - 2] = worksheet.cell_value(row, col)

        X, Y = np.meshgrid(np.array(x), np.array(y))

    return X, Y, Z


def get_maximum_bow(X, Y, Z):
    # plane fit to corner points
    x = np.unique(X)
    y = np.unique(Y)

    xs, ys, zs = [], [], []
    for i_y in [0, -1]:
        for i_x in [0, -1]:
            xs.append(x[i_x])
            ys.append(y[i_y])
            zs.append(Z[i_y, i_x])

    tmp_A = []
    tmp_b = []
    for i in range(len(x)):
        tmp_A.append([xs[i], ys[i], 1])
        tmp_b.append(zs[i])
    b = np.matrix(tmp_b).T
    A = np.matrix(tmp_A)
    fit = (A.T * A).I * A.T * b
    # errors = b - A * fit
    # residual = np.linalg.norm(errors)

    print('Bottom plane fit result:')
    print('{0:1.3e} x + {1:1.3e} y + {2:1.3e} = z'.format(fit.item(0), fit.item(1), fit.item(2)))

    max_bow = abs(fit.item(2) - np.max(Z))

    print('Max bow: {}'.format(max_bow))

    return max_bow, fit


def plot_title_page(X, Y, Z, pdf, max_bow):
    fig = Figure()
    FigureCanvas(fig)
    ax = fig.add_subplot(111)
    ax.axis('off')

    text = 'Metrology measurement for module'
    ax.text(0.01, 0.9, text, fontsize=10)
    ax.text(0.3, 0.8, module_name, fontsize=12)
    text = 'done with {0}.'.format(method)
    ax.text(0.01, 0.7, text, fontsize=10)

    text = 'Origin is {}.'.format(origin)
    ax.text(0.01, 0.6, text)
    text = 'Max bow is {0}$\mu$m'.format(max_bow)
    ax.text(0.01, 0.5, text)

    pdf.savefig(fig)


def plot_surface(X, Y, Z, pdf, plane_fit=None, projections=True, live=True, colorbar=False):
    fig = plt.figure(figsize=plt.figaspect(0.5))
    ax = plt.axes(projection='3d')

    cs = ax.plot_surface(X, Y, Z, rstride=1, cstride=1, cmap='coolwarm', edgecolor='none', alpha=0.75, shade=True)

    if projections:
        ax.contour(X, Y, Z, zdir='x', offset=ax.get_xlim()[0], cmap='viridis')
        ax.contour(X, Y, Z, zdir='y', offset=ax.get_ylim()[1], cmap='viridis')

    # Set module to correct aspect ratio
    scaling = np.array([getattr(ax, 'get_{}lim'.format(dim))() for dim in 'xyz'])
    # ax.auto_scale_xyz(*[[np.min(scaling), np.max(scaling)]]*3)

    if colorbar:
        cb = fig.colorbar(cs, shrink=0.75, aspect=50, orientation='horizontal')
        cb.set_label(r'z [$\mu$m]')

    # Plot fit plane
    if fit is not None:
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        X_p, Y_p = np.meshgrid(np.arange(xlim[0], xlim[1], int(xlim[1] / 100)), np.arange(ylim[0], ylim[1], int(ylim[1] / 100)))

        Z_p = np.zeros(X_p.shape)
        for r in range(X_p.shape[0]):
            for c in range(X_p.shape[1]):
                Z_p[r, c] = fit.item(0) * X_p[r, c] + fit.item(1) * Y_p[r, c] + fit.item(2)
        ax.plot_wireframe(X_p, Y_p, Z_p, color='k')

    ax.set_xlabel('x [mm]')
    ax.set_ylabel('y [mm]')
    ax.set_zlabel(r'z [$\mu$m]')

    ax.set_title(module_name)

    # Angle for PDF output
    ax.view_init(45, -15)

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

    # Set module to correct aspect ratio
    scaling = np.array([getattr(ax, 'get_{}lim'.format(dim))() for dim in 'xyz'])
    # ax.auto_scale_xyz(*[[np.min(scaling), np.max(scaling)]]*3)

    ax.set_xlabel('x [mm]')
    ax.set_ylabel('y [mm]')
    ax.set_zlabel('z [$\mu$m]')

    ax.set_title(module_name)

    # Angle for PDF output
    ax.view_init(45, -15)

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
    max_bow, fit = get_maximum_bow(X, Y, Z)

    pdf = PdfPages(os.path.join(os.path.dirname(in_file), '_'.join(os.path.split(in_file)[-1].split('.')[0:-1]) + '.pdf'))
    plot_title_page(X, Y, Z, pdf, max_bow=max_bow)
    plot_surface(X, Y, Z, pdf, plane_fit=fit, live=True)
    plot_wireframe(X, Y, Z, pdf)
    plot_contour(X, Y, Z, pdf)

    pdf.close()
