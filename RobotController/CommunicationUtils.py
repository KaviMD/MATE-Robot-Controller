import json
import time
import socket
import base64
import cv2

def sendMsg(sckt,data,dataType,metadata):
	msg = "<{"
	msg += '"dataType":"'+str(dataType)+'",'
	msg += '"data":"'+str(data)+'",'
	msg += '"timestamp":'+str(time.time())+','
	msg += '"metadata":"'+str(metadata)+'"'
	msg += "}>"
	sckt.sendall(msg.encode())
	return msg

def recvMsg(conn):
	startMarker = b'<'
	endMarker = b'>'
	recvInProgress = False
	recv = b''

	while(conn.recv(1, socket.MSG_PEEK)):
		data = conn.recv(1)
		if(recvInProgress):
			if(data != endMarker):
				recv += data
			else:
				recvInProgress = False
				break
		if(data == startMarker):
			recvInProgress = True
	return recv.decode()

def encode_img(image):
	retval, bffr = cv2.imencode('.jpg', image)
	return base64.b64encode(bffr).decode("utf-8") 