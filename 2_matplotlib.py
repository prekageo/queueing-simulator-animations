#!/usr/bin/env python3

import math
import numpy as np
import random
import time

import matplotlib
from matplotlib import pyplot as plt
from matplotlib import animation

SPEED = .1
MAX_SVC_TIME = 40
QUEUE_WIDTH = 1.5

class Conf:
  def __init__(self):
    self.g = Generator()
    self.rss = RSS()
    self.packets = []
    self.queues = []
    self.processors = []

  def update(self, queues, processors, steal, push, svc_time_lambda, ia_time_lambda, name):
    self.QUEUES = queues
    self.PROCESSORS = processors
    self.STEAL = steal
    self.PUSH = push
    self.svc_time_lambda = svc_time_lambda
    self.ia_time_lambda = ia_time_lambda
    self.queueing_delay = []
    self.packet_count = 0
    self.name = name

    def adjust(container, klass, count):
      if count >= len(container):
        container += [klass(i + len(container)) for i in range(count - len(container))]
      else:
        for c in container[count - len(container):]:
          c.remove()
        del container[count - len(container):]
    adjust(self.queues, Queue, queues)
    adjust(self.processors, Processor, processors)
    self.objects = [self.g, self.rss] + self.processors + self.queues + self.packets
    for o in self.objects:
      patches.extend(o.draw(0))

  def gen_svc_time(self):
    return self.svc_time_lambda()
  def gen_ia_time(self):
    return self.ia_time_lambda()

  def record_queueing_delay(self, delay):
    self.queueing_delay.append(delay)
    if len(self.queueing_delay) > 30:
      del self.queueing_delay[0]

confs = [
  (1,1,True,True,lambda:20,lambda:40,'small bank'),
  (1,1,True,True,lambda:20,lambda:20,'small but busy bank'),
  (1,3,True,True,lambda:20,lambda:20,'bigger bank'),
  (1,5,True,True,lambda:20,lambda:20,'biggest bank'),
  (5,5,False,False,lambda:20,lambda:20,'supermarket'),
  (5,5,False,False,lambda:20,lambda:8,'busy supermarket'),
  (5,5,True,False,lambda:20,lambda:8,'supermarket where you can go to any cashier you want'),
  (5,5,True,False,lambda:random.randint(5,20),lambda:8,'not everyone has the same amount of products in his cart'),
]
curr_conf_idx = 0

patches = []

def key_callback(event):
  global curr_conf_idx, conf, screen

  if event.key == 'up' and curr_conf_idx < len(confs) - 1:
    curr_conf_idx += 1
  elif event.key == 'down' and curr_conf_idx > 0:
    curr_conf_idx -= 1

  conf.update(*confs[curr_conf_idx])

virt_time = 0
prv_display_time =0
fps = 0

def main():
  fig = plt.figure(figsize=(6,4))

  global ax, rss, queues, processors, fps
  ax = plt.axes(xlim=(-2.5, 12.5), ylim=(0, 10))
  ax.axis('off')

  global conf
  conf = Conf()
  conf.update(*confs[curr_conf_idx])

  fps_text = ax.text(-2,0.1,'')
  patches.extend([fps_text])

  def animate(t):
    global virt_time
    virt_time += 1
    for o in conf.objects[::-1]:
      o.tick(t)

    global prv_display_time
    now = time.time()

    global fps

    if virt_time % 10 == 0:
      fps = 10 / (now - prv_display_time)
    qd = sorted(conf.queueing_delay)
    mqd = 0
    if len(qd) > 0:
      mqd = qd[int(len(qd)*0.9)]

    fps_text.set_text('%s\nT=%d - fps=%.1f - packets=%d - 90th pct queueing delay=%d' % (conf.name, virt_time, fps, conf.packet_count, mqd))

    if virt_time % 10 == 0:
      prv_display_time = now

    return patches

  fig.canvas.mpl_connect('key_press_event', key_callback)
  anim = animation.FuncAnimation(fig, animate, frames=10000, interval=1)
  plt.show()

def pkt_arrived_rss(p, t):
  dest_q = random.randint(0, len(conf.queues) - 1)
  p.queue = conf.queues[dest_q]
  p.move(t, p.queue.recv_pos(), pkt_arrived_queue, speed = SPEED)
  p.queue.enqueue(p, t)

def pkt_arrived_queue(p, t):
  pass

class Generator:
  def __init__(self):
    self.next_time = 0

  def tick(self, t):
    if t >= self.next_time:
      self.next_time += conf.gen_ia_time()
      conf.packet_count += 1
      p = Packet(conf.gen_svc_time())
      p.move(t, conf.rss.recv_pos, pkt_arrived_rss, speed = SPEED)
      conf.packets.append(p)
      conf.objects.append(p)
      patches.extend(p.draw(t))

  def draw(self, t):
    return []

