#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2014, Perceptive Automation, LLC. All rights reserved.
# http://www.indigodomo.com

import indigo
import os
from os import symlink
from os import listdir
from os.path import isfile, join
import sys
import time
import threading
import datetime
import shutil
import math
import requests
from requests.auth import HTTPDigestAuth
from datetime import date
from ghpu import GitHubPluginUpdater
from PIL import Image, ImageFont, ImageDraw, ImageChops, ImageEnhance
from StringIO import StringIO
import numpy as np
import scipy as sp
import scipy.ndimage as ndimage
import scipy.spatial as spatial
import scipy.misc as misc
import glob

#Global Variables
Intiation = True

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

################################################################################
#
# Misc Functions
#
################################################################################

def getSortedDir(path, srch, start, finish):

	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	PathCheck = os.path.isdir(path)
	
	if PathCheck is False:
		return "False"
	else:

		#name_list = [f for f in listdir(path) if isfile(join(path, f))]
		#try:
			#full_list = [os.path.join(path,i) for i in name_list]
			#time_sorted_list = sorted(full_list, key=os.path.getmtime, reverse=True)
		#except:
			#indigo.server.log("Get file list sub: " + str(errtxt))
		#Search for ext in file name
		#for file in time_sorted_list:
			#if file.find(srch) != -1:
				#filter_list.append(file) 
				
		filter_list = []

		filter_list = glob.glob(path + "/" + srch + "*.jpg")
		time_sorted_list = sorted(filter_list, key=os.path.getmtime, reverse=True)
				
		if start < 0:
			start = 0
			
		if finish > len(time_sorted_list):
			finish = len(time_sorted_list)
			
		#return final list
		final_list = time_sorted_list[start:finish]
		#indigo.server.log("mark1:" + str(len(final_list)))
		return final_list

def rmsdiff(im1, im2):
	##################Calculate the root mean square difference of two images
	diff = ImageChops.difference(im1, im2)
	h = diff.histogram()
	sq = (value*((idx%256)**2) for idx, value in enumerate(h))
	sum_of_squares = sum(sq)
	rms = math.sqrt(sum_of_squares/float(im1.size[0] * im1.size[1]))
	return rms

################################################################################
#
# Motion Detection Procedures
#
################################################################################

class BBox(object):
    def __init__(self, x1, y1, x2, y2):
        '''
        (x1, y1) is the upper left corner,
        (x2, y2) is the lower right corner,
        with (0, 0) being in the upper left corner.
        '''
        if x1 > x2: x1, x2 = x2, x1
        if y1 > y2: y1, y2 = y2, y1
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
    def taxicab_diagonal(self):
        '''
        Return the taxicab distance from (x1,y1) to (x2,y2)
        '''
        return self.x2 - self.x1 + self.y2 - self.y1
    def overlaps(self, other):
        '''
        Return True iff self and other overlap.
        '''
        return not ((self.x1 > other.x2)
                    or (self.x2 < other.x1)
                    or (self.y1 > other.y2)
                    or (self.y2 < other.y1))
    def __eq__(self, other):
        return (self.x1 == other.x1
                and self.y1 == other.y1
                and self.x2 == other.x2
                and self.y2 == other.y2)

def NewMotionCheck(imgA, imgB, CameraDir):

	#indigo.server.log("enter new motion")
	
	outlineimage = CameraDir + "/outline.jpg"
	#bwimage = GetDiff(imgA, imgB)
	img3 = GetDiff(imgA, imgB)
	MotionDetected = False
	listwidth = [0.0]
	listheight = [0.0]
	listarea = [0.0]
	listportion = [0.0]
	listratio = [0.0]
	bboxlist = []
	smoothradius = 15
	threshold = 25
	
	vcount = 0
	hcount = 0
	scount = 0
	
	smcount = 0
	mcount = 0
	lcount = 0
	
	topedge = 35
	
	minportion = .002
	maxportion = .30
	
	imgsize = img3.size
	bottomedge = imgsize[1]*.90
	imgarea = imgsize[0]*imgsize[1]
	
	#indigo.server.log("getting blobs")
	blobdata = misc.fromimage(img3, flatten=True)
	blobs = findBlobs(blobdata, smoothradius, threshold) #(smooth radius, threshold)
	bboxcount = 0
	
	#indigo.server.log(str(len(blobs)))
	if len(blobs) > 0:
		bboxes = remove_overlaps(slice_to_bbox(blobs))
		img_draw = ImageDraw.Draw(imgB)

		#indigo.server.log("-----")	
		#indigo.server.log(str(len(bboxes)))
		for bbox in bboxes:
			UniqueBox = True
			boxdem = (str(bbox.x1)+str(bbox.x2)+str(bbox.y1)+str(bbox.y2))
			
			if boxdem in bboxlist:
				UniqueBox = False
			else:
				bboxlist.append(boxdem)
		
			#indigo.server.log(str(bbox.y2))
			width = float(bbox.x2 - bbox.x1) #/ float(imgsize[0])			
			height = float(bbox.y2 - bbox.y1) #/ float(imgsize[1])
			area = float(width*height) #/ float(imgsize[0]*imgsize[1])
			portion = float(area/imgarea)
			ratio = float(height/width)
		
			if UniqueBox and bbox.y1 <= bottomedge and bbox.y2 >= topedge and (minportion <= portion <= maxportion):
				MotionDetected = True
				bboxcount = bboxcount + 1
				
				#indigo.server.log(str(bbox.x1) + ":" + str(bbox.y1) + "  " + str(bbox.x2) + ":" + str(bbox.y2))

				if ratio >= 1.2:  vcount = vcount + 1				
				if .8 < ratio < 1.2:  scount = scount + 1
				if ratio <= .8:  hcount = hcount + 1	
				
				if portion <= .01: 
					smcount = smcount + 1
					img_draw.rectangle((bbox.x1, bbox.y1, bbox.x2, bbox.y2), fill=None, outline=(255,255,0))
				if .01 < portion < .05: 
					mcount = mcount + 1
					img_draw.rectangle((bbox.x1, bbox.y1, bbox.x2, bbox.y2), fill=None, outline=(255,128,0))
				if portion >= .05: 
					lcount = lcount + 1
					img_draw.rectangle((bbox.x1, bbox.y1, bbox.x2, bbox.y2), fill=None, outline=(255,0,0))
				
				listarea.append(area)
				listheight.append(height)
				listwidth.append(width)
				listportion.append(portion)
		
		#indigo.server.log(str(bboxcount))
				
	#indigo.server.log(str(len(listarea)))
	maxarea = max(listarea)
	maxheight = max(listheight)
	maxwidth = max(listwidth)
	maxportion = max(listportion)
			
	return {'img':imgB, 'MaxArea':maxarea, 'MaxHeight':maxheight, 'MaxWidth':maxwidth, 'MaxPortion':maxportion, \
	'MotionDetected':MotionDetected, 'vcount':vcount, 'scount':scount, 'hcount':hcount, \
	'smcount':smcount, 'mcount':mcount, 'lcount':lcount}

