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
import subprocess
import datetime
from datetime import date
import urllib
import base64
import os
import shutil
import smtplib
#from ghpu import GitHubPluginUpdater

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

# Capture Image
def GetImage(IMDir, CameraAddress, CameraPath, CameraDir, CameraRotation, device):

	#Track open threads
	ThreadCount2 = int(device.pluginProps["ImageThreads"])+1
	device.pluginProps["ImageThreads"] = str(ThreadCount2)

	nowtime = datetime.datetime.now()
	displaytime = str(nowtime).split(".")[0]
	OrigImage = CameraDir + "/OrigImage.jpg"
	NewImage = CameraDir + "/00001.jpg"
	CurrentImage = CameraDir + "/CurrentImage.jpg"
	NoImage = CameraDir + "/NotActive.jpg"
	CameraTimeout = device.pluginProps["CameraTimeout"]
	
	URLAddress = CameraPath

	#setup image enhancement parameters
	ImageWidth = device.pluginProps["ImageWidth"]
	ImageHeight = device.pluginProps["ImageHeight"]
	BorderWidth = str(device.pluginProps["BorderWidth"])
	BorderColor = device.pluginProps["BorderColor"]
	AutoLevel = device.pluginProps["AutoLevel"]
	Normalize = device.pluginProps["Normalize"]
	Enhance = device.pluginProps["Enhance"]
	
	Border = ""
	
	if int(BorderWidth) > 0:
		Border = "-bordercolor " + BorderColor + " -border " + BorderWidth

	#indigo.server.log(Border)

	Options = ""
	
	if AutoLevel:
		Options = Options + "-auto-level "
		
	if Normalize:
		Options = Options + "-normalize "
		
	if Enhance:
		Options = Options + "-enhance "	

	try:
		urllib.urlretrieve(URLAddress, OrigImage)
		ImageFound = True
		device.updateStateOnServer("CameraState", value="On")
		device.updateStateOnServer("OfflineSeconds", value=0)
	except:
		OfflineSeconds = device.states["OfflineSeconds"] + 1
		device.updateStateOnServer("OfflineSeconds", value=OfflineSeconds)
		ImageFound = False
	
	if ImageFound:
		RotateImage = IMDir + "convert \"" + OrigImage + "\" -interlace Plane " + Options + "-rotate " + str(CameraRotation) + " -resize " + str(ImageWidth) + "x" + str(ImageHeight) + " " + Border +  " -background Grey  label:\"" + displaytime + "\" -gravity Center -append \"" + NewImage + "\""
	
		#indigo.server.log(RotateImage)
	
		#Rotate and resize Image			
		proc = subprocess.Popen(RotateImage, stdout=subprocess.PIPE, shell=True)
		(output, err) = proc.communicate()

		shutil.copy (NewImage, CurrentImage)
	
		#save image history
		for num in reversed(range(1, 20)):
			fromfile = "0000" + str(num)
			fromfile = CameraDir + "/" + fromfile[-5:] + ".jpg"
		
			tofile = "0000" + str(num+1)
			tofile = CameraDir + "/" + tofile[-5:] + ".jpg"
		
			if os.path.isfile(fromfile):
				os.rename(fromfile, tofile)	
	else:
		if OfflineSeconds >= int(CameraTimeout):
			shutil.copy (NoImage, CurrentImage)
	
	#Update Threadcount
	ThreadCount2 = int(device.pluginProps["ImageThreads"])-1
	device.pluginProps["ImageThreads"] = str(ThreadCount2)

