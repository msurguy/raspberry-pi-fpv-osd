#!/usr/bin/python

import picamera
import time
import datetime
import numpy as np
import string
import random
import os
import math
from gps import *
import subprocess
import threading

from PIL import Image, ImageDraw, ImageFont

# Video Resolution for recording
VIDEO_HEIGHT = 720
VIDEO_WIDTH = 1280

baseDir='/home/pi/OSD/' # directory where the video will be recorded

crosshairImagePath = '/home/pi/OSD/crosshair.png'
gpsd = None # seting the global variable to track whether GPSD service is running
 
os.system('clear') # clear the terminal from any other text

# Create empty images to store text overlays
textOverlayCanvas = Image.new("RGB", (704, 60))
textOverlayPixels = textOverlayCanvas.load()

# Use Roboto font (must be downloaded first)
font = ImageFont.truetype("/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf", 20) 

initialLatitude = 0
initialLongitude = 0
initialStartupTime = ""
timeActive = 0
distanceTraveled = 0
secondsRecorded = 0
isCameraRecording = False

def make_time(gps_datetime_str):
    """Makes datetime object from string object"""
    if not 'n/a' == gps_datetime_str:
        datetime_string = gps_datetime_str
        datetime_object = datetime.datetime.strptime(datetime_string, "%Y-%m-%dT%H:%M:%S")
        return datetime_object

def elapsed_time_from(start_time, now_time):
    """calculate time delta from latched time and current time"""
    time_then = make_time(start_time)
    time_now = make_time(now_time)
    if time_then is None:
        return
    delta_t = time_now - time_then
    return delta_t

def distance(origin, destination):
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371 # km

    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = radius * c

    return d

class GpsPoller(threading.Thread):
   def __init__(self):
      threading.Thread.__init__(self)
      global gpsd #bring it in scope
      gpsd = gps(mode=WATCH_ENABLE) #starting the stream of info
      self.current_value = None
      self.running = True #setting the thread running to true
 
   def run(self):
      global gpsd
      while gpsp.running:
         gpsd.next() #this will continue to loop and grab EACH set of gpsd info to clear the buffer
        
with picamera.PiCamera() as camera:
   camera.resolution = (VIDEO_WIDTH, VIDEO_HEIGHT)
   camera.framerate = 60
   camera.led = False
   camera.start_preview()

   time.sleep(3)

   camera.start_recording('video.h264')
   isCameraRecording = True

   gpsp = GpsPoller() # create the GPS Poller thread

   topOverlayImage = textOverlayCanvas.copy()
   bottomOverlayImage = textOverlayCanvas.copy()

   # Load the crosshair image
   crosshairImg = Image.open(crosshairImagePath)

   # Create an image padded to the required size with
   crosshairPad = Image.new('RGBA', (((crosshairImg.size[0] + 31) // 32) * 32, ((crosshairImg.size[1] + 15) // 16) * 16))
   crosshairPad.paste(crosshairImg, (0, 0))

   # Attach overlays 
   topOverlay = camera.add_overlay(topOverlayImage.tobytes(), format='rgb', size=(704,60), layer=5, alpha=128, fullscreen=False, window=(0,20,704,60))
   bottomOverlay = camera.add_overlay(bottomOverlayImage.tobytes(), format='rgb', size=(704,60), layer=4, alpha=128, fullscreen=False, window=(0,400,704,60))
   crosshairOverlay = camera.add_overlay(crosshairPad.tobytes(), format='rgba', size=(400,400), layer=3, alpha=10, fullscreen=False, window=(0,0,704,512))

   try:
      gpsp.start() # start receiving data from GPS sensor

      while True:
          if (gpsd.fix.latitude != "n/a" and initialLatitude == 0): 
            initialLatitude = gpsd.fix.latitude
         
          if (gpsd.fix.longitude != "n/a" and initialLongitude == 0): 
            initialLongitude = gpsd.fix.longitude

          if (gpsd.utc != "n/a" and initialStartupTime == "" and '-' in gpsd.utc):
            initialStartupTime = gpsd.utc.split('.')[0]

          if (gpsd.utc != "n/a" and '-' in initialStartupTime and '-' in gpsd.utc):
            timeActive = elapsed_time_from(initialStartupTime, gpsd.utc.split('.')[0])

          if isCameraRecording == False:
            timeActive = "OFF"

          distanceTraveled = round(distance( (initialLatitude, initialLongitude), (gpsd.fix.latitude, gpsd.fix.longitude) ),2)

          topOverlayImage = textOverlayCanvas.copy()
          bottomOverlayImage = textOverlayCanvas.copy()

          topText = "Spd: {0:.2f}  Climb:{1:.2f}  Dir: {2}  Sats: {3} Mode: {4}".format(gpsd.fix.speed, gpsd.fix.climb, gpsd.fix.track, len(gpsd.satellites), gpsd.fix.mode)
          drawTopOverlay = ImageDraw.Draw(topOverlayImage)
          drawTopOverlay.text((200, 15), topText, font=font, fill=(255, 0, 255))
          topOverlay.update(topOverlayImage.tobytes())

          bottomText = "Alt: {0}m  Loc: {1:.5f}, {2:.5f}   Home: {3}m    Rec: {4}".format(gpsd.fix.altitude,gpsd.fix.latitude, gpsd.fix.longitude, distanceTraveled, timeActive)
          drawBottomOverlay = ImageDraw.Draw(bottomOverlayImage)
          drawBottomOverlay.text((50, 20), bottomText, font=font, fill=(255, 255, 255))
          bottomOverlay.update(bottomOverlayImage.tobytes())

          secondsRecorded = secondsRecorded + 1

          if isCameraRecording == True:
            camera.wait_recording(1)

            if secondsRecorded > 10: 
              camera.stop_recording()
              isCameraRecording = False 

          else: 
            time.sleep(1)

   except KeyboardInterrupt:
      gpsp.running = False
      gpsp.join()
      camera.remove_overlay(topOverlay)
      camera.remove_overlay(bottomOverlay)
      camera.remove_overlay(crosshairOverlay)
      if isCameraRecording:
        camera.stop_recording() 

      print "Cancelled"

   finally:
      gpsp.running = False
      gpsp.join()
      camera.remove_overlay(topOverlay)
      camera.remove_overlay(bottomOverlay)
      camera.remove_overlay(crosshairOverlay)
      if isCameraRecording:
        camera.stop_recording() 

