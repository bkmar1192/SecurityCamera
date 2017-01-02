#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2014, Perceptive Automation, LLC. All rights reserved.
# http://www.indigodomo.com

import indigo
import os
import sys
import time
import thread
import threading
import subprocess
import datetime
import urllib
import urllib2
import shutil
import math

from datetime import date
from ghpu import GitHubPluginUpdater
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw 
from PIL import ImageChops 
from PIL import ImageEnhance

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

################################################################################
#
# Image Procedures
#
################################################################################

def rmsdiff(im1, im2):
	##################Calculate the root mean square difference of two images
	diff = ImageChops.difference(im1, im2)
	h = diff.histogram()
	sq = (value*((idx%256)**2) for idx, value in enumerate(h))
	sum_of_squares = sum(sq)
	rms = math.sqrt(sum_of_squares/float(im1.size[0] * im1.size[1]))
	return rms

def GetSnapshot(device):
	##################Get single image

	nowtime = datetime.datetime.now()
	displaytime = str(nowtime).split(".")[0]
	CameraName = device.pluginProps["CameraName"]
	labeltext = CameraName + " : " + displaytime
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	CameraDir = MainDir + "/" + CameraName
	OrigImage = CameraDir + "/OrigImage.jpg"
	NoImage = CameraDir + "/NotActive.jpg"
	CameraAddress = device.pluginProps["CameraAddress"]
	URLAddress = "http://" + CameraAddress
	CameraTimeout = device.pluginProps["CameraTimeout"]
	
	#setup image enhancement parameters
	RawImage = device.pluginProps["Raw"]
	CameraRotation = device.pluginProps["CameraRotation"]
	ImageWidth = device.pluginProps["ImageWidth"]
	ImageHeight = device.pluginProps["ImageHeight"]
	BorderWidth = str(device.pluginProps["BorderWidth"])
	BorderColor = device.pluginProps["BorderColor"]
	Brightness = device.pluginProps["Brightness"]
	Contrast = device.pluginProps["Contrast"]
	Sharpness = device.pluginProps["Sharpness"]

	ImageFound = True
	try:
		urllib.urlretrieve(URLAddress, OrigImage)
		device.updateStateOnServer("CameraState", value="On")
	except:
		ImageFound = False
	
	if ImageFound:
		if str(RawImage) == "False":
			#get image
			img = Image.open(OrigImage)
			#Resize image
			img = img.resize((int(ImageWidth), int(ImageHeight)-15))
			#rotate image
			img = img.rotate(int(CameraRotation))
			#brighten image
			enhancer = ImageEnhance.Brightness(img)
			img = enhancer.enhance(float(Brightness))
			#contrast image
			enhancer = ImageEnhance.Contrast(img)
			img = enhancer.enhance(float(Contrast))
			#sharpen image
			enhancer = ImageEnhance.Sharpness(img)
			img = enhancer.enhance(float(Sharpness))

			#Create label border
			old_size = img.size
			new_size = (old_size[0], old_size[1]+15)
			new_img = Image.new("RGB", new_size, "grey")
			#Add label text 
			draw = ImageDraw.Draw(new_img)
			font = ImageFont.truetype("Verdana.ttf", 8)
			draw.text((5, old_size[1]+3),labeltext,(255,255,255),font=font)
			#Add image to label
			new_img.paste(img, (0,0))	
		
			if int(BorderWidth) > 0:
				old_size = new_img.size
				#Create border
				borderedge = int(BorderWidth)*2
				new_size = (old_size[0]+borderedge, old_size[1]+borderedge)
				final_img = Image.new("RGB", new_size, BorderColor) 
				#Add image to border
				final_img.paste(new_img, (int(BorderWidth),int(BorderWidth)))
			else:
			#Save image without border
				final_img = new_img
		else:
			final_img = Image.open(OrigImage)
	else:
		final_img = Image.open(OrigImage)
		#offline code
	
	return final_img