def MotionCheck(CameraDir, IMDir, device):

	#Update Threadcount
	ThreadCount2 = int(device.pluginProps["MotionThreads"])+1
	device.pluginProps["MotionThreads"] = str(ThreadCount2)

	#variable setup
	MaxSensitivity = float(device.pluginProps["MaxSensitivity"])
	MinSensitivity = float(device.pluginProps["MinSensitivity"])
	FramesDifferent = int(device.pluginProps["FramesDifferent"])
	MotionReset = int(device.pluginProps["MotionReset"])
	CameraName = device.pluginProps["CameraName"]
	CheckMotion = device.pluginProps["CheckMotion"]

	#Motion detection
	#Get differences between images
	Compare1 = CameraDir + "/00002.jpg"
	Compare2 = CameraDir + "/00007.jpg"
	NewCompare = CameraDir + "/Compare.jpg"
	newProps = device.pluginProps
	Compare = IMDir + "compare -metric RMSE \"" + Compare1 + "\" \"" + Compare2 + "\" null: 2>&1"
	
	proc = subprocess.Popen(Compare, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
	(output, err) = proc.communicate()	
	
	#Current image difference
	ImageDiff = str(output)
	ImageDiff = ImageDiff[int(ImageDiff.index("("))+1:int(ImageDiff.index(")"))-1]
	ImageDiff = round(float(ImageDiff),4)

	#Average image difference
	ImageAveDiff = device.states["ImageAveDiff"]
	if ImageAveDiff == "":
		ImageAveDiff = "0"
		device.updateStateOnServer("ImageAveDiff", value=0)
	ImageAveDiff = float(ImageAveDiff)
	FramesDiff = device.states["FramesDiff"]
	CameraName = device.pluginProps["CameraName"]

	#Check for change or update average
	if ImageDiff > 0:
		DiffFromAve = float(ImageDiff - ImageAveDiff)
		DiffFromAve = round(DiffFromAve,4)
		device.updateStateOnServer("PixelDiff", value=DiffFromAve)
		
		if CheckMotion:
			indigo.server.log(str(FramesDiff) + " - " + str(MinSensitivity) + "<=" + str(DiffFromAve) + "<=" + str(MaxSensitivity) + " = " + str(MinSensitivity <= DiffFromAve <= MaxSensitivity))

		if MinSensitivity <= DiffFromAve <= MaxSensitivity:
			FramesDiff = FramesDiff + 1
			device.updateStateOnServer("FramesDiff", value=FramesDiff)
		else:
			ImageNewAve = round(float(((ImageAveDiff*4) + ImageDiff)/5),4)
			device.updateStateOnServer("ImageAveDiff", value=ImageNewAve)
			device.updateStateOnServer("FramesDiff", value=0)
			MotionSeconds = device.states["MotionSeconds"] + 1
			device.updateStateOnServer("MotionSeconds", value=MotionSeconds)
	
	else:
		indigo.server.log(str(ImageNewAve))
		device.updateStateOnServer("ImageAveDiff", value="0")
		device.updateStateOnServer("MotionSeconds", value=0)
		
	if int(FramesDiff) >= int(FramesDifferent):
		device.updateStateOnServer("MotionDetected", value="true")
		device.updateStateOnServer("MotionSeconds", value=0)
	
	if int(MotionSeconds) >= int(MotionReset):
		device.updateStateOnServer("MotionDetected", value="false")
		
	#Update Threadcount
	ThreadCount2 = int(device.pluginProps["MotionThreads"])-1
	device.pluginProps["MotionThreads"] = str(ThreadCount2)

def GetMosaic(device):

	#montage 00002.jpg 00003.jpg 00004.jpg 00005.jpg 00006.jpg 00007.jpg -geometry 384x256+3+3 montage.jpg

	IMDir = indigo.activePlugin.pluginPrefs["IMDirectory"]
	SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	CameraPath = "http://" + device.pluginProps["CameraAddress"]
	CameraRotation = device.pluginProps["CameraRotation"]
	CameraName = device.pluginProps["CameraName"]
	CameraDir = CameraDir = MainDir + "/" + CameraName
	MontageImage = SnapshotDir + "/mosaic.jpg"
	
	Image1 = CameraDir + "/00002.jpg"
	Image2 = CameraDir + "/00003.jpg"
	Image3 = CameraDir + "/00004.jpg"
	Image4 = CameraDir + "/00005.jpg"
	Image5 = CameraDir + "/00006.jpg"
	Image6 = CameraDir + "/00007.jpg"

	MontageImage = IMDir + "montage \"" + Image6 + "\" \"" + Image5 + "\" \"" + Image4 + "\" \"" + Image3 + "\" \"" + Image2 + "\" \"" + Image1 + "\" -tile 2x3 -geometry 350x200 \"" + MontageImage + "\" "
		
	#Rotate and resize Image			
	proc = subprocess.Popen(MontageImage, stdout=subprocess.PIPE, shell=True)
	(output, err) = proc.communicate()

def GetSnapshot(device):

	IMDir = indigo.activePlugin.pluginPrefs["IMDirectory"]
	SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	CameraPath = "http://" + device.pluginProps["CameraAddress"]
	CameraRotation = device.pluginProps["CameraRotation"]
	CameraName = device.pluginProps["CameraName"]
	CameraDir = CameraDir = MainDir + "/" + CameraName

	nowtime = datetime.datetime.now()
	displaytime = str(nowtime).split(".")[0]
	OrigImage = SnapshotDir + "/OrigImage.jpg"
	NewImage = SnapshotDir + "/00001.jpg"
	CurrentImage = SnapshotDir + "/CurrentImage.jpg"
	NoImage = CameraDir + "/NotActive.jpg"
	
	URLAddress = CameraPath

	#setup image enhancement parameters
	ImageWidth = device.pluginProps["ImageWidth"]
	ImageHeight = device.pluginProps["ImageHeight"]
	BorderWidth = str(device.pluginProps["BorderWidth"])
	BorderColor = device.pluginProps["BorderColor"]
	AutoLevel = device.pluginProps["AutoLevel"]
	Normalize = device.pluginProps["Normalize"]
	Enhance = device.pluginProps["Enhance"]
	
	Border = ""
	
	if int(BorderWidth) > 0:
		Border = "-bordercolor " + BorderColor + " -border " + BorderWidth

	#indigo.server.log(Border)

	Options = ""
	
	if AutoLevel:
		Options = Options + "-auto-level "
		
	if Normalize:
		Options = Options + "-normalize "
		
	if Enhance:
		Options = Options + "-enhance "	

	try:
		urllib.urlretrieve(URLAddress, OrigImage)
		ImageFound = True
	except:
		shutil.copy (NoImage, CurrentImage)
		ImageFound = False
	
	if ImageFound:
		RotateImage = IMDir + "convert \"" + OrigImage + "\" -interlace Plane " + Options + "-rotate " + str(CameraRotation) + " -resize " + str(ImageWidth) + "x" + str(ImageHeight) + " " + Border + " -font Arial -pointsize 20 -draw \"gravity north fill black  text 0,12 '" + displaytime + "' fill yellow  text 1,11 '" + displaytime + "'\" \"" + NewImage + "\""
		
		#Rotate and resize Image			
		proc = subprocess.Popen(RotateImage, stdout=subprocess.PIPE, shell=True)
		(output, err) = proc.communicate()

	shutil.copy (NewImage, CurrentImage)
	
	#save image history
	for num in reversed(range(1, 20)):
		fromfile = "0000" + str(num)
		fromfile = SnapshotDir + "/" + fromfile[-5:] + ".jpg"
		
		tofile = "0000" + str(num+1)
		tofile = SnapshotDir + "/" + tofile[-5:] + ".jpg"
		
		if os.path.isfile(fromfile):
			os.rename(fromfile, tofile)	

def MasterImage(RecordingFlag, MasterRecording, MasterCameraDir, MainDir, MasterCameraName):

	#Set master image	
	ThreadCount2 = int(indigo.activePlugin.pluginPrefs["MasterThreads"])+1
	indigo.activePlugin.pluginPrefs["MasterThreads"] = str(ThreadCount2)
	
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
	except:
		pass

	ThreadCount2 = int(indigo.activePlugin.pluginPrefs["MasterThreads"])-1
	indigo.activePlugin.pluginPrefs["MasterThreads"] = str(ThreadCount2)

def ChangeFile(FromFile, ToFile):
	#Update Symbolic Link
	LinkCommand = "ln -s -f \"" + FromFile + "\" \"" + ToFile + "\""
	
	proc = subprocess.Popen(LinkCommand, stdout=subprocess.PIPE, shell=True)
	(output, err) = proc.communicate()


################################################################################
class Plugin(indigo.PluginBase):
	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		#self.updater = GitHubPluginUpdater(self)

	def __del__(self):
		indigo.PluginBase.__del__(self)

	########################################
	def startup(self):
		self.debugLog(u"startup called")
		#self.updater.checkForUpdate()
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		MainDirTest = os.path.isdir(MainDir)
		indigo.activePlugin.pluginPrefs["MasterThreads"] = "0"
		if MainDirTest is False:
			indigo.server.log("Home image directory not found.")
			os.makedirs(MainDir)
			indigo.server.log("Created: " + MainDir)
			
		SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
		SnapshotDirTest = os.path.isdir(SnapshotDir)
		if SnapshotDirTest is False:
			indigo.server.log("Snapshot image directory not found.")
			os.makedirs(SnapshotDir)
			indigo.server.log("Created: " + SnapshotDir)

	def shutdown(self):
		self.debugLog(u"shutdown called")

	def validatePrefsConfigUi(self, valuesDict):
		MainDir = valuesDict["MainDirectory"]
		MainDirTest = os.path.isdir(MainDir)
		ArchiveDir = MainDir + "/Archive"
		ArchiveDirTest = os.path.isdir(ArchiveDir)
		if MainDirTest is False:
			indigo.server.log("Home image directory not found.")
			os.makedirs(MainDir)
			indigo.server.log("Created: " + MainDir)
		if ArchiveDirTest is False:
			indigo.server.log("Archive image directory not found.")
			os.makedirs(ArchiveDir)
			indigo.server.log("Created: " + ArchiveDir)
		return True


	def deviceStartComm(self, dev):
		CameraName = dev.pluginProps["CameraName"]
		dev.pluginProps["ImageThreads"] = "0"
		dev.pluginProps["MotionThreads"] = "0"
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		CameraDir = MainDir + "/" + CameraName
		CameraDirTest = os.path.isdir(CameraDir)
		if CameraDirTest is False:
			indigo.server.log("Camera image directory not found.")
			os.makedirs(CameraDir)
			indigo.server.log("Created: " + CameraDir)
		dev.updateStateOnServer("CameraState", value="On")
		
		IMDir = indigo.activePlugin.pluginPrefs["IMDirectory"]
		NotActiveImage = CameraDir + "/NotActive.jpg"
		NotActiveImageTest = os.path.isfile(NotActiveImage)
		if NotActiveImageTest is False:
			#Create Image Not Found
			CreateNotActive = IMDir + "convert -size 200x200 xc:grey -gravity Center -pointsize 30 -annotate 0 \"Offline\" " + "\"" +  NotActiveImage + "\""	
			indigo.server.log(CreateNotActive)	
			proc = subprocess.Popen(CreateNotActive, stdout=subprocess.PIPE, shell=True)
			(output, err) = proc.communicate()
			
		return True


	########################################
	# If runConcurrentThread() is defined, then a new thread is automatically created
	# and runConcurrentThread() is called in that thread after startup() has been called.
	#
	# runConcurrentThread() should loop forever and only return after self.stopThread
	# becomes True. If this function returns prematurely then the plugin host process
	# will log an error and attempt to call runConcurrentThread() again after several seconds.

	# Create two threads as follows

	def runConcurrentThread(self):
		try:
			while True:
				self.sleep(1)
				
				#Debug Mode
				DebugMode = indigo.activePlugin.pluginPrefs["Debug"]
				self.debug = DebugMode	
				
				self.debugLog("Starting Loop")
				
				#set up plugin variable
				MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
				IMDir = indigo.activePlugin.pluginPrefs["IMDirectory"]
				CarouselCount = int(indigo.activePlugin.pluginPrefs["CarouselCount"])
				RecordingCount = int(indigo.activePlugin.pluginPrefs["RecordingCount"])
				RecordingFlag = indigo.activePlugin.pluginPrefs["RecordingFlag"]
				PlayRecording = indigo.activePlugin.pluginPrefs["PlayRecording"]
				
				self.debugLog("Main Dir" + MainDir)
				self.debugLog("Recording Flag" + str(RecordingFlag))
				self.debugLog("Play Recording" + str(RecordingFlag))		
				
				#set record loop frame
				if RecordingCount <= 2:
					RecordingCount = 20
				else:
					RecordingCount = RecordingCount - 1
				RecordingFrame = "00000" + str(RecordingCount)
				RecordingFrame = RecordingFrame[-5:] + ".jpg"
				indigo.activePlugin.pluginPrefs["RecordingFrame"] = RecordingFrame
				indigo.activePlugin.pluginPrefs["RecordingCount"] = RecordingCount		
				
				#Copy Master Image
				MasterThreads = int(indigo.activePlugin.pluginPrefs["MasterThreads"])
				self.debugLog("Start Master Image Copy")
				if MasterThreads == 0:
					DeviceID = int(indigo.activePlugin.pluginPrefs["MasterCamera"])
					self.debugLog(DeviceID)
					MasterCameraDir = ""
					MasterCameraName = ""
					try:
						MasterCameraDevice = indigo.devices[DeviceID]
						MasterCameraName = MasterCameraDevice.pluginProps["CameraName"]
						MasterCameraDir = MainDir + "/" + MasterCameraName
						MasterRecording = PlayRecording + "/" + RecordingFrame
						thread.start_new_thread( MasterImage, (RecordingFlag, MasterRecording, MasterCameraDir, MainDir, MasterCameraName) )
						self.debugLog(MasterCameraDir)
					except:
						self.debugLog("Master Camera image not found.")
					
				#Create camera device list
				#Clear threadcount
				self.debugLog("Camera List Build")
				alist = []
				for sdevice in indigo.devices.iter("self"):
					self.debugLog(sdevice.pluginProps["CameraName"])
					alist.append(sdevice.pluginProps["CameraName"] )

				self.debugLog("Camera List Build Complete")
					
				for device in indigo.devices.iter("self"):
					
					#Set State Timers
					if device.states["RecordSeconds"] > 3600:
						RecordSeconds = 0
					else:
						RecordSeconds = device.states["RecordSeconds"] + 1
						
					OfflineSeconds = device.states["OfflineSeconds"]
					device.updateStateOnServer("RecordSeconds", value=RecordSeconds)
					
					self.debugLog("Start Variable setup")
					
					#set up device variables
					CameraState = device.states["CameraState"]
					CarouselCamera = alist[CarouselCount]
					CameraName = device.pluginProps["CameraName"]
					CameraAddress = device.pluginProps["CameraAddress"]
					#CameraUserName = device.pluginProps["CameraUserName"]
					#CameraPassword = device.pluginProps["CameraPassword"]
					CameraRotation = device.pluginProps["CameraRotation"]
					CameraTimeout = device.pluginProps["CameraTimeout"]
					ImageAveDiff = device.pluginProps["ImageAveDiff"]
					ImageThreadCount = int(device.pluginProps["ImageThreads"])
					MotionThreadCount = int(device.pluginProps["MotionThreads"])
					CameraPath = ""
					
					#UserPwd = CameraUserName + ":" + CameraPassword + "@"
					#if CameraUserName > "":
						#CameraPath = "http://" + UserPwd + CameraAddress
						#device.pluginProps["CameraAddress"] = UserPwd + CameraAddress
						#device.pluginProps["CameraUserName"] = ""
						#device.pluginProps["CameraPassword"] = ""
					#else:
					CameraPath = "http://" + CameraAddress
						
					CameraDir = MainDir + "/" + CameraName
					
					newProps = device.pluginProps
					self.debugLog(CameraPath)
					
					#capture video
					if CameraState != "Off":
						if ImageThreadCount <= 0:
							if int(OfflineSeconds) >= int(CameraTimeout):
								self.debugLog("No image from " + CameraName + " - Retrying")
								device.updateStateOnServer("CameraState", value="Unavailable")
								device.updateStateOnServer("OfflineSeconds", value=0)
							try:
								self.debugLog("Starting image capture thread")
								thread.start_new_thread( GetImage, (IMDir, CameraAddress, CameraPath, CameraDir, CameraRotation, device) )
								if MotionThreadCount == 0:
									thread.start_new_thread(MotionCheck, (CameraDir, IMDir, device))
							except Exception as errtxt:
								self.debugLog(str(errtxt))

				#run the carousel
				ToggleCarousel = indigo.activePlugin.pluginPrefs["CarouselOn"]
				if len(alist) > 0:
					self.debugLog("Running Carousel")
					CarouselTimer = indigo.activePlugin.pluginPrefs["CarouselTimer"]
					if int(CarouselTimer) >= 4 and ToggleCarousel == "true":
						CarouselTimer = 0
						MaxCarouselCount = len(alist)
						CarouselCount = indigo.activePlugin.pluginPrefs["CarouselCount"]
						CarouselCount = int(CarouselCount) + 1
						if int(CarouselCount) >= MaxCarouselCount:
							CarouselCount = 0
						indigo.activePlugin.pluginPrefs["CarouselCount"] = str(CarouselCount)
						indigo.activePlugin.pluginPrefs["CarouselTimer"] = str(CarouselTimer)
					CarouselTimer = int(CarouselTimer) + 1
					CarouselCamera = alist[CarouselCount]
					indigo.activePlugin.pluginPrefs["CarouselTimer"] = str(CarouselTimer)
					CurrentImage = MainDir + "/" + CarouselCamera + "/CurrentImage.jpg"
					CarouselImage = MainDir + "/CarouselImage.jpg"
				else:
					CarouselCount = indigo.activePlugin.pluginPrefs["CarouselCount"]
					CarouselCount = int(CarouselCount) + 1
					indigo.activePlugin.pluginPrefs["CarouselCount"] = str(CarouselCount)
				
				try:
					ChangeFile (CurrentImage, CarouselImage)
				except:
					self.debugLog("Error copying Carousel Image: " + str(CarouselCount))
		
		except self.StopThread:
			pass

	########################################
	# Plugin Actions object callbacks (pluginAction is an Indigo plugin action instance)
	######################
	
	def StopCamera(self, pluginAction):
		#PluginID = pluginAction.items()
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
        			except:
        				pass
		
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
			except:
				pass
		CurrentThumb = SourceDir + "/Thumb01.jpg"
		shutil.copy (CurrentImage, CurrentThumb)
		CameraDevice.updateStateOnServer("Recording01", value=SavedDir)
		indigo.server.log("Record action called:" + CameraName)
		
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
		CameraDevice = indigo.devices[pluginAction.deviceId]
		GetSnapshot(CameraDevice)
		
	def Mosaic(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		GetMosaic(CameraDevice)
		
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

