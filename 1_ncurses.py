#!/usr/bin/env python3

import math
import numpy as np
import random
import sys
import time

import curses

def parse_hex_color(c):
  return [int(c[:2],16)/255,int(c[2:4],16)/255,int(c[4:],16)/255]

SPEED = .1
MAX_SVC_TIME = 40
COLORS = ['1f77b4', 'ff7f0e', '2ca02c', 'd62728', '9467bd', '8c564b', 'e377c2', '7f7f7f', 'bcbd22', '17becf']
COLORS = [parse_hex_color(c) for c in COLORS]
QUEUE_WIDTH = 1.5
ROOM_COLOR=parse_hex_color('FFD0AA')
QUEUE_COLOR=parse_hex_color('557FCC')
QUEUE_ARROW_COLORS=[parse_hex_color(c) for c in ['000000', 'FFFFFF', '000000']]

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

virt_time = 0
prv_frame_time = 0
prv_display_time = 0

fps = 0

def display_callback():
  global prv_display_time, screen
  now = time.time()

  global virt_time, fps
  for o in conf.objects:
    o.draw(virt_time)

  if virt_time % 10 == 0:
    fps = 10 / (now - prv_display_time)
  qd = sorted(conf.queueing_delay)
  mqd = 0
  if len(qd) > 0:
    mqd = qd[int(len(qd)*0.9)]

  screen.addstr(26,0, conf.name)
  screen.clrtoeol()
  screen.addstr(27,0,'T=%d - fps=%.1f - packets=%d - 90th pct queueing delay=%d' % (virt_time, fps, conf.packet_count, mqd))
  screen.clrtoeol()

  mybox(25, 80, 0, 0)
  screen.noutrefresh()
  curses.doupdate()
  if virt_time % 10 == 0:
    prv_display_time = now

state = 0
def idle_callback():
  # print('idle')
  global virt_time, prv_frame_time, state, screen
  
  if state == 0:
    for o in conf.objects[::-1]:
      o.tick(virt_time)
    virt_time += 1
    state = 1
  elif state == 1:
    now = time.time()
    if True: # TODO
      display_callback()
      prv_frame_time = now
      state = 0

def key_callback(key, x, y):
  global curr_conf_idx, conf, screen

  if key != 27:
    return
  key = screen.getch()
  if key != 91:
    return
  key = screen.getch()

  if key == 65 and curr_conf_idx < len(confs) - 1:
    curr_conf_idx += 1
  elif key == 66 and curr_conf_idx > 0:
    curr_conf_idx -= 1

  conf.update(*confs[curr_conf_idx])

def main():
  global conf

  try:
    global screen
    screen = curses.initscr()
    curses.start_color()
    curses.use_default_colors()
    for i in range(len(COLORS)):
      curses.init_color(i+1, int(1000*COLORS[i][0]), int(1000*COLORS[i][1]), int(1000*COLORS[i][2]))
      curses.init_pair(i, i, curses.COLOR_BLACK)
    curses.curs_set(0)

    conf = Conf()
    conf.update(*confs[curr_conf_idx])

    screen.timeout(0)
    curses.noecho()
    while True:
      time.sleep(.01)
      c = screen.getch()
      if c != -1:
        key_callback(c, 0, 0)
      idle_callback()

  finally:
    curses.endwin()

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
    self.color = curses.color_pair(self.id % 10 + 1)
    self.done_perc = 0
    self.prvx = 0
    self.prvy = 0

  def calc_fill_degrees(self, svc_time):
    rad = svc_time / MAX_SVC_TIME * 180 - 90
    return rad, -180-rad

  def draw(self, t):
    global screen
    y,x = ncurses_scale(self.pos)
    screen.addch(self.prvy, self.prvx, ' ')
    screen.attron(self.color)
    top = self.svc_time*(1-self.done_perc) / MAX_SVC_TIME
    ch = chr(int(0x2588-7*(1-top)))
    screen.addch(y,x,ch)
    screen.attrset(0)
    self.prvx = x
    self.prvy = y

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
      p.done_perc = (t - self.start_time) / p.svc_time
      if p.done_perc >= 1:
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
      if perc >= 1:
        if self.callback:
          self.callback(p, t)
        return True
      return False

  def remove(self):
    screen.addch(self.prvy, self.prvx, ' ')
    conf.packets.remove(self)
    conf.objects.remove(self)

def ncurses_scale(pos):
  x = pos[0]
  y = pos[1]
  return int(25-y*2.5), int(x*7)

class RSS:
  def __init__(self):
    self.recv_pos = (4.5 + QUEUE_WIDTH/2,2.5)

  def draw(self, t):
    y,x=ncurses_scale(self.recv_pos)
    mybox(3, 11, y+1,x-5)

  def tick(self, t):
    pass

class Queue:
  def __init__(self, id):
    self.id = id
    self.queue = []
    self.count_ready = 0

  def draw(self, t):
    y,x=ncurses_scale((self.recv_pos()[0],6))
    mybox(5, 5, y-5,x-2)

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
    global screen
    screen.erase()
    for p in self.queue:
      p.remove()

def mybox(h, w, y, x):
  global screen
  h -= 1
  w -= 1
  screen.addch(y, x, curses.ACS_ULCORNER)
  screen.addch(y, x+w, curses.ACS_URCORNER)
  screen.addch(y+h, x, curses.ACS_LLCORNER)
  screen.addch(y+h, x+w, curses.ACS_LRCORNER)
  for i in range(x+1,x+w):
    screen.addch(y, i, curses.ACS_HLINE)
    screen.addch(y+h, i, curses.ACS_HLINE)
  for i in range(y+1,y+h):
    screen.addch(i, x, curses.ACS_VLINE)
    screen.addch(i, x+w, curses.ACS_VLINE)

class Processor:
  def __init__(self, id):
    self.id = id
    self.proc = None
    x = self.id // 2 if self.id % 2 == 0 else -self.id // 2
    self.pos = (4.5 + x * QUEUE_WIDTH + QUEUE_WIDTH / 2, 9)

  def draw(self, t):
    y,x=ncurses_scale(self.pos)
    global screen
    if self.proc:
      screen.attrset(self.proc.color)
    mybox(3, 5, y-1,x-2)
    if self.proc:
      screen.attrset(0)

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

  def is_busy(self):
    return self.proc is not None

  def remove(self):
    global screen
    screen.erase()
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