def GetImage(device):
	##################Capture image for video
	
	#Update Threadcount
	localPropsCopy = device.pluginProps
	localPropsCopy["ImageThreads"] = "1"
	device.replacePluginPropsOnServer(localPropsCopy)
	
	CameraName = device.pluginProps["CameraName"]
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	CameraDir = MainDir + "/" + CameraName
	CurrentImage = CameraDir + "/CurrentImage.jpg"
	NewImage = CameraDir + "/00001.jpg"
	
	img = GetSnapshot(device)
	
	for num in reversed(range(1, 20)):
		fromfile = "0000" + str(num)
		fromfile = CameraDir + "/" + fromfile[-5:] + ".jpg"
		tofile = "0000" + str(num+1)
		tofile = CameraDir + "/" + tofile[-5:] + ".jpg"
		if os.path.isfile(fromfile):
			os.rename(fromfile, tofile)	

	#Save image
	width, height = img.size
	try:
		img.save(CurrentImage,optimize=True,quality=75)
	except Exception as errtxt:
		indigo.server.log(CameraName + ": error saving current image: w" + str(width) + " h" + str(height))
	
	try:
		img.save(NewImage,optimize=True,quality=75)
	except Exception as errtxt:
		indigo.server.log(CameraName + ": error saving 001 image")
	
	#Update Threadcount
	localPropsCopy["ImageThreads"] = "0"
	device.replacePluginPropsOnServer(localPropsCopy)

def MotionCheck(device):
	##################Check for motion

	#Update Threadcount
	localPropsCopy = device.pluginProps
	localPropsCopy["MotionThreads"] = "1"
	device.replacePluginPropsOnServer(localPropsCopy)

	#variable setup
	MaxSensitivity = float(device.pluginProps["MaxSensitivity"])
	MinSensitivity = float(device.pluginProps["MinSensitivity"])
	FramesDifferent = int(device.pluginProps["FramesDifferent"])
	MotionReset = int(device.pluginProps["MotionReset"])
	CameraName = device.pluginProps["CameraName"]
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	CameraDir = MainDir + "/" + CameraName
	CheckMotion = device.pluginProps["CheckMotion"]

	#Set images
	img1 = Image.open(CameraDir + "/CurrentImage.jpg")
	img2 = Image.open(CameraDir + "/00007.jpg")
	ImageDiff = rmsdiff(img1,img2)

	#Average image difference
	ImageAveDiff = device.states["ImageAveDiff"]
	if ImageAveDiff == "":
		ImageAveDiff = "0"
		device.updateStateOnServer("ImageAveDiff", value=0)
	ImageAveDiff = float(ImageAveDiff)
	FramesDiff = device.states["FramesDiff"]

	#Check for change or update average
	if ImageDiff > 0:
		DiffFromAve = float(ImageDiff - ImageAveDiff)
		DiffFromAve = round(DiffFromAve,4)
		device.updateStateOnServer("PixelDiff", value=DiffFromAve)

		if MinSensitivity <= DiffFromAve <= MaxSensitivity:
			FramesDiff = FramesDiff + 1
			device.updateStateOnServer("FramesDiff", value=FramesDiff)
		elif float(ImageDiff) <= float(ImageAveDiff)+10:
			ImageNewAve = round(float(((ImageAveDiff*10) + ImageDiff)/11),4)
			device.updateStateOnServer("ImageAveDiff", value=ImageNewAve)
			device.updateStateOnServer("FramesDiff", value=0)
			MotionSeconds = device.states["MotionSeconds"] + 1
			device.updateStateOnServer("MotionSeconds", value=MotionSeconds)
	else:
		indigo.server.log("Motion Check: " + str(ImageNewAve))
		device.updateStateOnServer("ImageAveDiff", value="0")
		device.updateStateOnServer("MotionSeconds", value=0)

	if CheckMotion:
		#Add label
		imgsize = img1.size
		draw = ImageDraw.Draw(img1)
		font = ImageFont.truetype("Verdana.ttf", 8)
		draw.text(((imgsize[0]-75), (imgsize[1]-15)),str(DiffFromAve),(255,255,255),font=font)
		img1.save(CameraDir + "/CurrentImage.jpg")
		img1.save(CameraDir + "/00001.jpg")
		
	if int(FramesDiff) >= int(FramesDifferent):
		device.updateStateOnServer("MotionDetected", value="true")
		device.updateStateOnServer("MotionSeconds", value=0)
	
	if int(MotionSeconds) >= int(MotionReset):
		device.updateStateOnServer("MotionDetected", value="false")
		
	#Update Threadcount
	localPropsCopy["MotionThreads"] = "0"
	device.replacePluginPropsOnServer(localPropsCopy)
	