def findBlobs(data, smooth_radius, threshold):
    """Detects and isolates contiguous regions in the input array"""
    # Blur the input data a bit so the blobs have a continous footprint 
    data = sp.ndimage.uniform_filter(data, smooth_radius)
    # Threshold the blurred data (this needs to be a bit > 0 due to the blur)
    thresh = data > threshold
    # Fill any interior holes in the paws to get cleaner regions...
    filled = sp.ndimage.morphology.binary_fill_holes(thresh)
    # Label each contiguous blob
    coded_blobs, num_paws = sp.ndimage.label(filled)
    # Isolate the extent of each paw
    data_slices = sp.ndimage.find_objects(coded_blobs)
    return data_slices

def slice_to_bbox(slices):
    for s in slices:
        dy, dx = s[:2]
        yield BBox(dx.start, dy.start, dx.stop+1, dy.stop+1)

def remove_overlaps(bboxes):
    '''
    Return a set of BBoxes which contain the given BBoxes.
    When two BBoxes overlap, replace both with the minimal BBox that contains both.
    '''
    # list upper left and lower right corners of the Bboxes
    corners = []

    # list upper left corners of the Bboxes
    ulcorners = []

    # dict mapping corners to Bboxes.
    bbox_map = {}

    for bbox in bboxes:
        ul = (bbox.x1, bbox.y1)
        lr = (bbox.x2, bbox.y2)
        bbox_map[ul] = bbox
        bbox_map[lr] = bbox
        ulcorners.append(ul)
        corners.append(ul)
        corners.append(lr)        

    # Use a KDTree so we can find corners that are nearby efficiently.
    tree = spatial.KDTree(corners)
    new_corners = []
    for corner in ulcorners:
        bbox = bbox_map[corner]
        # Find all points which are within a taxicab distance of corner
        indices = tree.query_ball_point(
            corner, bbox_map[corner].taxicab_diagonal(), p = 1)
        for near_corner in tree.data[indices]:
            near_bbox = bbox_map[tuple(near_corner)]
            if bbox != near_bbox and bbox.overlaps(near_bbox):
                # Expand both bboxes.
                # Since we mutate the bbox, all references to this bbox in
                # bbox_map are updated simultaneously.
                bbox.x1 = near_bbox.x1 = min(bbox.x1, near_bbox.x1)
                bbox.y1 = near_bbox.y1 = min(bbox.y1, near_bbox.y1) 
                bbox.x2 = near_bbox.x2 = max(bbox.x2, near_bbox.x2)
                bbox.y2 = near_bbox.y2 = max(bbox.y2, near_bbox.y2) 
    return set(bbox_map.values())
    
def GetDiff(img1, img2):
	img1 = img1.convert('L')
	img2 = img2.convert('L')
	img3 = ImageChops.difference(img1, img2)
	img3 = img3.convert('L')
	img3 = img3.convert('RGB')
	return img3

def convertBW(img3):
	datas = img3.getdata()
	newData = []
	white = 0
	black = 0

	for item in datas:
		if item[0] >= 35 and item[1] >= 35 and item[2] >= 35:
			newData.append((255, 255, 255))
			white = white + 1
		else:
			newData.append((0,0,0))
			black = black + 1
			
	img3.putdata(newData)
	percentdiff = float(float(white) / (float(white) + float(black)))*100
	
	return {'img3':img3, 'whitepx':white, 'blackpx': black, 'percentpx':percentdiff}

################################################################################
#
# New Image Procedures
#
################################################################################

def addLabel(img, labeltext):
	oldSize = img.size
	labelBorder = int(oldSize[1]*.06)
	newSize = (oldSize[0], labelBorder)	
	newImg = Image.new('RGBA', newSize, (128, 128, 128, 200))
	textSize = labelBorder-8	
	
	#Add label text
	draw = ImageDraw.Draw(newImg)
	font = ImageFont.truetype("Verdana.ttf", textSize)
	draw.text((5, 0),labeltext,(255,255,255),font=font)
	
	#Add label to image
	img.paste(newImg, (0,oldSize[1]-labelBorder+5), newImg)
	
	return img

def getURLImage(url,user,pwd,digest):
	
	#########  Add code to open HTML to File images
	img = "error"
	timecheck = datetime.datetime.now()
	
	#indigo.server.log("start url capture:" + url + "- digest " + str(digest))
	if digest:
		try:
			response = requests.get(url, auth=HTTPDigestAuth(user, pwd), timeout=(1,6))
			img = Image.open(StringIO(response.content))
		except Exception as errtxt:
			#indigo.server.log("Getting Image: " + str(errtxt))
			img = "error"
			pass
	else:
		try:
			response = requests.get(url, auth=(user, pwd), timeout=(1,6))
			img = Image.open(StringIO(response.content))
		except Exception as errtxt:
			#indigo.server.log("Getting Image: " + str(errtxt))
			img = "error"
			pass
			
	return img

def addBorder(img, width, height, color):
	#calculate black borders to keep aspect ratio
	oldSize = img.size
	newSize = (width, height)
	backgroundImg = Image.new("RGB", newSize, color)
	borderWidth = int((newSize[0] - oldSize[0])/2)
	borderHeight = int((newSize[1] - oldSize[1])/2)
	backgroundImg.paste(img, (borderWidth,borderHeight))
	
	return backgroundImg

