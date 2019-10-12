import socket
import thread
import sys
import time
import simplejson as json
import threading
import os
import sys
from datetime import datetime as dt, timedelta
import pdb


port_c = 6666
interface_port = {"http":80,"https":443,"ftp":20,"smtp":25}
 
MAX_REQUEST = 4096
BLACKLIST = "blacklist.txt"
CACHE = "./cache"
locks = {}
blocked = []

def getAccess (url):
	if url in locks :
		lock = locks[url]
	else:
		lock = threading.Lock()
		locks[url] = lock
	lock.acquire()

def leaveAccess (url):
	if url in locks:
		lock = locks[url]
		lock.release()

def loadBlackList ():
	f = open(BLACKLIST,'r')
	data = ""
	while True:
		dummy = f.read()
		if len(dummy)>0:
			data+=dummy
		else:
			f.close()
			break
	return data.splitlines()
	

#Load BlackList o day
blocked = loadBlackList()

#Luu vao cache hay khong
def doCacheProxy (url,lastModifiedTime):
	try:
		if lastModifiedTime is None:
			return True
		else:
			last = dt.fromtimestamp(time.mktime(lastModifiedTime))			

		if dt.now() - last <= timedelta(minutes=10):
			return False
		else:
			return True
	except Exception:
		print ("loi do cache: "+str(Exception))
		return False

#lay thong tin cua url trong cache
def getInfoCache(url):
	try:
		cachePath = CACHE + "/" + url.replace("/","_")
		if os.path.exists(cachePath):
			lastModifiedTime =time.strptime(time.ctime(os.path.getmtime(cachePath)),"%a %b %d %H:%M:%S %Y")
			return cachePath,lastModifiedTime  
		else:
			return cachePath, None
	except Exception:
		print("Loi lay info Cache"+str(Exception))
		return None, None 

#chen them hear vao request
def insertModifiedHeader (details):
	request = details["request"]
	modifiedHeader = "If-Modified-Since: " + time.strftime("%a %b %d %H:%M:%S %y",details["last_mtime"])
	details["request"] = request.strip("\r\n") + "\r\n" + modifiedHeader + "\r\n\r\n"
	return details

			

def getCacheDetails (client_addr, details):
	getAccess(details["url"])
	cachePath, lastModifiedTime = getInfoCache(details["url"])
	doCache = doCacheProxy(details["url"],lastModifiedTime)
	leaveAccess(details["url"])
	return doCache, cachePath, lastModifiedTime

#Get
def serverGetRequest(conn,client_addr,details):
	request = details["request"]
	doCache = details["doCache"]
	cachePath = details["cachePath"]
	lastModifiedTime = details["last_mtime"]
	
	try:
		sv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sv.connect ((details["webserver"],details["port"]))
		sv.send(details["request"])

		reply = sv.recv(MAX_REQUEST)

		if lastModifiedTime or "304 Not Modified" in reply:
			print ("returning cache")
			getAccess(details["url"])
			f = open(cachePath, "rb")
			dummy = f.read(MAX_REQUEST)
			while  len(dummy) > 0:
				conn.send(dummy)
				dummy = f.read(MAX_REQUEST)
			f.close()
			leaveAccess(details["url"])
		else:
			if doCache is True:
				print ("luu vao cache")
				getAccess(details["url"])
				f = open(cachePath, "w+")
				while len(reply)>0:
					conn.send(reply)
					f.write(reply)
					reply = sv.recv(MAX_REQUEST)
			
				f.close()
				leaveAccess(details["url"])
				conn.send("/r/n/r/n")
			else:
				print ("chay bt")
				while len(reply)>0:
					conn.send(reply)
					reply = sv.recv(MAX_REQUEST)
				conn.send("/r/n/r/n")

	except Exception :
		print ("Loi Proxy Get: "+  str(Exception))
	finally :
		sv.close()
		conn.close()
		return

#Post
def serverPostRequest(conn,client_addr,details):
	try:
		sv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sv.connect((details["webserver"],details["port"]))
		sv.send(details["request"])
		
		while True:
			reply = sv.recv(MAX_REQUEST)
			if len(reply):
				conn.send(reply)
			else:
				break
	except Exception:
		print("Loi Proxy Post: " + str(Exception))
	finally:
		sv.close()
		conn.close()
		return

	
	
#lay thong tin ve request cua browser
def getDetails (conn, client_addr):
	
	request = conn.recv(MAX_REQUEST)

	lines = request.splitlines()

	fisrt_line = lines[0]
	
	dummy = fisrt_line.split(' ')

	method = dummy[0]
		
	url = dummy[1]

	protocol_pos = url.find("://")
	protocol = url[:protocol_pos]
	
	url = url[(protocol_pos+3):]

	port = interface_port[str(protocol)]
	
	webserver = lines[1].split(" ")[1]

	return {
		"method":method,
		"webserver":webserver,
		"port":port,
		"request":request,
		"url":url
		}

#ktra url co thuoc danh sach blacklist
def isBlock (conn,client_addri,details):
	if not (details["webserver"]+":"+str(details["port"])) in blocked:
		return False
	return True

#tien trinh tu proxy -> webserver -> proxy -> client
def proxy (conn,client_addr):
	details = getDetails(conn,client_addr)

	if isBlock(conn,client_addr,details):
		conn.send("HTTP/1.0 200 OK\r\n")
		conn.send("Content-Length: 11\r\n")
		conn.send("\r\n")
		conn.send("Error\r\n")
		conn.send("\r\n\r\n")
		conn.close()	
	elif details["method"] == "GET":
		details["doCache"], details["cachePath"], details["last_mtime"] = getCacheDetails(client_addr,details)
		if details["last_mtime"] is not None and details["doCache"] is False:
			details = insertModifiedHeader(details)
		serverGetRequest(conn,client_addr,details)
	elif details["method"] == "POST":
		serverPostRequest(conn,client_addr,details)
	else:
		conn.close()


#tien trinh tu browser -> proxy
def start_proxy():
	try:
		proxyServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		proxyServer.bind(('',port_c))
		proxyServer.listen(10)
		
	  
		while True:
			conn , client_addr = proxyServer.accept()
			d = thread.start_new_thread(proxy,(conn,client_addr))
	except Exception:
		print ("Loi Ket noi Proxy: "+str(Exception))
		conn.close()

def main():
	start_proxy()

if __name__ == '__main__':
	main()