def GetMosaic(device):
	##################Create tiled version of last 6 images

	SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	CameraName = device.pluginProps["CameraName"]
	CameraDir = CameraDir = MainDir + "/" + CameraName
	MosaicImage = SnapshotDir + "/mosaic.jpg"
	
	img1 = Image.open(CameraDir + "/00003.jpg")
	img2 = Image.open(CameraDir + "/00004.jpg")
	img3 = Image.open(CameraDir + "/00005.jpg")
	img4 = Image.open(CameraDir + "/00006.jpg")
	img5 = Image.open(CameraDir + "/00007.jpg")
	img6 = Image.open(CameraDir + "/00008.jpg")
	
	#Create mosaic back ground
	mosaic_size = img1.size
	mosaic_size = (mosaic_size[0]*2, (mosaic_size[1]*3))
	mosaic_img = Image.new("RGB", mosaic_size, "white")

	#copy images into mosaic
	mosaic_img.paste(img1, (0,0))
	mosaic_img.paste(img2, (mosaic_size[0]/2,0))
	mosaic_img.paste(img3, (0,mosaic_size[1]/3))
	mosaic_img.paste(img4, (mosaic_size[0]/2,mosaic_size[1]/3))
	mosaic_img.paste(img5, (0,(mosaic_size[1]/3)*2))
	mosaic_img.paste(img6, (mosaic_size[0]/2,(mosaic_size[1]/3)*2))

	#save mosaic
	mosaic_img.save(MosaicImage)


def MasterImage(sub, thread):
	##################Display a master image of different cameras
	
	DeviceID = int(indigo.activePlugin.pluginPrefs["MasterCamera"])
	PlayRecording = indigo.activePlugin.pluginPrefs["PlayRecording"]
	RecordingFrame = indigo.activePlugin.pluginPrefs["RecordingFrame"]
	RecordingFlag = indigo.activePlugin.pluginPrefs["RecordingFlag"]  
	MasterCameraDevice = indigo.devices[DeviceID]
	MasterCameraName = MasterCameraDevice.pluginProps["CameraName"]
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	MasterCameraDir = MainDir + "/" + MasterCameraName
	MasterRecording = PlayRecording + "/" + RecordingFrame
	
	CurrentImage = MasterCameraDir + "/CurrentImage.jpg"
	RecordingImage = MainDir + "/" + MasterRecording
	MasterImage1 = MainDir + "/Master1.jpg"
	MasterImage2 = MainDir + "/Master2.jpg"
	MasterImage3 = MainDir + "/Master3.jpg"

	if str(RecordingFlag) == "1":
		FileFrom = RecordingImage
	else:
		FileFrom = CurrentImage	
	
	try:
		ChangeFile(FileFrom, MasterImage1)
		ChangeFile(CurrentImage, MasterImage2)
		ChangeFile(RecordingImage, MasterImage3)
	except Exception as errtxt:
		indigo.server.log("Master: " + str(errtxt))

def ChangeFile(FromFile, ToFile):
	##################Change dynamic link
	LinkCommand = "ln -s -f \"" + FromFile + "\" \"" + ToFile + "\""
	proc = subprocess.Popen(LinkCommand, stdout=subprocess.PIPE, shell=True)
	(output, err) = proc.communicate()
	