def editImage(img, rotation, brightness, contrast, sharpness, bandw):
	#rotate image
	if rotation != 0:
		img = img.rotate(rotation)
	#brighten image
	if brightness != 1:
		enhancer = ImageEnhance.Brightness(img)
		img = enhancer.enhance(brightness)
	#contrast image
	if contrast != 1:
		enhancer = ImageEnhance.Contrast(img)
		img = enhancer.enhance(contrast)
	#sharpen image
	if sharpness != 1:
		enhancer = ImageEnhance.Sharpness(img)
		img = enhancer.enhance(sharpness)
	#convert to black and white
	if bandw:
		img = img.convert('L')
		
	return img
		
def CameraThread(deviceID, MainDir):
	ImageFound = 0
	FramesDiff = 0
	MotionSeconds = 0
	MotionDetected = False
	MotionDelayedCounter = 0
	
	while True:
	
		time.sleep(1)
	
		try:
			device = indigo.devices[deviceID]
			CameraState = device.states["CameraState"]
			CameraName = device.pluginProps["CameraName"]
			CameraDir = MainDir + "/" + CameraName

			CurrentImage = CameraDir + "/" + "/CurrentImage.jpg"		
			CurrentImageTH = CameraDir + "/" + "CurrentImageTH.jpg"	
			TempMotion = CameraDir + "/TempMotion.jpg"	
			ErrorImage = CameraDir + "/NotActive.jpg"
			TempImage = CameraDir + "/TempImage.jpg"
			ErrorImage = CameraDir + "/NotActive.jpg"
			TestImage = CameraDir + "/test.jpg"
			TempMotion = CameraDir + "/TempMotion.jpg"
			
			try:
				RecordSeconds = device.states["RecordSeconds"]+1
				device.updateStateOnServer("RecordSeconds", value=RecordSeconds)
			except Exception as errtxt:
				indigo.server.log("Record Seconds: " + str(errtxt))

			if CameraState == "On":
				timecheck = datetime.datetime.now()
			
				CameraName = device.pluginProps["CameraName"]
				CameraTimeout = int(device.pluginProps["CameraTimeout"])
				url = device.pluginProps["CaptureType"] + device.pluginProps["CameraAddress"]
				user = device.pluginProps["uname"]
				pwd = device.pluginProps["pwd"]
				Timeout = int(device.pluginProps["CameraTimeout"])
			
				ImageWidth = int(device.pluginProps["ImageWidth"])
				ImageHeight = int(device.pluginProps["ImageHeight"])
				BorderWidth = int(device.pluginProps["BorderWidth"])*2
				BorderColor = device.pluginProps["BorderColor"]
				Digest = device.pluginProps["Digest"]
				Rotation = device.pluginProps["CameraRotation"]
				Brightness = device.pluginProps["Brightness"]
				Contrast = device.pluginProps["Contrast"]
				Sharpness = device.pluginProps["Sharpness"]
				ImageQuality = int(device.pluginProps["ImageQuality"])
			
				CheckMotion = device.pluginProps["CheckMotion"]
				Motion = device.pluginProps["Motion"]
				MotionDelay = int(device.pluginProps["MotionDelay"])
				device.updateStateOnServer("Motion", value=Motion)
				device.updateStateOnServer("MotionDetected", value=False)
				MotionResults = ""
				imgM = ""

				imagedate = time.strftime("%m.%d.%Y.%H.%M.%S")
				NewImage = CameraDir + "/img_" + imagedate + ".jpg"
			
				nowtime = datetime.datetime.now()
				displaytime = str(nowtime).split(".")[0]
				labelText = CameraName + " : " + displaytime
			
				try:
					img=getURLImage(url,user,pwd,Digest)
				except Exception as errtxt:
					indigo.server.log(CameraName + "Get URL Image: " + str(errtxt))
			
				if img == "error":
					ImageFound = ImageFound + 1
				else:
					ImageFound = 0

				if ImageFound == 0:
					try:	
						sortedList = getSortedDir(CameraDir, "img", 1, 35)
					except Exception as errtxt:
						indigo.server.log(CameraName + "Get file list: " + str(errtxt))
				
					try:	
						#indigo.server.log("Set Size")
						img.thumbnail((ImageWidth, ImageHeight))
						#indigo.server.log(Brightness +":"+ Contrast +":"+ Sharpness)
						img=editImage(img, int(Rotation), float(Brightness), float(Contrast), float(Sharpness), False)
						#indigo.server.log("Add black bars")
						img=addBorder(img, ImageWidth, ImageHeight, "black")
						#indigo.server.log("Add Text")		
						img=addLabel(img, labelText)
						#indigo.server.log("Add Border")
						img=addBorder(img, ImageWidth + BorderWidth, ImageHeight + BorderWidth, BorderColor)
					except Exception as errtxt:
						indigo.server.log(CameraName + " edit image: " + str(errtxt))

					if Motion == True:
						MaxArea = 0
						MaxHeight = 0
						MaxWidth = 0
						MaxPortion = 0
						vcount = 0
						scount = 0
						hcount = 0
						smcount = 0
						mcount = 0
						lcount = 0
						shapecount = ("v" + str(vcount) + ":s" + str(scount) + ":h" + str(hcount))
						sizecount = ("s" + str(smcount) + ":m" + str(mcount) + ":l" + str(lcount))
						if len(sortedList) > 5:
							try:
								motionimage = Image.open(sortedList[0])
								MotionResults = NewMotionCheck(motionimage, img, CameraDir)
							except Exception as errtxt:
								indigo.server.log(CameraName + "Get motion: " + str(errtxt))

							try:
								MaxArea = "%.0f" % MotionResults['MaxArea']
								MaxHeight = "%.0f" % MotionResults['MaxHeight']
								MaxWidth = "%.0f" % MotionResults['MaxWidth']
								MaxPortion = "%.3f" % MotionResults['MaxPortion']
								vcount = MotionResults['vcount']
								scount = MotionResults['scount']
								hcount = MotionResults['hcount']
								smcount = MotionResults['smcount']
								mcount = MotionResults['mcount']
								lcount = MotionResults['lcount']
								shapecount = ("v" + str(vcount)+ ":s" + str(scount) + ":h" + str(hcount))
								sizecount = ("s" + str(smcount) + ":m" + str(mcount) + ":l" + str(lcount))
								MotionDetected = MotionResults['MotionDetected']
							except Exception as errtxt:
								indigo.server.log(CameraName + " Get motion states: " + str(errtxt))
								shapecount = ("v" + str(vcount) + ":s" + str(scount) + ":h" + str(hcount))
								sizecount = ("s" + str(smcount) + ":m" + str(mcount) + ":l" + str(lcount))
								MotionDetected = MotionResults['MotionDetected']

						try:
							if MotionDetected:
								img = MotionResults['img']
								device.updateStateOnServer("MotionDetected", value=MotionDetected)
								device.updateStateOnServer("MaxHeight", value=MaxHeight)				
								device.updateStateOnServer("MaxWidth", value=MaxWidth)					
								device.updateStateOnServer("MaxArea", value=MaxArea)
								device.updateStateOnServer("MaxPortion", value=MaxPortion)
								device.updateStateOnServer("vcount", value=vcount)
								device.updateStateOnServer("scount", value=scount)
								device.updateStateOnServer("hcount", value=hcount)
								device.updateStateOnServer("smcount", value=smcount)
								device.updateStateOnServer("mcount", value=mcount)
								device.updateStateOnServer("lcount", value=lcount)
								MotionDelayedCounter = 1	
								device.updateStateOnServer("MotionDelay", value=True)				
							else:
								device.updateStateOnServer("MotionDetected", value=MotionDetected)
								device.updateStateOnServer("MaxHeight", value=0)					
								device.updateStateOnServer("MaxWidth", value=0)					
								device.updateStateOnServer("MaxArea", value=0)
								device.updateStateOnServer("MaxPortion", value=0)
								device.updateStateOnServer("vcount", value=0)
								device.updateStateOnServer("scount", value=0)
								device.updateStateOnServer("hcount", value=0)
								device.updateStateOnServer("smcount", value=0)
								device.updateStateOnServer("mcount", value=0)
								device.updateStateOnServer("lcount", value=0)
		
							if MotionDelayedCounter < MotionDelay and MotionDelayedCounter > 0:
								MotionDelayedCounter = MotionDelayedCounter +  1
							else:
								MotionDelayedCounter = 0
								device.updateStateOnServer("MotionDelay", value=False)
							
						except Exception as errtxt:
								indigo.server.log(CameraName + " get motion: " + str(errtxt))

						#indigo.server.log(str(CheckMotion))
						if CheckMotion == True:
							#indigo.server.log("Add Motion Data")
							draw = ImageDraw.Draw(img)
							font = ImageFont.truetype("Verdana.ttf", 12)
							labeltext = "M:" + str(MotionDetected) + " A:" + str(MaxArea) + " H:" + str(MaxHeight) + " W:" + str(MaxWidth) + " P:" + str(MaxPortion) + " " + shapecount + " " + sizecount
							draw.text((10, 10),labeltext,(255,255,255),font=font)

					img.save(NewImage,optimize=True,quality=ImageQuality)

					try:	
						if os.path.exists(TempImage):
							os.remove(TempImage)						
						os.symlink(NewImage, TempImage)
					except Exception as errtxt:
						indigo.server.log(CameraName + " change SymLink: " + str(errtxt))
					
					#indigo.server.log("Rename file")
					try:
						time.sleep(.1)
						os.rename(TempImage, CurrentImage)
					except Exception as errtxt:
						indigo.server.log(CameraName + " rename image: " + str(errtxt))

					#indigo.server.log("Thumbnails")
					try:
						imgTH = img
						imgTH.thumbnail((250,250))
						imgTH.save(CurrentImageTH,optimize=True,quality=ImageQuality)
					except Exception as errtxt:
						indigo.server.log(CameraName + " Thumbnails: " + str(errtxt))

					#indigo.server.log("Image Cleanup")
					try:			
						if len(sortedList) > 30:
							for item in range(30,len(sortedList)):
								file = sortedList[item]
								os.remove(file)	
					except Exception as errtxt:
						indigo.server.log(CameraName + " Image Cleanup: " + str(errtxt))
				
				else:
					if ImageFound == Timeout:
						shutil.copy(ErrorImage, CurrentImageTH)
						indigo.server.log("Image not loaded for " + CameraName + " camera. " + str(ImageFound))
		
			else:
				shutil.copy(ErrorImage, CurrentImageTH)
				
		except Exception as errtxt:
			indigo.server.log("Master Camera Thread: " + str(errtxt))	
			
