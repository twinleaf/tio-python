#!/usr/bin/env python3
 
import time, random
import math
import collections
import matplotlib.pyplot
import matplotlib.animation
import tldevice
import argparse

class RealtimePlot:
  def __init__(self, 
      dev,
      windowLength = 10, # seconds 
      tickTime = 0.5, # seconds
      xlabel="Time (s)", 
      ylabel="Field (nT)"):
    
    self.dev = dev

    queueLength = int(windowLength*dev._tio.protocol.streams[0]['stream_Fs'])
    self.data_t = collections.deque(maxlen=queueLength)
    self.data_x = collections.deque(maxlen=queueLength)
    self.data_y = collections.deque(maxlen=queueLength)
    self.data_z = collections.deque(maxlen=queueLength)

    self.tickTime = tickTime

    matplotlib.rcParams['font.family'] = 'Palatino'
    self.fig = matplotlib.pyplot.figure(constrained_layout=True)
    gs = matplotlib.gridspec.GridSpec(3,1, figure=self.fig, hspace= 0.08, wspace=0.1)
    self.ax1 = self.fig.add_subplot(gs[2])
    self.ax2 = self.fig.add_subplot(gs[1], sharex=self.ax1)
    self.ax3 = self.fig.add_subplot(gs[0], sharex=self.ax2) 
    matplotlib.pyplot.setp(self.ax2.get_xticklabels(), visible=False)
    matplotlib.pyplot.setp(self.ax3.get_xticklabels(), visible=False)
 
    self.ax1line = matplotlib.lines.Line2D([],[], color='black', linewidth = 0.5)
    self.ax2line = matplotlib.lines.Line2D([],[], color='black', linewidth = 0.5)
    self.ax3line = matplotlib.lines.Line2D([],[], color='black', linewidth = 0.5)
    self.ax1.add_line(self.ax1line)
    self.ax2.add_line(self.ax2line)
    self.ax3.add_line(self.ax3line)

    self.ax1.set_xlabel(xlabel)
    self.ax1.set_ylabel('X '+ylabel)
    self.ax2.set_ylabel('Y '+ylabel)
    self.ax3.set_ylabel('Z '+ylabel)

    self.animate()
    self.ani = matplotlib.animation.FuncAnimation(self.fig, self.animate, interval=10)
    matplotlib.pyplot.show()

  def animate(self,*args):
    data = self.dev.vector(duration=self.tickTime, timeaxis=True, flush=False)

    self.data_t.extend(data[0])
    self.data_x.extend(data[1])
    self.data_y.extend(data[2])
    self.data_z.extend(data[3])

    self.ax1line.set_data(self.data_t, self.data_x)
    self.ax2line.set_data(self.data_t, self.data_y)
    self.ax3line.set_data(self.data_t, self.data_z)

    self.ax1.set_xlim(self.data_t[0], self.data_t[-1])
    self.ax1.relim()
    self.ax1.autoscale_view()
    #self.ax2.set_xlim(self.data_t[0], self.data_t[-1])
    self.ax2.relim()
    self.ax2.autoscale_view()
    #self.ax3.set_xlim(self.data_t[0], self.data_t[-1])
    self.ax3.relim()
    self.ax3.autoscale_view()
    return self.ax1line, self.ax2line, self.ax3line,

def main():
  parser = argparse.ArgumentParser(prog='vectorMonitor', 
                             description='Vector Field Graphing Monitor')
  parser.add_argument("url", 
                nargs='?', 
                default='tcp://localhost/',
                help='URL: tcp://localhost')
  args = parser.parse_args()
  dev = tldevice.Device(args.url)
  
  RealtimePlot(dev)

if __name__ == "__main__": main()