def RunCarousel(CarouselCamera):
	##################Run Carousel
	
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	ToggleCarousel = indigo.activePlugin.pluginPrefs["CarouselOn"]
	CarouselTimer = indigo.activePlugin.pluginPrefs["CarouselTimer"]
	CarouselTimer = int(CarouselTimer) + 1
	
	if int(CarouselTimer) >= 4 and ToggleCarousel == "true":
		CarouselTimer = 0
		CarouselCount = int(indigo.activePlugin.pluginPrefs["CarouselCount"])
		indigo.activePlugin.pluginPrefs["CarouselCount"] = CarouselCount + 1
		
	indigo.activePlugin.pluginPrefs["CarouselTimer"] = str(CarouselTimer)
	CurrentImage = MainDir + "/" + CarouselCamera + "/CurrentImage.jpg"
	CarouselImage = MainDir + "/CarouselImage.jpg"	
			
	try:
		ChangeFile (CurrentImage, CarouselImage)
	except:
		indigo.server.log("Carousel Image: " + str(CarouselCount))

################################################################################
#
# Start up Procedures
#
################################################################################

class Plugin(indigo.PluginBase):
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		self.updater = GitHubPluginUpdater(self)

	def __del__(self):
		indigo.PluginBase.__del__(self)

	def startup(self):
		self.debugLog(u"startup called")
		
		indigo.server.log("Checking for update")
		ActiveVersion = str(self.pluginVersion)
		CurrentVersion = str(self.updater.getVersion())
		if ActiveVersion == CurrentVersion:
			indigo.server.log("Running the current version of Security Camera")
		else:
			indigo.server.log("The current version of Security Camera is " + str(CurrentVersion) + " and the running version " + str(ActiveVersion) + ".")
		
		SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]

		indigo.activePlugin.pluginPrefs["MasterThreads"] = "0"
		indigo.activePlugin.pluginPrefs["CarouselCount"] = "0"		
		indigo.activePlugin.pluginPrefs["CarouselTimer"] = "0"	
		
		#clear Thread Count
		for sdevice in indigo.devices.iter("self"):
			CameraName = sdevice.pluginProps["CameraName"]
			localPropsCopy = sdevice.pluginProps
			localPropsCopy["ImageThreads"] = "0"
			localPropsCopy["MotionThreads"] = "0"
			sdevice.replacePluginPropsOnServer(localPropsCopy)
		
		MainDirTest = os.path.isdir(MainDir)
		if MainDirTest is False:
			indigo.server.log("Home image directory not found.")
			os.makedirs(MainDir)
			indigo.server.log("Created: " + MainDir)
			
		SnapshotDirTest = os.path.isdir(SnapshotDir)
		if SnapshotDirTest is False:
			indigo.server.log("Snapshot image directory not found.")
			os.makedirs(SnapshotDir)
			indigo.server.log("Created: " + SnapshotDir)

	def shutdown(self):
		self.debugLog(u"shutdown called")

	def validatePrefsConfigUi(self, valuesDict):
		MainDir = valuesDict["MainDirectory"]
		ArchiveDir = MainDir + "/Archive"
		
		MainDirTest = os.path.isdir(MainDir)		
		if MainDirTest is False:
			indigo.server.log("Home image directory not found.")
			os.makedirs(MainDir)
			indigo.server.log("Created: " + MainDir)

		ArchiveDirTest = os.path.isdir(ArchiveDir)			
		if ArchiveDirTest is False:
			indigo.server.log("Archive image directory not found.")
			os.makedirs(ArchiveDir)
			indigo.server.log("Created: " + ArchiveDir)
		return True

	def deviceStartComm(self, dev):
		dev.stateListOrDisplayStateIdChanged()
	
		localPropsCopy = dev.pluginProps
		CameraName = dev.pluginProps["CameraName"]
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		IMDir = indigo.activePlugin.pluginPrefs["IMDirectory"]
		CameraDir = MainDir + "/" + CameraName
		NotActiveImage = CameraDir + "/NotActive.jpg"

		CameraDirTest = os.path.isdir(CameraDir)		
		if CameraDirTest is False:
			indigo.server.log("Camera image directory not found.")
			os.makedirs(CameraDir)
			indigo.server.log("Created: " + CameraDir)
		if dev.states["CameraState"] != "Off":
			dev.updateStateOnServer("CameraState", value="On")
		
		NotActiveImageTest = os.path.isfile(NotActiveImage)
		if NotActiveImageTest is False:
			img = Image.new("RGB", (200, 200), "grey")
			draw = ImageDraw.Draw(img)
			font = ImageFont.truetype("Verdana.ttf", 24)
			center = 100 - ((len(CameraName)*13)/2)
			draw.text((center, 75),CameraName,(255,255,255),font=font)
			center = 100 - ((len("Not Active")*12)/2)
			draw.text((center, 100),"Not Active",(255,255,255),font=font)
			img.save(NotActiveImage)
			indigo.server.log("Created Not Active Image")	
		return True