################################################################################
#
# Master Image Procedures
#
################################################################################

def MasterImage():
	##################Display a master image of different cameras
	DeviceID = int(indigo.activePlugin.pluginPrefs["MasterCamera"])
	MasterCameraDevice = indigo.devices[DeviceID]
	
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	PlayRecording = indigo.activePlugin.pluginPrefs["PlayRecording"]
	RecordingFrame = indigo.activePlugin.pluginPrefs["RecordingFrame"]
	RecordingFlag = indigo.activePlugin.pluginPrefs["RecordingFlag"]  
	MasterCameraName = MasterCameraDevice.pluginProps["CameraName"]
	ToggleResolution = indigo.activePlugin.pluginPrefs["LowRes"]

	MasterCameraDir = MainDir + "/" + MasterCameraName
	MasterRecording = MainDir + "/" + PlayRecording
	MasterImage1 = MainDir + "/Master1.jpg"
	MasterImage2 = MainDir + "/Master2.jpg"
	MasterImage3 = MainDir + "/Master3.jpg"
	MasterImage4 = MainDir + "/Master4.jpg"
	
	#MasterCameraDevice.updateStateOnServer("LogMessage", value="Master 1 " + MasterCameraName)

	#sortedList = getSortedDir(MasterCameraDir, "img", 0, 2)
	#CurrentImage = sortedList[1]
	CurrentImage = MasterCameraDir + "/CurrentImage.jpg"
	CurrentImageLR = CurrentImage

	#setup playing the master image
	if ToggleResolution == "true":
		CurrentImageLR = MasterCameraDir + "/CurrentImageTH.jpg"
	
	#MasterCameraDevice.updateStateOnServer("LogMessage", value="Master 2 " + MasterCameraName)
	
	#setup playing a recording
	sortedList = getSortedDir(MasterRecording, "img", 0, 30)
	#indigo.server.log(str(len(sortedList)))
	if sortedList == "False":
		RecordingImage = MainDir + "/" + "NoRecording.jpg"
	else:
		if len(sortedList)-1 <= int(RecordingFrame):
			RecordingFrame = 0
	
		try:
			RecordingImage = sortedList[int(RecordingFrame)]
		except Exception as errtxt:
			indigo.server.log("Show recording " + str(len(sortedList)) + " " + str(RecordingFrame) + ":" + str(errtxt))

	if str(RecordingFlag) == "1":
		FileFrom = RecordingImage
		CurrentImageLR = RecordingImage
	else:
		FileFrom = CurrentImage	
	
	#MasterCameraDevice.updateStateOnServer("LogMessage", value="Master 3 " + MasterCameraName)
			
	try:
		#Remove Files
		if os.path.exists(MasterImage1):
			os.remove(MasterImage1)
		os.symlink(FileFrom, MasterImage1)		
	except Exception as errtxt:
		indigo.server.log("Master 1: " + str(errtxt))

	try:
		if os.path.exists(MasterImage2):
			os.remove(MasterImage2)
		os.symlink(CurrentImage, MasterImage2)	
	except Exception as errtxt:
		indigo.server.log("Master 2: " + str(errtxt))

	try:
		os.remove(MasterImage3)
		if os.path.exists(MasterImage3):
			os.remove(MasterImage3)
		os.symlink(RecordingImage, MasterImage3)	
	except Exception as errtxt:
		indigo.server.log("Master 3: " + str(errtxt))

	try:
		if os.path.exists(MasterImage4):
			os.remove(MasterImage4)
		os.symlink(CurrentImageLR, MasterImage4)

	except Exception as errtxt:
		indigo.server.log("Master 4: " + str(errtxt))



