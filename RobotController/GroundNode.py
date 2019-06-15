# Imports for Logging
import logging

# Imports for Threading
import threading
import keyboard

# Imports for Video Streaming
import sys
sys.path.insert(0, 'imagezmq/imagezmq')

import cv2
import imagezmq

# Imports for Socket Communication
import socket
import CommunicationUtils
import simplejson as json
import time
import keyboard

# Imports for Controller Communication and Processing
import ControllerUtils
import evdev

# Settings Dict to keep track of editable settings for data processing
settings = {
    "numCams": 4,
    "drive": "holonomic",
    "numMotors": 6,
    "flipMotors": [1]*6
}

# Dict to stop threads
execute = {
    "streamVideo": True,
    "receiveData": True,
    "sendData": True,
    "updateSettings": True
}

def stopAllThreads(callback=0):
    """ Stops all currently running threads
        
        Argument:
            callback: (optional) callback event
    """

    execute['streamVideo'] = False
    execute['receiveData'] = False
    execute['sendData'] = False
    execute['updateSettings'] = False
    logging.debug("Stopping Threads")

def receiveVideoStreams(debug=False):
    """ Recieves and processes video from the Water Node

        Arguments:
            display: (optional) display recieved images using OpenCV
            debug: (optional) log debugging data
    """

    image_hub = imagezmq.ImageHub()
    while execute['streamVideo']:
        deviceName, image = image_hub.recv_image()
        if debug:
            print(image)
        image_hub.send_reply(b'OK')
    logging.debug("Stopped VideoStream")

def receiveData(debug=False):
    """ Recieves and processes JSON data from the Water Node

        Data will most likely be sensor data from an IMU and voltage/amperage sensor

        Arguments:
            debug: (optional) log debugging data
    """

    HOST = '127.0.0.1'
    PORT = CommunicationUtils.SNSR_PORT

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as snsr:
            try:
                snsr.bind((HOST, PORT))
            except:
                logging.info("Port {} is already in use".format(PORT))
                time.sleep(10)
                snsr.bind((HOST, PORT))
            snsr.listen()
            conn, addr = snsr.accept()
            logging.info('Sensor Socket Connected by '+str(addr))

            while execute['receiveData']:
                try:
                    recv = CommunicationUtils.recvMsg(conn)
                    j = json.loads(recv)
                    if debug:
                        logging.debug("Raw receive: "+str(recv))
                        logging.debug("TtS: "+str(time.time()-float(j['timestamp'])))
                except Exception as e:
                    logging.debug(e)
    except Exception as e:
        logging.error("Receive Exception Occurred",exc_info=True)
    logging.debug("Stopped recvData")

def sendData(debug=False):
    """ Sends JSON data to the Water Node

        Data will most likel contain motor data, and settings changes

        Arguments:
            debug: (optional) log debugging data
    """
    HOST = '127.0.0.1'
    PORT = CommunicationUtils.CNTLR_PORT

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as cntlr:
            # Setup socket communication
            try:
                cntlr.bind((HOST, PORT))
            except:
                logging.info("Port {} is already in use".format(PORT))
                time.sleep(10)
                cntlr.bind((HOST, PORT))
            cntlr.listen()
            conn, addr = cntlr.accept()
            logging.info('Motor Socket Connected by '+str(addr))

            # Start the update settings thread
            updtSettingsThread = threading.Thread(target=updateSettings, args=(conn,debug,))
            updtSettingsThread.start()

            # Start Controller
            gamepad = ControllerUtils.identifyControllers()
            while (not gamepad) and execute['sendData']:
                time.sleep(5)
                gamepad = ControllerUtils.identifyControllers()

            while execute['sendData']:
                event = gamepad.read_one()
                if event:
                    if (ControllerUtils.isStopCode(event)):
                        logging.debug(CommunicationUtils.sendMsg(conn,"closing","connInfo","None",repetitions=2))
                        time.sleep(2)
                        stopAllThreads()
                        break
                    ControllerUtils.processEvent(event)
                    speeds = ControllerUtils.calcThrust()
                    sent = CommunicationUtils.sendMsg(conn,speeds,"motorSpds","None",isString=False)
                    if debug:
                        time.sleep(1)
                        logging.debug("Sending: "+str(sent))

            updtSettingsThread.join()

    except Exception as e:
        logging.error("Send Exception Occurred",exc_info=True)
    logging.debug("Stopped sendData")

def updateSettings(sckt,debug=False):
    """ Receives setting updates from the Air Node and makes edits

        Most changes will be made to settings in the Ground Node, but some will be sent to the Water Node

        Arguments:
            sckt: socket to communicate with the Water Node
            debug: (optional) log debugging data
    """
    # Wait until a setting is updated, then make the change and or sent data to the water node
    while execute['updateSettings']:
        time.sleep(2)
    logging.debug("Stopped updateSettings")

if( __name__ == "__main__"):
    # Setup Logging preferences
    verbose = [False,True]
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

    # Setup a callback to force stop the program
    keyboard.on_press_key("q", stopAllThreads, suppress=False)

    # Start each thread
    logging.info("Starting Ground Node")
    logging.debug("Started all Threads")
    vidStreamThread = threading.Thread(target=receiveVideoStreams, args=(verbose[0],),daemon=True)
    recvDataThread = threading.Thread(target=receiveData, args=(verbose[0],))
    sendDataThread = threading.Thread(target=sendData, args=(verbose[0],))
    vidStreamThread.start()
    recvDataThread.start()
    sendDataThread.start()

    # Begin the Shutdown
        # Because there is no timeout on recvDataThread or sendDataThread, they won't join until manually stopped
        # It's a bit of a hack, but it stops the program from shuting down instantly
    recvDataThread.join()
    sendDataThread.join()
    vidStreamThread.join(timeout=5)
    logging.debug("Stopped all Threads")
    logging.info("Shutting Down Ground Node")
    sys.exit()