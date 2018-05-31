#!/usr/bin/env python3

import math
import numpy as np
import random
import sys
import time

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

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

def set_eye():
  gluPerspective(60,4.0/3,1,30)
  gluLookAt(6,-6,6,5,5,0,0,0,1)

def opengl_init():
  glutInit(sys.argv)
  glutInitDisplayMode(GLUT_RGB | GLUT_DOUBLE | GLUT_DEPTH)
  glutInitWindowSize(800,600)
  glutInitWindowPosition(50,50)
  glutCreateWindow('Queue simulator')
  glShadeModel(GL_SMOOTH)
  glMatrixMode(GL_PROJECTION)
  glLoadIdentity()
  set_eye()

  glClearColor(0,0,0,0)
  glEnable(GL_DEPTH_TEST)
  glEnable(GL_LIGHTING)
  glMatrixMode(GL_MODELVIEW)

  glLightModelfv(GL_LIGHT_MODEL_AMBIENT,[0,0,0])
  l = GL_LIGHT0
  glLoadIdentity()
  glLightfv(l, GL_POSITION, [.5,5,5,1])
  glLightfv(l, GL_AMBIENT, [0,0,0])
  glLightfv(l, GL_DIFFUSE, [.5,.5,.5])
  glLightfv(l, GL_SPECULAR, [0,0,0])
  glEnable(l)

  l = GL_LIGHT1
  glLightfv(l, GL_POSITION, [9.5,5,5,1])
  glLightfv(l, GL_AMBIENT, [0,0,0])
  glLightfv(l, GL_DIFFUSE, [.5,.5,.5])
  glLightfv(l, GL_SPECULAR, [0,0,0])
  glEnable(l)

LIST_WALL = 1
LIST_RSS_WALL = 2
fps = 0

def display_callback():
  global prv_display_time
  now = time.time()

  glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

  global xxx,xxxstep
  glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, [0,0,0])
  x = GL_FRONT_AND_BACK
  c =ROOM_COLOR
  glMaterialfv(x, GL_AMBIENT, [0,0,0])
  glMaterialfv(x, GL_DIFFUSE, c)
  glMaterialfv(x, GL_SPECULAR, [0,0,0])
  glLoadIdentity()

  glLoadIdentity()
  glTranslatef(0,0,-.01)
  glTranslatef(-.05,0,0)
  glScale(11.1,11.1,1)
  glCallList(LIST_WALL)
  
  glLoadIdentity()
  glRotatef(90,1,0,0)
  glTranslatef(0,0,-11)
  glScale(11,5,1)
  glCallList(LIST_WALL)
  
  glLoadIdentity()
  glRotatef(90,0,1,0)
  glTranslatef(-5,0,0)
  glScale(5,11,1)
  glCallList(LIST_WALL)
  
  glLoadIdentity()
  glRotatef(-90,0,1,0)
  glTranslatef(0,0,-11)
  glScale(5,11,1)
  glCallList(LIST_WALL)

  global virt_time, fps
  for o in conf.objects:
    o.draw(virt_time)

  if virt_time % 10 == 0:
    fps = 10 / (now - prv_display_time)
  qd = sorted(conf.queueing_delay)
  mqd = 0
  if len(qd) > 0:
    mqd = qd[int(len(qd)*0.9)]

  glDisable(GL_LIGHTING)
  glDisable(GL_DEPTH_TEST)
  glColor3f(1,1,1)
  glMatrixMode(GL_PROJECTION)
  glPushMatrix()
  glLoadIdentity()
  gluOrtho2D(0, 800, 600, 0)
  glMatrixMode(GL_MODELVIEW)
  text(0,570, conf.name)
  text(0,590,'T=%d - fps=%.1f - packets=%d - 90th pct queueing delay=%d' % (virt_time, fps, conf.packet_count, mqd))
  glMatrixMode(GL_PROJECTION)
  glPopMatrix()
  glMatrixMode(GL_MODELVIEW)
  glEnable(GL_LIGHTING)
  glEnable(GL_DEPTH_TEST)

  glutSwapBuffers()
  if virt_time % 10 == 0:
    prv_display_time = now

def text(x,y,string):
  glLoadIdentity()
  glRasterPos2f(x, y)
  for c in string:
    glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(c))

def mouseButtonClicked(button,state,x, y):
  global xorig,yorig
  if(state==GLUT_DOWN and button==GLUT_LEFT_BUTTON):
    xorig=x;
    yorig=y;
  elif (state==GLUT_UP and button==GLUT_LEFT_BUTTON):
    xorig=0;
    glMatrixMode(GL_PROJECTION);
    glLoadIdentity();
    set_eye()
    glMatrixMode(GL_MODELVIEW)