def RunCarousel(MainDir, CarouselCount, CarouselTimer):

	actlist = []
	for sdevice in indigo.devices.iter("self"):
		CameraState = sdevice.states["CameraState"]
		if CameraState == "On":
			actlist.append(sdevice.pluginProps["CameraName"] )
	
	MaxCarouselCount = len(actlist)
		
	if MaxCarouselCount > 0:				
		if CarouselTimer >= 5:
			CarouselTimer = 0
			if CarouselCount >= MaxCarouselCount-1:
				CarouselCount = 0
			else:
				CarouselCount = CarouselCount + 1
		else:
			CarouselTimer = CarouselTimer + 1
	
		try:
			CarouselCamera = actlist[CarouselCount]	
		except:
			CarouselCamera = actlist[0]
		
		#indigo.server.log(CarouselCamera)
		CurrentImage = MainDir + "/" + CarouselCamera + "/CurrentImage.jpg"
		CurrentImageLR = MainDir + "/" + CarouselCamera + "/CurrentImageTH.jpg"
		CarouselImage = MainDir + "/CarouselImage.jpg"
		CarouselImageLR = MainDir + "/CarouselImageLR.jpg"
		
		try:
			os.remove(CarouselImage)
			os.remove(CarouselImageLR)
		except Exception as errtxt:
			indigo.server.log("Error Carousel File Remove: " + str(errtxt))	
			
		try:
			os.symlink(CurrentImage, CarouselImage)
			os.symlink(CurrentImageLR, CarouselImageLR)			
		except Exception as errtxt:
			indigo.server.log("Error Carousel SymLink: " + str(errtxt))
		
		indigo.activePlugin.pluginPrefs["CarouselCount"] = CarouselCount
	return (CarouselTimer)