################################################################################
#
# Main looping thread
#
################################################################################

	def runConcurrentThread(self):
		try:
			while True:
				self.sleep(1)
				
				#Debug Mode
				DebugMode = indigo.activePlugin.pluginPrefs["Debug"]
				self.debug = DebugMode	
				self.debugLog("Starting main loop")
				
				################################################################################
				#
				# Setup
				#
				################################################################################
				
				MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
				RecordingCount = int(indigo.activePlugin.pluginPrefs["RecordingCount"])
				
				#set record loop frame
				if RecordingCount <= 2:
					RecordingCount = 20
				else:
					RecordingCount = RecordingCount - 1
					
				RecordingFrame = "00000" + str(RecordingCount)
				RecordingFrame = RecordingFrame[-5:] + ".jpg"
				indigo.activePlugin.pluginPrefs["RecordingFrame"] = RecordingFrame
				indigo.activePlugin.pluginPrefs["RecordingCount"] = RecordingCount		
										
				#Create camera device list
				alist = []
				for sdevice in indigo.devices.iter("self"):
					alist.append(sdevice.pluginProps["CameraName"] )
				
				################################################################################
				#
				# Create image carousel
				#
				################################################################################
	
				CarouselCount = int(indigo.activePlugin.pluginPrefs["CarouselCount"])
				MaxCarouselCount = len(alist)
				
				if CarouselCount >= MaxCarouselCount-1:
					indigo.activePlugin.pluginPrefs["CarouselCount"] = 0
				
				CarouselCamera = alist[CarouselCount]
				RunCarousel(CarouselCamera)
				
				################################################################################
				#
				# Set Master Image
				#
				################################################################################
				
				MasterID = int(indigo.activePlugin.pluginPrefs["MasterCamera"])
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
				if MasterID != "":
=======
				if MasterID != 0:
>>>>>>> master
=======
				if MasterID != 0:
>>>>>>> master
=======
				if MasterID != 0:
>>>>>>> master
					MasterImage("Master", "Thread")
				
				################################################################################
				#
				# Start device loop
				#
				################################################################################
				
				for device in indigo.devices.iter("self"):
					
					CameraState = device.states["CameraState"]
					CameraTimeout = int(device.pluginProps["CameraTimeout"])
					OfflineSeconds = int(device.states["OfflineSeconds"])
					ImageThreadCount = int(device.pluginProps["ImageThreads"])
					MotionThreadCount = int(device.pluginProps["MotionThreads"])
					MotionThreadSeconds = int(device.pluginProps["MotionThreadSeconds"])
					MotionOff = device.pluginProps["MotionOff"]
					localPropsCopy = device.pluginProps
					
					#Set State Timers
					if device.states["RecordSeconds"] > 3600:
						RecordSeconds = 0
						device.updateStateOnServer("RecordSeconds", value=0)
					else:
						RecordSeconds = device.states["RecordSeconds"] + 1
						device.updateStateOnServer("RecordSeconds", value=RecordSeconds)
					
					if str(CameraState) != "Off":
						#Get Images
						if ImageThreadCount <= 0:
							device.updateStateOnServer("OfflineSeconds", value="0")
							threadid = thread.start_new_thread( GetImage, (device,))
						else:
							OfflineSeconds += 1
							device.updateStateOnServer("OfflineSeconds", value=str(OfflineSeconds))
							localPropsCopy["OfflineSeconds"] = str(OfflineSeconds)
							device.replacePluginPropsOnServer(localPropsCopy)
							if OfflineSeconds >= CameraTimeout:
								localPropsCopy = device.pluginProps
								localPropsCopy["ImageThreads"] = "0"
								localPropsCopy["OfflineSeconds"] = "0"
								device.replacePluginPropsOnServer(localPropsCopy)
								device.updateStateOnServer("CameraState", value="Unavailable")
						
						#Check Motion
						if str(MotionOff) == "False":
							if MotionThreadCount <= 0:
								threadid = thread.start_new_thread( MotionCheck, (device,))
							else:
								MotionThreadSeconds += 1
								localPropsCopy["MotionThreadSeconds"] = str(MotionThreadSeconds)
								device.replacePluginPropsOnServer(localPropsCopy)
								if MotionThreadSeconds >= 10:
									localPropsCopy = device.pluginProps
									localPropsCopy["MotionThreads"] = "0"
									localPropsCopy["MotionThreadSeconds"] = "0"
									device.replacePluginPropsOnServer(localPropsCopy)
								
		
		except self.StopThread:
			pass

################################################################################
#
# Plugin menus
#
################################################################################

	def checkForUpdate(self):
		ActiveVersion = str(self.pluginVersion)
		CurrentVersion = str(self.updater.getVersion())
		if ActiveVersion == CurrentVersion:
			indigo.server.log("Running the most recent version of Security Camera")
		else:
			indigo.server.log("The current version of Security Camera is " + str(CurrentVersion) + " and the running version " + str(ActiveVersion) + ".")
		
	def updatePlugin(self):
		ActiveVersion = str(self.pluginVersion)
		CurrentVersion = str(self.updater.getVersion())
		if ActiveVersion == CurrentVersion:
			indigo.server.log("Already running the most recent version of Security Camera")
		else:
			indigo.server.log("The current version of Security Camera is " + str(CurrentVersion) + " and the running version " + str(ActiveVersion) + ".")
			self.updater.update()
    	
