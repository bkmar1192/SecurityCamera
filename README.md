# SecurityCamera
Security Camera Plugin for Indigo

This plugin is designed to be used for security cameras that provide
access to a refreshing image file.  Although it was designed with Security 
Cameras in mind it should work with any refreshing image file.

Plugin Configuration:
---------------------

Main Directory - is the base directory that all files will be saved.  A directory
for each camera (device) will be created in this directory.  You can leave 
this at the default location unless you want to store them somewhere else.

Snapshot Directory - the directory that snapshots and mosaics are stored (described below). You can leave 
this at the default location unless you want to store them somewhere else.

ImageMagick Directory - IM (http://www.imagemagick.org) is required to be installed for the plugin to work.
The default directory location should be OK unless you changed the default install
of ImageMagick.

Debug - Turning this on increases the logging of the plugin.  Turning this on will add 
a lot of messages to your log file so use it sparingly.

Device Configuration:
---------------------

Camera Name - Unique name of the camera.  This will be the name of the directory that 
gets created.

Address - URL of the file that is being accessed.  

[Note: http://www.ispyconnect.com/sources.aspx has a lot of information on specific urls for a 
variety of cameras.  Find your camera brand and click on the link, look for the camera model with 
Type equal to JPEG, click on the model name, a dialog will pop up that will guide you through creating the url.]

Camera Timeout (in seconds) - How many seconds of no new images from the URL before 
it triggers a timeout.

Image Rotation - Rotates the image if your camera is upside down or sideways.

Image width and height - Default image size.

Image border width/colorm - Add a border to the image.

Auto Level - Automagically adjust color levels of image.  This is a 'perfect' image normalization operator. It finds the exact minimum and maximum color values in the image and then applies a -level operator to stretch the values to the full range of values.

Normalize - Increase the contrast in an image by stretching the range of intensity values.  The intensity values are stretched to cover the entire range of possible values. While doing so, black-out at most 2% of the pixels and white-out at most 1% of the pixels.

Enhance - Apply a digital filter to enhance a noisy image.

Sensitivity - How sensitive is the motion detection.  The larger the number the less sensitive the camera will be to detecting motion.

Different Frames in Row - how many different frames need to be registered to trigger motion.

Seconds Until Reset - how many seconds between registration of motion.

Actions:
--------

Stop Camera:  Stop capturing images from the camera.

Start Camera:  Start capturing images from the camera.

Toggle:  Turn the camera on/off.

Master Camera:  Switch the Master image to the specified camera (see detailes on images
below).

Record:  Save the last 20 seconds of images from the camera.  Up to 10 videos can be 
played back although an unlimited number of records can be captured. 

Play: Play back a recorded video - specify recording 1 - 10.

Take Snapshot:  Saves current image to series of flies in the snapshot directory.  Saves images as 0000[1-9].jpg. 

Take Mosaic:  Saves current image to series of flies in the snapshot directory.  Saves only a single image at a time, saving over previous file.

Toggle Carousel: Start/stop the rotation of the cameras.

Delete Old Files:  Move files to an archive folder that are older than the days 
specified.  

States:
-------

CameraState (on/off): State of the camera as deteremined by the actions: Stop Camera, Start Camera, and Toggle Camera.  Will show Unavailable if no picture has been captured in the last x seconds (dteremined by the Timeout setting on the camera device).

FrameDiff: Number of frames that have detected motion.

ImageAveDiff:  Average difference between image frames.

MotionDetected:  Has x frames detected motion (as determined by the Different Frames in Row setting on the device.

MotionSeconds:  Number of seconds since last motion detection.

Offline Seconds:  Number of seconds an image has not been captured from the camera.

PixelDiff: % of different pixels detected between the current frame and frame 00007.jpg.

RecordSeconds:  Seconds since last recording.

Recording[01-10]: List of last 10 recordings - top recording is most recent.

Files:
------

Main Directory/Camera Name/CurrentImage.jpg - current refreshing image.  Add to control 
pages as a refreshing image.

Main Directory/Camera Name/thumb[01 - 10] - Thumbnail images for each of the 10 recording.

Main Directory/Camera Name/NotActive.jpg - Default image when a camera is off or unavailable.
This can be manually replaced (same file name) to change the default.

Main Directory/Master1.jpg - An image that will show either the most recent selected 
master iamge (Master Camera action) or the last selected recording.

Main Directory/Master2.jpg - An image that will show the most recent selected 
master image(Master Camera action).

Main Directory/Master3.jpg - An image that will show the last selected recording.

Main Directory/CarouselImage.jpg - An image that rotates through each of the cameras,
switrching every 3 seconds.

Snapshot Directory/0000[1-9].jpg - last 9 snapshot images taken via the snapshot action.

Sanpshot Directory/mosaic.jpg - mosaic image taken witht he mosaic action.

Motion Detection:
-----------------

Motion detection works by comparing the differences in pixels between the last image and image 00007.jpg and subtracting that number from the average difference of previous comparison.

If the difference is greater than the Sensitivy setting it registers a different frame (FrameDiff).  If the difference is less than the sensitivity it recalculates the average image difference.

If FrameDiff becomes greater than Different Frames in a Row setting then the MotionDetected state is set to true.  After x seconds (as determined by the Seconds Until Reset setting) the MotionDetected is set to false.

Tested Cameras:
---------------

Generic camera (try first): username:password@ipaddddress/snapshot.cgi

D-Link: user:password@ipaddddress/image.jpg

Tenvis: user:password@ipaddress:7777/snapshot.cgi

Amrest: user:password@10.0.1.46/cgi-bin/snapshot.cgi?chn=1&u=user&p=password

LTS: with current firmware