def GetMosaic(device):
	##################Create tiled version of last 6 images
	SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
	MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
	CameraName = device.pluginProps["CameraName"]
	CameraFile = CameraName.replace(" ", "_")
	CameraDir = CameraDir = MainDir + "/" + CameraName
	MosaicImage = SnapshotDir + "/" + CameraFile + "_mosaic.jpg"
	MosaicImageLR = SnapshotDir + "/" + CameraFile + "_mosaicLR.jpg"
	sortedList = getSortedDir(CameraDir, "img", 0, 30)
	
	img1 = Image.open(sortedList[10])
	img2 = Image.open(sortedList[11])
	img3 = Image.open(sortedList[12])
	img4 = Image.open(sortedList[13])
	img5 = Image.open(sortedList[14])
	img6 = Image.open(sortedList[15])
	
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
	mosaic_img.save(MosaicImage,optimize=True,quality=30)
	mosaic_img.thumbnail((200,200))
	mosaic_img.save(MosaicImageLR,optimize=True,quality=30)

	indigo.server.log("mosaic done")
			
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
		indigo.server.log("-----  startup called  ------")
		indigo.server.log("Checking for update")
		
		ActiveVersion = str(self.pluginVersion)
		CurrentVersion = str(self.updater.getVersion())
		
		if ActiveVersion == CurrentVersion:
			indigo.server.log("Running the current version of Security Camera")
		else:
			indigo.server.log("The current version of Security Camera is " + str(CurrentVersion) + " and the running version " + str(ActiveVersion) + ".")
			indigo.server.log("WARNING:  Upgrading to this version will require recreating all existing cameras.")
		
		SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		
		#Main dir test
		MainDirTest = os.path.isdir(MainDir)
		if MainDirTest is False:
			indigo.server.log("Home image directory not found.  Creating...")
			os.makedirs(MainDir)
			indigo.server.log("Created: " + MainDir)
			
		#Snapshot Test
		SnapshotDirTest = os.path.isdir(SnapshotDir)
		if SnapshotDirTest is False:
			indigo.server.log("Snapshot image directory not found. Creating...")
			os.makedirs(SnapshotDir)
			indigo.server.log("Created: " + SnapshotDir)

	def shutdown(self):
		indigo.server.log(u"shutdown called")

	def validatePrefsConfigUi(self, valuesDict):
	
		MainDir = valuesDict["MainDirectory"]
		ArchiveDir = MainDir + "/Archive"
		
		#Main Dir Test
		MainDirTest = os.path.isdir(MainDir)		
		if MainDirTest is False:
			indigo.server.log("Home image directory not found. Creating...")
			os.makedirs(MainDir)
			indigo.server.log("Created: " + MainDir)

		#archive dir test
		ArchiveDirTest = os.path.isdir(ArchiveDir)			
		if ArchiveDirTest is False:
			indigo.server.log("Archive image directory not found. Creating...")
			os.makedirs(ArchiveDir)
			indigo.server.log("Created: " + ArchiveDir)
		return True

	def didDeviceCommPropertyChange(self, origDev, newDev):
			return False

	def deviceStartComm(self, dev):
		CameraName = dev.pluginProps["CameraName"]
		#url = dev.pluginProps["CameraAddress"]	<remove>	
		dev.stateListOrDisplayStateIdChanged()
	
		localPropsCopy = dev.pluginProps
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		IMDir = indigo.activePlugin.pluginPrefs["IMDirectory"]
		CameraDir = MainDir + "/" + CameraName
		NotActiveImage = CameraDir + "/NotActive.jpg"

		CameraDirTest = os.path.isdir(CameraDir)
		if CameraDirTest is False:
			indigo.server.log("Camera image directory not found. Creating...")
			os.makedirs(CameraDir)
			
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
			indigo.server.log("Not Active Image not found.  Creating...")	
	
		if dev.states["CameraState"] != "Off":
			dev.updateStateOnServer("CameraState", value="On")	
			
		dev.stateListOrDisplayStateIdChanged()
			
		return True