################################################################################
#
# Plugin actions
#
################################################################################
	
	def StopCamera(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		indigo.server.log("Stop Camera action called:" + CameraName)
		CameraDevice.updateStateOnServer("CameraState", value="Off")
		
	def StartCamera(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		indigo.server.log("Start Camera action called:" + CameraName)
		CameraDevice.updateStateOnServer("CameraState", value="On")
		
	def ToggleCamera(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		CameraState = CameraDevice.states["CameraState"]
		if CameraState == "On":
			indigo.server.log("Stop Camera action called:" + CameraName)
			CameraDevice.updateStateOnServer("CameraState", value="Off")
		else:
			indigo.server.log("Start Camera action called:" + CameraName)
			CameraDevice.updateStateOnServer("CameraState", value="On")
		
	def MasterCamera(self, pluginAction):
		indigo.activePlugin.pluginPrefs["MasterCamera"] = pluginAction.deviceId
		indigo.activePlugin.pluginPrefs["RecordingFlag"] = 0
		MasterImage("Master", "Thread")

	def RecordCamera(self, pluginAction):
		
		time.sleep(2)
	
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		CameraDevice.updateStateOnServer("RecordSeconds", value=0)
		SavedDir = time.strftime("%m %d %Y %H.%M.%S")
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		SourceDir = MainDir + "/" + CameraName
		RecordingDir = MainDir + "/" + CameraName + "/" + SavedDir
		
		os.makedirs(RecordingDir)
		src_files = os.listdir(SourceDir)
		for file_name in src_files:
			full_file_name = os.path.join(SourceDir, file_name)
    			if (os.path.isfile(full_file_name)):
    				try:
        				shutil.copy(full_file_name, RecordingDir)
        			except Exception as errtxt:
						self.debugLog(str(errtxt))
		
		CurrentImage = RecordingDir + "/00003.jpg"
		
		for num in reversed(range(2, 10)):
			LeadingNum = "0" + str(num)
			Current = LeadingNum[-2:]
			LeadingPrev = "0" + str(num - 1)
			Previous = LeadingPrev[-2:]
			PrevValue = CameraDevice.states["Recording" + Previous]
			CameraDevice.updateStateOnServer("Recording" + Current, value=PrevValue)
			ThumbTo = SourceDir +"/thumb" + Current + ".jpg"
			ThumbFrom = SourceDir +"/thumb" + Previous + ".jpg"
			try:
				os.rename(ThumbFrom, ThumbTo)	
			except Exception as errtxt:
				self.debugLog(str(errtxt))
				
		CurrentThumb = SourceDir + "/Thumb01.jpg"
		shutil.copy (CurrentImage, CurrentThumb)
		CameraDevice.updateStateOnServer("Recording01", value=SavedDir)
		
	def ToggleCarousel(self, pluginAction):
		ToggleCarousel = indigo.activePlugin.pluginPrefs["CarouselOn"]
		if ToggleCarousel == "true":
			indigo.activePlugin.pluginPrefs["CarouselOn"] = "false"
		else:
			indigo.activePlugin.pluginPrefs["CarouselOn"] = "true"

	def PlayRecording(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		RecordingID = pluginAction.props["PlaySelect"]
		Recording = CameraName + "/" + CameraDevice.states["Recording" + RecordingID]
		
		indigo.activePlugin.pluginPrefs["RecordingFlag"] = 1
		indigo.activePlugin.pluginPrefs["PlayRecording"] = Recording
		indigo.server.log("Play recording action called:" + CameraName)
		
	def Snapshot(self, pluginAction):
		device = indigo.devices[pluginAction.deviceId]
		SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
		SnapshotImage = SnapshotDir + "/Snap001.jpg"
		
		final_img = GetSnapshot(device)
		
		#save image history
		for num in reversed(range(1, 5)):
			fromfile = "Snap00" + str(num)
			fromfile = SnapshotDir + "/" + fromfile + ".jpg"
			tofile = "Snap00" + str(num+1)
			tofile = SnapshotDir + "/" + tofile + ".jpg"
			if os.path.isfile(fromfile):
				os.rename(fromfile, tofile)	

		try:		
			final_img.save(SnapshotImage)
		except Exception as errtxt:
			self.debugLog(str(errtxt))
		
	def Mosaic(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		GetMosaic(CameraDevice)
		
	def CameraCommand(self, pluginAction):
		ReturnVariable = pluginAction.props["ReturnVariable"]
		CameraCommandURL = pluginAction.props["CameraCommandURL"]
		ReturnVariable = ReturnVariable.replace(" ", "_")
		
		try:
			ReturnVar = indigo.variables[ReturnVariable]
		except Exception as errtxt:
			indigo.server.log(str(errtxt))
			indigo.variable.create(ReturnVariable)
			indigo.server.log(ReturnVariable + " created")
			
		returnvalue = urllib.urlretrieve(CameraCommandURL)
		indigo.variable.updateValue(ReturnVariable, value=str(returnvalue))

		
	def DeleteRecording(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		Months = pluginAction.props["DeleteMonths"]
		Days = int(Months) * 30
		#Days = 4
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		ArchiveDir = MainDir + "/" + "Archive" + "/" + CameraName
		
		OldDirs = []
		today = date.today()
		StartPath = MainDir + "/" + CameraName

		for root, dirs, files in os.walk(StartPath):
			for FileName in dirs:
				filedate = date.fromtimestamp(os.path.getmtime(os.path.join(root, FileName)))
				if (today - filedate).days >= Days:
					CurrentDir =  StartPath + "/" + FileName                                         
					shutil.copytree(CurrentDir,ArchiveDir+ "/" + FileName)
					shutil.rmtree(CurrentDir)
					
		indigo.server.log("Archived videos older than " + Months + " months:" + CameraName)
