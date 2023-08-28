# Localized-Google-Play-Scraper
Locally (no API calls through terminal), download (scrape) apps directly from the Play Store through a phone and transfer it over adb into a desired destination.


Tested on Ubuntu 20.04 - requires X-based terminal tools: 
- xwininfo
- xdotool.<br>


Python requirements:
- easyocr
- opencv
- numpy
- pyautogui

How to use:
- Take a screenshot of a Google Play "Download" button for any app as a template image. For an example take a look at "install_button_template.png".
- Provide an application list (the identifiers) inside of the app_list.txt file.
- Open an Android emulator on your computer WITH GOOGLE PLAY INSTALLED; or remotely control an Android phone through the computer.
- Lauch the tool, provide a save path, and finally select the window of your Android phone process.

![til](./IMG_1125.gif)