def mouseActiveMotion(x, y):
  global xorig,yorig
  if (xorig):
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    set_eye()
    glTranslatef(5,5,0)
    glRotatef((y-yorig)/3.0,1,0,0)
    glRotatef((x-xorig)/3.0,0,0,1)
    glTranslatef(-5,-5,0)
    glMatrixMode(GL_MODELVIEW)

state = 0
def idle_callback():
  global virt_time, prv_frame_time, state
  
  if state == 0:
    for o in conf.objects[::-1]:
      o.tick(virt_time)
    virt_time += 1
    state = 1
  elif state == 1:
    now = time.time()
    if now - prv_frame_time >= 0.020:
      glutPostRedisplay()
      prv_frame_time = now
      state = 0

def key_callback(key, x, y):
  global curr_conf_idx, conf

  if key == GLUT_KEY_UP and curr_conf_idx < len(confs) - 1:
    curr_conf_idx += 1
  elif key == GLUT_KEY_DOWN and curr_conf_idx > 0:
    curr_conf_idx -= 1
  elif key == GLUT_KEY_F4 and glutGetModifiers() == GLUT_ACTIVE_ALT:
    sys.exit(0)

  print('conf', curr_conf_idx, confs[curr_conf_idx])
  conf.update(*confs[curr_conf_idx])

def main():
  opengl_init()
  conf.update(*confs[curr_conf_idx])

  glutDisplayFunc(display_callback)
  glutIdleFunc(idle_callback)
  glutSpecialFunc(key_callback)
  glutMouseFunc(mouseButtonClicked)
  glutMotionFunc(mouseActiveMotion)

  def wall(resolution):
    glNormal(0,0,1)
    for i in range(resolution):
      glBegin(GL_QUAD_STRIP)
      for j in range(resolution+1):
        glVertex3f(i/resolution,j/resolution,0)
        glVertex3f((i+1)/resolution,j/resolution,0)
      glEnd()
  glNewList(LIST_WALL, GL_COMPILE)
  wall(10)
  glEndList()
  
  glNewList(LIST_RSS_WALL, GL_COMPILE)
  glPushMatrix()
  glTranslatef(.4,-.5,0)
  glRotatef(-90,0,1,0)
  glScale(.5,.5,.5)
  glCallList(LIST_WALL)
  glPopMatrix()

  glPushMatrix()
  glTranslatef(.5,-.5,.5)
  glRotatef(90,0,1,0)
  glScale(.5,.5,.5)
  glCallList(LIST_WALL)
  glPopMatrix()

  glPushMatrix()
  glTranslatef(.4,0,0)
  glRotatef(-90,0,1,0)
  glRotatef(45,1,0,0)
  glScale(.5,1/math.sqrt(2),.5)
  glCallList(LIST_WALL)
  glPopMatrix()

  glPushMatrix()
  glTranslatef(.5,0,.5)
  glRotatef(90,0,1,0)
  glRotatef(-45,1,0,0)
  glScale(.5,1/math.sqrt(2),.5)
  glCallList(LIST_WALL)
  glPopMatrix()

  glBegin(GL_QUAD_STRIP)
  glNormal(0,1,0)
  glVertex3f(0,.5,0)
  glVertex3f(-.1,.5,0)
  glVertex3f(0,.5,0.5)
  glVertex3f(-.1,.5,0.5)
  glNormal(0,0,1)
  glVertex3f(.5,0,0.5)
  glVertex3f(.4,0,0.5)
  glVertex3f(.5,-.5,0.5)
  glVertex3f(.4,-.5,0.5)
  glNormal(0,-1,0)
  glVertex3f(.5,-.5,0)
  glVertex3f(.4,-.5,0)
  glEnd()
  glEndList()

  glutMainLoop()

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
    self.q = gluNewQuadric()
    self.q2 = gluNewQuadric()
    self.pos = (4.5 + QUEUE_WIDTH/2,-1)
    self.color = COLORS[self.id % 10]
    self.done_perc = 0

  def calc_fill_degrees(self, svc_time):
    rad = svc_time / MAX_SVC_TIME * 180 - 90
    return rad, -180-rad

  def draw(self, t):
    glLoadIdentity()
    glTranslatef(*self.pos, 0)
    glMaterialfv(GL_FRONT_AND_BACK,GL_EMISSION,[0,0,0])
    glMaterialfv(GL_FRONT_AND_BACK,GL_AMBIENT,self.color)
    glMaterialfv(GL_FRONT_AND_BACK,GL_SPECULAR,self.color)
    glMaterialfv(GL_FRONT_AND_BACK,GL_DIFFUSE,self.color)
    top = self.svc_time*(1-self.done_perc) / MAX_SVC_TIME
    gluCylinder(self.q, .2, .2, top, 16, 16)
    glTranslatef(0, 0, top)
    gluDisk(self.q2, 0, .2, 16, 16)

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
    conf.packets.remove(self)
    conf.objects.remove(self)

