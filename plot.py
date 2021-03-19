import matplotlib.pyplot as plt
import numpy as np


class Plot:
    def __init__(self, yvalues, xvalues=[], title="", labels=[],
                 xlabel="", ylabel="", save=0):
        self.yvalues = yvalues
        self.xvalues = xvalues
        self.title = title
        self.save = save
        self.labels = labels
        self.xlabel = xlabel
        self.ylabel = ylabel

    def plot(self):
        plt.figure()
        plt.grid()
        plt.title(self.title)

        plt.plot(self.xvalues, self.yvalues)

        if self.save:
            plt.savefig(f"plots/{self.title}.png")

        plt.show()

    def plot_by_day(self):
        fig = plt.figure()
        plt.grid()
        plt.title(self.title)

        plt.xlim((0, 365))
        plt.ylim((min(self.yvalues), max(self.yvalues) + 2))

        # if re.search(".*(C|c)ost.*", self.title):
        plt.axvline(80, linestyle='--', c='r')
        plt.axvline(172, linestyle='--', c='r')
        plt.axvline(265, linestyle='--', c='r')
        plt.axvline(356, linestyle='--', c='r')

        ax = fig.add_subplot()

        major_ticks = np.arange(0, 365, 30)
        minor_ticks = np.arange(0, 365, 5)

        ax.set_xticks(major_ticks)
        ax.set_xticks(minor_ticks, minor=True)

        ax.grid(which='both')

        ax.grid(which='minor', alpha=0.2)
        ax.grid(which='major', alpha=0.5)

        plt.plot(range(365), self.yvalues)

        if self.save:
            plt.savefig(f"plots/{self.title}.png")

        plt.show()

    def plot_by_hour(self):
        fig = plt.figure()
        plt.grid()

        plt.xlim((0, 23))

        ax = fig.add_subplot(1, 1, 1)
        major_ticks = np.arange(0, 23, 1)
        minor_ticks = np.arange(0, 23, 1)
        ax.set_xticks(major_ticks)
        ax.set_xticks(minor_ticks, minor=True)

        plt.title(self.title)
        plt.plot(range(24), self.yvalues, '.-')

    def scatter(self):
        plt.figure()
        plt.grid()
        plt.title(self.title)

        plt.xlim((min(self.xvalues), max(self.xvalues)))

        plt.scatter(self.xvalues, self.yvalues)
        plt.show()


class MultiPlot(Plot):

    # override
    def plot(self, legend_labels):
        plt.figure()
        plt.grid()
        plt.title(self.title)
        plt.xlabel(self.xlabel)

        plt.ylim((np.min(self.yvalues) - 1, np.max(self.yvalues) + 2))


        for i in range(self.yvalues.shape[0]):
            plt.plot(self.xvalues, self.yvalues[i, :], ".-",label=self.labels + " " + str(legend_labels[i]))

        plt.legend()
        plt.show()

    def single_plot(self, label_axis=""):
        plt.figure()
        plt.grid()
        plt.title(self.title)
        plt.xlabel(self.xlabel)

        xlen = self.yvalues.shape[0]
        # plt.xlim((-0.1, xlen - 1 + 0.1))
        # plt.ylim((np.min(self.yvalues) - 1, np.max(self.yvalues) + 2))

        # plt.xticks(ticks=range(0, xlen, 5), labels=list(self.labels[0: xlen: 5]), rotation=45)

        for i in range(self.yvalues.shape[1]):
            plt.plot(range(xlen), self.yvalues[:, i])
        # plt.legend()
        plt.show()

    def plot_cost_prob_loss(self, label):
        x = self.xvalues[:, 0]
        y = self.yvalues[:, 0]

        fig = plt.figure()
        plt.grid()
        plt.title(self.title)
        plt.xlabel("Loss Probability")
        plt.ylabel("Daily Mean Cost")

        ax = fig.add_subplot()

        for i, txt in enumerate(label):
            ax.annotate(txt, (x[i], y[i]))

        for j in range(self.yvalues.shape[0]):
            plt.plot(x[j], y[j], marker="+", markersize=12, mew=2)
        plt.show()