class Packet:
  id = 0
  def __init__(self, svc_time):
    self.id = Packet.id
    Packet.id += 1
    self.moves = []
    self.start_proc_time = None
    self.svc_time = svc_time
    self.pos = (4.5 + QUEUE_WIDTH/2,-1)
    self.color = 'C%d' % (self.id % 10)
    self.done_perc = 0
    self.prvx = 0
    self.prvy = 0
    self.pos = (5,0)
    self.circle = plt.Circle((0,0), 0.2, edgecolor='C%d' % (self.id % 10), facecolor='none')
    rad = self.svc_time / MAX_SVC_TIME * 180 - 90
    self.fillarc = matplotlib.patches.Polygon(arc_patch_points(.2, *self.calc_fill_degrees(self.svc_time)).T, closed=True, facecolor=self.color)
    tr = matplotlib.transforms.Affine2D().translate(*self.pos) + ax.transData
    self.circle.set_transform(tr)
    self.fillarc.set_transform(tr)
    ax.add_patch(self.circle)
    ax.add_patch(self.fillarc)
    patches.extend([self.circle, self.fillarc])

  def calc_fill_degrees(self, svc_time):
    rad = svc_time / MAX_SVC_TIME * 180 - 90
    return rad, -180-rad
  
  def draw(self, t):
    return []

  def tick(self, t):
    if len(self.moves) == 0:
      return
    move = self.moves[0]
    if move.animate(self, t):
      del self.moves[0]

  def process(self, t, callback):
    self.moves.append(Packet.ProcessAnimation(callback))

  def move(self, start_time, stop_pos, callback, callback_start = None, duration = None, speed = None):
    self.moves.append(Packet.MoveAnimation(start_time, stop_pos, callback, callback_start, duration, speed))

  class ProcessAnimation:
    def __init__(self, callback):
      self.callback = callback
      self.started = False

    def animate(self, p, t):
      if not self.started:
        self.started = True
        self.start_time = t
      perc = (t - self.start_time) / p.svc_time
      p.fillarc.set_xy(arc_patch_points(.2, *p.calc_fill_degrees(p.svc_time*(1-perc))).T)
      if perc >= 1:
        self.callback(p, t)
        return True
      return False

  class MoveAnimation:
    def __init__(self, start_time, stop_pos, callback, callback_start, duration, speed):
      self.start_time = start_time
      self.stop_pos = stop_pos
      self.callback = callback
      self.callback_start = callback_start
      self.duration = duration
      self.speed = speed
      self.started = False

    def animate(self, p, t):
      if not self.started:
        self.started = True
        self.start_time = t
        self.start_pos = p.pos
        if not self.duration:
          dist = math.sqrt((self.start_pos[0] - self.stop_pos[0]) ** 2 + (self.start_pos[1] - self.stop_pos[1]) ** 2)
          self.duration = dist / self.speed
        if self.callback_start:
          self.callback_start(p, t)
      if self.duration == 0:
        perc = 1
      else:
        perc = (t - self.start_time) / self.duration
      p.pos = interpolate_xy(perc, self.start_pos, self.stop_pos)
      tr = matplotlib.transforms.Affine2D().translate(*p.pos) + ax.transData
      p.circle.set_transform(tr)
      p.fillarc.set_transform(tr)
      if perc >= 1:
        if self.callback:
          self.callback(p, t)
        return True
      return False

  def remove(self):
    conf.packets.remove(self)
    conf.objects.remove(self)
    patches.remove(self.circle)
    patches.remove(self.fillarc)
    self.circle.remove()
    self.fillarc.remove()

class RSS:
  def __init__(self):
    self.recv_pos = (4.5 + QUEUE_WIDTH/2,2.5)

  def draw(self, t):
    vertices = [(4.5, 2.5),(4.5, 3),(4, 3.5),(6,3.5),(5.5,3),(5.5,2.5)]
    Path = matplotlib.path.Path
    codes = [Path.MOVETO, Path.LINETO, Path.LINETO, Path.MOVETO, Path.LINETO, Path.LINETO]
    path = Path(vertices, codes)
    self.rect = matplotlib.patches.PathPatch(path, facecolor='none',edgecolor='k')
    x,y=self.recv_pos
    x-=5.1
    y=-2
    self.rect.set_transform(matplotlib.transforms.Affine2D().translate(x,y) + ax.transData)
    ax.add_patch(self.rect)
    return []
  def tick(self, t):
    pass

