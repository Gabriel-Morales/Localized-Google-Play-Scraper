#!/usr/bin/env python3

import cv2 as cv
import os
import subprocess
import sys
import numpy as np
import re
import pyautogui
import time
import easyocr

from mss import mss, tools
from matplotlib import pyplot as plt

matcher = re.compile(r'^[ ]+0x.*')
matcher2 = re.compile(r'\$?[0-9]+')

ADB_PATH = "/home/gmo/Android/Sdk/platform-tools/"
SAVE_PATH = ""
reader = easyocr.Reader(['en']) # this needs to run only once to load the model into memory

# Can use xwinfo to get window information 

# xwininfo -root -children| sed -E 's/.*[Tt]erminal|[Gg]nome.*//g' | grep -E 'Android' | sed -e 's/^ *//'|grep -E "^0x"|awk '{ print $1 }'
# xwininfo -id <id from above>

# Take screenshot of active emulator window using info from the commands above

# Search for template image in screenshot

def getActiveWindows():

	output_window_choices = {}

	window_infos = subprocess.run(['xwininfo', '-root', '-children'], capture_output=True)
	windows = window_infos.stdout.decode('UTF-8').split('\n')
	
	idx = 1
	for win in windows:
		match_result = matcher.search(win)
		if match_result is not None:
			win_str = win.rstrip()
			win_str = win.lstrip()
			choice = win_str.split(' ', 1)
			print(f'{idx}.)\tID: {choice[0]}\tWINDOW NAME: {choice[1]}')
			output_window_choices[idx] = (choice[0], choice[1])
			idx += 1

	return output_window_choices


# Input is the Window ID. 
def getWindowInfo(selected_window):


	win_id = selected_window
	os.system(f'xdotool windowactivate {win_id}')
	window_details = subprocess.run(['xwininfo', '-id', win_id], capture_output=True)
	window_details_decoded =  window_details.stdout.decode('UTF-8')
	window_details_cleanesed = list(filter(lambda x: x != '' and x != ' ', window_details_decoded.split('\n')))
	window_details_cleanesed = list(map(lambda x: x.lstrip(), window_details_cleanesed))
	print(window_details_decoded)
	dims = {}
	for detail in window_details_cleanesed:
		if detail.startswith('Absolute upper-left') or detail.startswith('Height') or detail.startswith('Width'):
			splt = detail.split(':')
			dims[splt[0]] = int(splt[-1].lstrip())
	
	print(f'Captured dimensions: {dims}')
	return dims


def capture_screenshot(dims):

	time.sleep(1)
	print('Capturing screenshot...')
	img = None
	with mss() as sct:
		# The screen part to capture
		region = {'top': dims['Absolute upper-left Y'], 'left': dims['Absolute upper-left X'], 'width': dims['Width'], 'height': dims['Height']}
		img = sct.grab(region)

		#debug output
		tools.to_png(img.rgb, img.size, output='debug.png')

	return img


def execute_gplay_activity(screen_dims, app_id):
	base_command = f"{ADB_PATH}adb shell am start \"market://details?id={app_id}\""
	os.system(base_command)
	gplay_image = capture_screenshot(screen_dims)
	return gplay_image