class RSS:
  def __init__(self):
    self.q = gluNewQuadric()
    self.recv_pos = (4.5 + QUEUE_WIDTH/2,3.5)

  def draw(self, t):
    glLoadIdentity()
    glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, [0,0,0])
    glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT, [0,0,0])
    glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, [0,1,0])
    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, [0,0,0])
    glMaterialfv(GL_BACK, GL_EMISSION, [0,0,0])
    glMaterialfv(GL_BACK, GL_AMBIENT, [0,0,0])
    glMaterialfv(GL_BACK, GL_DIFFUSE, [0,0,1])
    glMaterialfv(GL_BACK, GL_SPECULAR, [0,0,0])
    glMaterialf( GL_BACK, GL_SHININESS, 0)
    
    glLoadIdentity()
    glTranslatef(3.5+QUEUE_WIDTH/2,3,0)
    glCallList(LIST_RSS_WALL)

    glLoadIdentity()
    glTranslatef(5.5+QUEUE_WIDTH/2,3,0)
    glScalef(-1,1,1)
    glCallList(LIST_RSS_WALL)

  def tick(self, t):
    pass

class Queue:
  def __init__(self, id):
    self.id = id
    self.queue = []
    self.count_ready = 0
    self.q = gluNewQuadric()

  def draw(self, t):
    glLoadIdentity()
    glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, [0,0,0])
    glMaterialfv(GL_FRONT_AND_BACK, GL_AMBIENT, [0,0,0])
    glMaterialfv(GL_FRONT_AND_BACK, GL_DIFFUSE, QUEUE_COLOR)
    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, [0,0,0])
    glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 0)

    glTranslatef(self.recv_pos()[0] - QUEUE_WIDTH*0.9 / 2, 6, 0)
    glScale(QUEUE_WIDTH*0.9,2,0)
    glNormal(0,0,1)
    glCallList(LIST_WALL)

    glLoadIdentity()
    glTranslatef(self.recv_pos()[0] - QUEUE_WIDTH*0.9 / 2, 6, 0)

    for i in range(3):
      color = interpolate((t % 50 - i * 10) / 50, *QUEUE_ARROW_COLORS)
      glMaterialfv(GL_FRONT_AND_BACK, GL_EMISSION, color)
      ofs = .25 + i * .5
      glBegin(GL_QUAD_STRIP)
      glVertex3f(QUEUE_WIDTH*0.9*0.1,ofs,0.01)
      glVertex3f(QUEUE_WIDTH*0.9*0.1,ofs+.1,0.01)
      glVertex3f(QUEUE_WIDTH*0.9/2,ofs+.2,0.01)
      glVertex3f(QUEUE_WIDTH*0.9/2,ofs+.3,0.01)
      glVertex3f(QUEUE_WIDTH*0.9*0.9,ofs,0.01)
      glVertex3f(QUEUE_WIDTH*0.9*0.9,ofs+.1,0.01)
      glEnd()

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
    for p in self.queue:
      p.remove()

class Processor:
  def __init__(self, id):
    self.id = id
    self.proc = None
    self.q = gluNewQuadric()
    x = self.id // 2 if self.id % 2 == 0 else -self.id // 2
    self.pos = (4.5 + x * QUEUE_WIDTH + QUEUE_WIDTH / 2, 9.5)

  def draw(self, t):
    glLoadIdentity()
    glTranslatef(*self.pos, 0)
    if self.proc:
      glLineWidth(2)
      glMaterialfv(GL_FRONT_AND_BACK,GL_EMISSION,self.proc.color)
    else:
      glLineWidth(1)
      glMaterialfv(GL_FRONT_AND_BACK,GL_EMISSION,[1,1,1,0])
    polygon = 5
    angle = 0
    glBegin(GL_QUAD_STRIP)
    for i in range(polygon+1):
      glVertex3f(.5*math.sin(angle+2*math.pi/polygon*i),.5*math.cos(angle+2*math.pi/polygon*i),0)
      glVertex3f(.7*math.sin(angle+2*math.pi/polygon*i),.7*math.cos(angle+2*math.pi/polygon*i),0)
    glEnd()

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

conf = Conf()

main()