class Queue:
  def __init__(self, id):
    self.id = id
    self.queue = []
    self.count_ready = 0
    Path = matplotlib.path.Path
    vertices = [(0,0),(0,2),(1,2),(1,0)]
    codes = [Path.MOVETO, Path.LINETO, Path.LINETO, Path.LINETO]
    path = Path(vertices, codes)
    self.rect = matplotlib.patches.PathPatch(path, facecolor='none',edgecolor='k')
    x, y = self.recv_pos()
    x -= 0.5
    self.rect.set_transform(matplotlib.transforms.Affine2D().translate(x,y) + ax.transData)
    ax.add_patch(self.rect)
    patches.append(self.rect)

  def draw(self, t):
    return []

  def tick(self, t):
    if not conf.PUSH:
      return
    processor = pick_random(conf.processors, lambda i, proc: not proc.is_busy())
    if processor:
      p = self.dequeue(t)
      if p:
        processor.proc = p
        p.move(t, processor.pos, processor.pkt_arrived, duration = 10)

  def ypos(self, i):
    return 7.5 - i * 0.5

  def recv_pos(self):
    x = self.id // 2 if self.id % 2 == 0 else -self.id // 2
    y = min(self.ypos(len(self.queue)), 5.5)
    return 4.5 + x * QUEUE_WIDTH + QUEUE_WIDTH / 2, y

  def enqueue(self, p, t):
    p.move(t, (self.recv_pos()[0], self.ypos(len(self.queue))), self.enqueued, duration = 10)
    self.queue.append(p)
  
  def enqueued(self, p, t):
    self.count_ready += 1
    p.enqueue_time = t

  def dequeue(self, t):
    if self.count_ready == 0:
      return None
    self.count_ready -= 1
    ret = self.queue[0]
    conf.record_queueing_delay(t - ret.enqueue_time)
    del self.queue[0]
    for i, p in enumerate(self.queue):
      p.move(t, (self.recv_pos()[0], self.ypos(i)), None, speed = SPEED)
    return ret

  def empty(self):
    return len(self.queue) == 0

  def remove(self):
    patches.remove(self.rect)
    for p in self.queue:
      p.remove()

class Processor:
  def __init__(self, id):
    self.id = id
    self.proc = None
    x = self.id // 2 if self.id % 2 == 0 else -self.id // 2
    self.pos = (4.5 + x * QUEUE_WIDTH + QUEUE_WIDTH / 2, 9)
    self.rect = matplotlib.patches.RegularPolygon(self.pos, 5, .5, facecolor='none', edgecolor='k')
    ax.add_patch(self.rect)
    patches.append(self.rect)

  def draw(self, t):
    return []

  def tick(self, t):
    if conf.PUSH or self.proc:
      return
    p = conf.queues[self.id].dequeue(t)
    if p is None and conf.STEAL:
      q = pick_random(conf.queues, lambda i, q: not q.empty() and conf.processors[i].is_busy())
      if q:
        p = q.dequeue(t)
    if p is None:
      return
    self.proc = p
    p.move(t, self.pos, self.pkt_arrived, duration = 10)

  def pkt_arrived(self, p, t):
    p.process(t, self.pkt_processed)

  def pkt_processed(self, p, t):
    self.proc.remove()
    self.proc = None
    self.rect.set_edgecolor('k')
    self.rect.set_linewidth(1)

  def is_busy(self):
    return self.proc is not None

  def remove(self):
    patches.remove(self.rect)
    if self.proc:
      self.proc.remove()

# TODO: use generic interpolate function below
def interpolate_xy(perc, src, dst):
  if perc >= 1:
    return dst
  def interpolate(a, b):
    return a + (b-a) * perc
  x = interpolate(src[0], dst[0])
  y = interpolate(src[1], dst[1])
  return x,y

def interpolate(perc, *steps):
  perc = max(0, min(1, perc))
  count = len(steps) - 1
  perc *= count
  ofs = int(perc)
  perc -= ofs
  start = steps[ofs]
  if ofs == count:
    return start
  stop = steps[ofs + 1]
  def f(a, b):
    return a + (b-a) * perc
  if isinstance(start, list):
    ret = [f(a, b) for a,b in zip(start, stop)]
  else:
    ret = f(start, stop)
  return ret

def arc_patch_points(radius, theta1, theta2, resolution=50):
  theta = np.linspace(np.radians(theta1), np.radians(theta2), resolution)
  points = np.vstack((radius*np.cos(theta), radius*np.sin(theta)))
  return points

def pick_random(collection, criteria):
  arr = []
  for i, item in enumerate(collection):
    if criteria(i, item):
      arr.append(item)
  if len(arr) > 0:
    return random.choice(arr)
  return None

main()