################################################################################
#
# Main looping thread
#
################################################################################

	def runConcurrentThread(self):
		CarouselCount = 0
		CarouselTimer = 0
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		
		DebugMode = indigo.activePlugin.pluginPrefs["Debug"]
		self.debug = DebugMode
		
		try:
			for device in indigo.devices.iter("self"):
				CameraName = device.pluginProps["CameraName"]
				CameraState = device.states["CameraState"]

				tw = threading.Thread(name=CameraName, target=CameraThread, args=(device.id, MainDir))
				tw.start()
				indigo.server.log("Thread started for " + CameraName + " camera. id: " + str(tw.ident))
				
			#Debug Mode	
			indigo.server.log("Starting main loop")	
					
			while True:

				self.sleep(1)
		
				################################################################################
				# Setup
				################################################################################
				MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
				RecordingCount = int(indigo.activePlugin.pluginPrefs["RecordingCount"])
				RecordingPause = indigo.activePlugin.pluginPrefs["RecordingPause"]
				CarouselCameraPause = str(indigo.activePlugin.pluginPrefs["CarouselCameraPause"])

				################################################################################
				# Recording setup
				################################################################################
				try:	
					if RecordingPause == "False":
						#set record loop frame
						if RecordingCount > 29:
							RecordingCount = 0
						else:
							RecordingCount = RecordingCount + 1
	
					RecordingFrame = str(RecordingCount)
					indigo.activePlugin.pluginPrefs["RecordingFrame"] = RecordingFrame
					indigo.activePlugin.pluginPrefs["RecordingCount"] = RecordingCount
				except Exception as errtxt:
						indigo.server.log("Record Setup "  + str(errtxt)) 		
		
				################################################################################
				# Create image carousel
				################################################################################
				#indigo.server.log("Carousel Paused: " + CarouselCameraPause)
				try:
					CarouselCount = int(indigo.activePlugin.pluginPrefs["CarouselCount"])		
					if CarouselCameraPause == "false":
						#indigo.server.log("Starting Carousel")
						CarouselTimer = RunCarousel(MainDir, CarouselCount, CarouselTimer)
				except Exception as errtxt:
						indigo.server.log("Carousel: "  + str(errtxt))
		
				################################################################################
				# Set Master Image
				################################################################################
				#indigo.server.log("Starting Master Image")
				try:
					MasterID = int(indigo.activePlugin.pluginPrefs["MasterCamera"])
					#indigo.server.log(str(MasterID))
					if MasterID != "":
						MasterImage()
				except Exception as errtxt:
					indigo.server.log("Unable to run Master Image: " + str(MasterID))	
						
		except self.StopThread:
			indigo.server.log("thread stopped")
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
		## add code to stop thread
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		indigo.server.log("Stop Camera action called:" + CameraName)
		CameraDevice.updateStateOnServer("CameraState", value="Off")
		
	def StartCamera(self, pluginAction):
		## add code to start thread
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		indigo.server.log("Start Camera action called:" + CameraName)
		CameraDevice.updateStateOnServer("CameraState", value="On")
		CameraDevice.updateStateOnServer("OfflineSeconds", value="On")
		
	def ToggleCamera(self, pluginAction):
		## add code to start/stop thread
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		CameraState = CameraDevice.states["CameraState"]
		localPropsCopy = CameraDevice.pluginProps
		
		if CameraState == "On":
			indigo.server.log("Stop Camera action called:" + CameraName)
			CameraDevice.updateStateOnServer("CameraState", value="Off")
		else:
			indigo.server.log("Start Camera action called:" + CameraName)
			CameraDevice.updateStateOnServer("CameraState", value="On")
			CameraDevice.updateStateOnServer("OfflineSeconds", value="0")
		
	def MasterCamera(self, pluginAction):
		indigo.activePlugin.pluginPrefs["MasterCamera"] = pluginAction.deviceId
		indigo.activePlugin.pluginPrefs["RecordingFlag"] = 0
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		
		try:
			MasterImage()
		except Exception as errtxt:
			LogMessage = CameraName + " Master: " + str(errtxt)
			indigo.server.log(LogMessage)

	def MotionOn(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		Motion = CameraDevice.pluginProps["Motion"]
		props = CameraDevice.pluginProps
		indigo.server.log("Start motion action called:" + CameraName)
		props['Motion'] = True
		CameraDevice.replacePluginPropsOnServer(props)
		
	def MotionOff(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		Motion = CameraDevice.pluginProps["Motion"]
		props = CameraDevice.pluginProps
		indigo.server.log("Stop motion action called:" + CameraName)
		props['Motion'] = False
		CameraDevice.replacePluginPropsOnServer(props)
		
	def ToggleMotion(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		Motion = CameraDevice.pluginProps["Motion"]
		props = CameraDevice.pluginProps

		try:
			if Motion == True:
				indigo.server.log("Stop motion action called:" + CameraName)
				props['Motion'] = False
				CameraDevice.replacePluginPropsOnServer(props)
			else:
				indigo.server.log("Start motion action called:" + CameraName)
				props['Motion'] = True
				CameraDevice.replacePluginPropsOnServer(props)
		except Exception as errtxt:
			LogMessage = CameraName + "Toggle Motion: " + str(errtxt)
			indigo.server.log(LogMessage)

	def RecordCamera(self, pluginAction):
	
		try:
			CameraDevice = indigo.devices[pluginAction.deviceId]
			CameraName = CameraDevice.pluginProps["CameraName"]
			CameraDevice.updateStateOnServer("RecordSeconds", value=0)
			SavedDir = time.strftime("%m %d %Y %H.%M.%S")
			MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
			SourceDir = MainDir + "/" + CameraName
			RecordingDir = MainDir + "/" + CameraName + "/" + SavedDir
			filecounter = 0
		
			time.sleep(20)
		
			os.makedirs(RecordingDir)
			src_files = getSortedDir(SourceDir, "img", 0, 30)
			for file_name in src_files:
				filecounter = filecounter + 1
				try:
					shutil.copy(file_name, RecordingDir)
				except Exception as errtxt:
					indigo.server.log(str(errtxt))
		
			sortedList = getSortedDir(SourceDir, "img", 3, 4)
			CurrentImage = sortedList[0]
		
			for num in reversed(range(2, 10)):
				LeadingNum = "0" + str(num)
				Current = LeadingNum[-2:]
				LeadingPrev = "0" + str(num - 1)
				Previous = LeadingPrev[-2:]
				PrevValue = CameraDevice.states["Recording" + Previous]
				PrevNewValue = CameraDevice.states["NewRecording" + Previous]
				CameraDevice.updateStateOnServer("Recording" + Current, value=PrevValue)
				CameraDevice.updateStateOnServer("NewRecording" + Current, value=PrevNewValue)
				ThumbTo = SourceDir +"/thumb" + Current + ".jpg"
				ThumbFrom = SourceDir +"/thumb" + Previous + ".jpg"
			
				try:
					os.rename(ThumbFrom, ThumbTo)	
				except Exception as errtxt:
					indigo.server.log("Thumb: " + str(errtxt))
				
			CurrentThumb = SourceDir + "/Thumb01.jpg"
			shutil.copy (CurrentImage, CurrentThumb)
			CameraDevice.updateStateOnServer("Recording01", value=SavedDir)
			CameraDevice.updateStateOnServer("NewRecording01", value="New")
		except Exception as errtxt:
			indigo.server.log(CameraName + " Record: " + str(errtxt))
		
	def ToggleCarousel(self, pluginAction):
		ToggleCarousel = indigo.activePlugin.pluginPrefs["CarouselOn"]
		if ToggleCarousel == "true":
			indigo.activePlugin.pluginPrefs["CarouselOn"] = "false"
		else:
			indigo.activePlugin.pluginPrefs["CarouselOn"] = "true"

	def ToggleCarouselCamera(self, pluginAction):
		ToggleCarousel = indigo.activePlugin.pluginPrefs["CarouselCameraPause"]
		if ToggleCarousel == "true":
			indigo.activePlugin.pluginPrefs["CarouselCameraPause"] = "false"
		else:
			indigo.activePlugin.pluginPrefs["CarouselCameraPause"] = "true"
			
	def NextCarouselCamera(self, pluginAction):
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		CarouselCount = int(indigo.activePlugin.pluginPrefs["CarouselCount"])
		indigo.activePlugin.pluginPrefs["CarouselCount"] = CarouselCount + 1
		RunCarousel(MainDir, CarouselCount, 5)

	def ToggleResolution(self, pluginAction):
		ToggleResolution = indigo.activePlugin.pluginPrefs["LowRes"]
		if ToggleResolution == "true":
			indigo.activePlugin.pluginPrefs["LowRes"] = "false"
		else:
			indigo.activePlugin.pluginPrefs["LowRes"] = "true"

	def PlayRecording(self, pluginAction):
	
		try:
			CameraDevice = indigo.devices[pluginAction.deviceId]
			CameraName = CameraDevice.pluginProps["CameraName"]
			RecordingID = pluginAction.props["PlaySelect"]
			Recording = CameraName + "/" + CameraDevice.states["Recording" + RecordingID]
			indigo.activePlugin.pluginPrefs["RecordingPause"] = "False"
		
			for device in indigo.devices.iter("self"):
					device.updateStateOnServer("Playing", value="Play")
		
			indigo.activePlugin.pluginPrefs["RecordingFrame"] = "0"
			indigo.activePlugin.pluginPrefs["RecordingCount"] = "0"
		
			indigo.activePlugin.pluginPrefs["RecordingFlag"] = 1
			indigo.activePlugin.pluginPrefs["PlayRecording"] = Recording
			indigo.server.log("Play recording action called:" + CameraName)
		
			CameraDevice.updateStateOnServer("NewRecording" + RecordingID, value="")
		except Exception as errtxt:
			indigo.server.log(CameraName + " Play: " + str(errtxt))
		
	def Snapshot(self, pluginAction):
		device = indigo.devices[pluginAction.deviceId]
		CameraName = device.pluginProps["CameraName"]
		SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
		SnapshotImage = SnapshotDir + "/Snap001.jpg"
		Quality = int(pluginAction.props["Quality"])
		CameraAddress = "http://" + device.pluginProps["CameraAddress"]
		CameraUser = device.pluginProps["uname"]
		CameraPwd = device.pluginProps["pwd"]
		Digest = device.pluginProps["Digest"]
		Rotation = device.pluginProps["CameraRotation"]
		Brightness = device.pluginProps["Brightness"]
		Contrast = device.pluginProps["Contrast"]
		Sharpness = device.pluginProps["Sharpness"]
		BorderWidth = int(device.pluginProps["BorderWidth"])*2
		BorderColor = device.pluginProps["BorderColor"]
		ImageWidth = 640
		ImageHeight = 480
		
		nowtime = datetime.datetime.now()
		displaytime = str(nowtime).split(".")[0]
		labelText = CameraName + " : " + displaytime
		
		#indigo.server.log("Capture Image")
		#indigo.server.log(CameraAddress)
		img=getURLImage(CameraAddress,CameraUser,CameraPwd, Digest)
		
		#indigo.server.log("Set Size")
		img.thumbnail((ImageWidth, ImageHeight))
		#indigo.server.log(Brightness +":"+ Contrast +":"+ Sharpness)
		img=editImage(img, int(Rotation), float(Brightness), float(Contrast), float(Sharpness), False)
		#indigo.server.log("Add black bars")
		img=addBorder(img, ImageWidth, ImageHeight, "black")
		#indigo.server.log("Add Text")		
		img=addLabel(img, labelText)
		#indigo.server.log("Add Border")
		img=addBorder(img, ImageWidth + BorderWidth, ImageHeight + BorderWidth, BorderColor)
		
		#save image history
		for num in reversed(range(1, 5)):
			fromfile = "Snap00" + str(num)
			fromfile = SnapshotDir + "/" + fromfile + ".jpg"
			tofile = "Snap00" + str(num+1)
			tofile = SnapshotDir + "/" + tofile + ".jpg"
			if os.path.isfile(fromfile):
				os.rename(fromfile, tofile)	

		try:		
			img.save(SnapshotImage,optimize=True,quality=Quality)
		except Exception as errtxt:
			indigo.server.log(str(errtxt))
	
	def GIF(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		SnapshotDir = indigo.activePlugin.pluginPrefs["SnapshotDirectory"]
		MainDir = indigo.activePlugin.pluginPrefs["MainDirectory"]
		SourceDir = MainDir + "/" + CameraName +"/"
		DestName = SnapshotDir + "/" + CameraName + ".gif"
		
		sortedList = getSortedDir(SourceDir, "img", 0, 30)
		images = [Image.open(fn) for fn in sortedList]
		
		writeGif(DestName, images, duration=1)
		indigo.server.log("done giffing")
		
	def PauseRecording(self, pluginAction):
		RecordingPaused = indigo.activePlugin.pluginPrefs["RecordingPause"]
		PlayState = ""
		
		if RecordingPaused == "False":
			indigo.activePlugin.pluginPrefs["RecordingPause"] = "True"
			PlayState = "Pause"
		else:
			indigo.activePlugin.pluginPrefs["RecordingPause"] = "False"
			PlayState = "Play"
		
		for device in indigo.devices.iter("self"):
				device.updateStateOnServer("Playing", value=PlayState)
		
	def FrameBackward(self, pluginAction):
	
		RecordingCount = int(indigo.activePlugin.pluginPrefs["RecordingCount"])
		#set record loop frame
		if RecordingCount < 0:
			RecordingCount = 20
		else:
			RecordingCount = RecordingCount - 1
					
		RecordingFrame = str(RecordingCount)
		indigo.activePlugin.pluginPrefs["RecordingFrame"] = RecordingFrame
		indigo.activePlugin.pluginPrefs["RecordingCount"] = RecordingCount

	def FrameForward(self, pluginAction):
			
		RecordingCount = int(indigo.activePlugin.pluginPrefs["RecordingCount"])
		#set record loop frame
		if RecordingCount > 20:
			RecordingCount = 0
		else:
			RecordingCount = RecordingCount + 1
					
		RecordingFrame = str(RecordingCount)
		indigo.activePlugin.pluginPrefs["RecordingFrame"] = RecordingFrame
		indigo.activePlugin.pluginPrefs["RecordingCount"] = RecordingCount
		
	def Mosaic(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		
		try:
			GetMosaic(CameraDevice)
		except Exception as errtxt:
			indigo.server.log(CameraName + " Mosaic: " + str(errtxt))
		
	def CameraCommand(self, pluginAction):
		ReturnVariable = pluginAction.props["ReturnVariable"]
		CameraAddress = "http://" + device.pluginProps["CameraAddress"]
		CameraUser = device.pluginProps["uname"]
		CameraPwd = device.pluginProps["pwd"]
		ReturnVariable = ReturnVariable.replace(" ", "_")
		
		try:
			ReturnVar = indigo.variables[ReturnVariable]
		except Exception as errtxt:
			indigo.server.log(str(errtxt))
			indigo.variable.create(ReturnVariable)
			indigo.server.log(ReturnVariable + " created")
		
		#indigo.server.log("start url Command")
		if digest:
			try:
				response = requests.get(CameraAddress, auth=HTTPDigestAuth(CameraUser, CameraPwd), timeout=(1, 3))
				indigo.variable.updateValue(ReturnVariable, value=str(returnvalue))
			except:
				indigo.variable.updateValue(ReturnVariable, value="Command Failed")
		else:
			try:
				response = requests.get(CameraAddress, auth=(CameraUser, CameraPwd), timeout=(1, 3))
				indigo.variable.updateValue(ReturnVariable, value=str(returnvalue))
			except:
				indigo.variable.updateValue(ReturnVariable, value="Command Failed")
	
	def DeleteRecording(self, pluginAction):
		CameraDevice = indigo.devices[pluginAction.deviceId]
		CameraName = CameraDevice.pluginProps["CameraName"]
		Months = pluginAction.props["DeleteMonths"]
		Days = int(Months) * 30
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