def execute_match(tmplt_img_name, gplayimg, dims):
	
	reference_image = cv.imread('debug.png', cv.IMREAD_GRAYSCALE)
	template_image = cv.imread(tmplt_img_name, cv.IMREAD_GRAYSCALE)
	w, h = template_image.shape[::-1]
	w_r, h_r = reference_image.shape[::-1]
	
	# may have to remove later and just use different template images instead of trying to make this general.
	# if w > w_r or w < w_r:
	# 	#tested_constants -> 'Width': 534, 'Height': 1151
	# 	width_scale_factor = dims['Width'] / 534 # Obtains width scale factor to new width
	# 	height_scale_factor = dims['Height'] / 1151 #Obtains height scale factor to new width

	# 	up_width = w * width_scale_factor
	# 	up_height = h * height_scale_factor
	# 	up_points = (int(up_width), int(up_height))
	# 	template_image = cv.resize(template_image, up_points, interpolation= cv.INTER_AREA)



	method = 'cv.TM_CCOEFF'
	res = cv.matchTemplate(reference_image, template_image, eval(method))

	min_val, max_val, min_loc, max_loc = cv.minMaxLoc(res)

	top_left = max_loc

	# If the method is TM_SQDIFF or TM_SQDIFF_NORMED, take minimum
	if method in ['cv.TM_SQDIFF', 'cv.TM_SQDIFF_NORMED']:
		top_left = min_loc
	else:
		top_left = max_loc

	top_left_x = top_left[0]
	top_left_y = top_left[1]
	bottom_right_y = top_left[1]+h
	bottom_right_x = top_left[0] + w

	bottom_right = (top_left[0] + w, top_left[1] + h)

	# Copy image, then crop image to button (ROI)
	im2 = reference_image.copy()
	cropped = im2[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]]

	# debug
	cv.rectangle(reference_image,top_left, bottom_right, 0, 3)
	plt.imshow(reference_image)
	plt.show()

	
	result = reader.readtext(cropped, detail=0)

	if len(result) == 0:
		print('No text found for button. Skipping.')
		return None

	txt = result[-1]

	if txt != 'Install' or matcher2.search(txt) is not None:
		print(f'Found {txt}, skipping.')
		return None


	im2 = None
	cropped = None



	return (top_left_x, top_left_y, w, h)
	


def move_and_save_application(app_id):
	# find package path for current app id: > adb shell pm path com.example.someapp
	app_path_enc = subprocess.run([f'{ADB_PATH}adb', 'shell', 'pm', 'path', app_id], capture_output=True)
	app_path_dec = app_path_enc.stdout.decode('UTF-8').rstrip('\n')
	app_path_dec = app_path_dec.split('\n')[0].split(':')[-1]


	# Transfer app from phone to path: > adb pull /data/app/com.example.someapp-2.apk path/to/desired/destination
	os.system(f'{ADB_PATH}adb pull {app_path_dec} {SAVE_PATH}')

	os.system(f'mv {SAVE_PATH}/base.apk {SAVE_PATH}/{app_id}.apk')

	# Delete app from phone: > ./adb uninstall com.example.app
	os.system(f'{ADB_PATH}adb uninstall {app_id}')


def begin_scrape(tmplt_img_name, dims):

	id_list = []

	with open('./app_list.txt', 'r') as infile:
		for line in infile:
			if line.isspace():
				continue
			id_list.append(line.strip())

	for appid in id_list:
		gplayimg = execute_gplay_activity(dims, appid)
		mouse_coords = execute_match(tmplt_img_name, gplayimg, dims)
		
		if mouse_coords == None:
			continue

		# Move mouse to coords
		mouse_upper_left_x = mouse_coords[0]
		mouse_upper_left_y = mouse_coords[1]
		but_w = mouse_coords[2]
		but_h = mouse_coords[3]

		button_middle_x = dims['Absolute upper-left X'] + mouse_upper_left_x + (but_w)/2
		button_middle_y = dims['Absolute upper-left Y'] + mouse_upper_left_y + (but_h/2)

		# Move mouse to center of button
		pyautogui.moveTo(button_middle_x, button_middle_y)
		# Click on install button
		pyautogui.leftClick()
		# Give enough time to install the app 
		time.sleep(50)
		move_and_save_application(appid) 

		

if __name__ == "__main__":
	
	# This tool is tested using an Android emulator of a Pixel 6 Pro with API level 34 on Ubuntu 20.04 LTS focal. You will need to install xdotool.
	print('Note: It is suggested you create a new install-button template if you change window sizes (even if it works okay in large windows).\nThe original dimensions used for testing was a Width of 534, and a Height of 1151')

	if len(sys.argv) != 2:
		print('Usage: ./app_tool_andr.py <save_path>')
		sys.exit(0)

	SAVE_PATH = sys.argv[1]

	window_dict = getActiveWindows()

	choice = int(input('Select window from list by number: '))
	window_choice = window_dict[choice]

	print(f'\nSelected Window ID {window_choice[0]} with name {window_choice[1]}. WARNING: Do NOT move this window!')

	dimensions = getWindowInfo(window_choice[0])
	#capture_screenshot(dimensions)
	begin_scrape("install_button_template.png",dimensions)
