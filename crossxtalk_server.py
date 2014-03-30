#!/usr/bin/env python

import socket, threading
from Queue import Queue

MSGLEN = 1024*4

class ClientThread(threading.Thread):

    username =""
    ip = ""
    port = 0
    q =""
    rating = 50
    known_users = []
    disconnect=False

    def __init__(self,ip,port,socket):
        threading.Thread.__init__(self)
        self.ip = ip
        self.port = port
        self.socket = socket
        print "[+] New thread started for "+ip+":"+str(port)

    def send(self, msg):

        while len(msg) < MSGLEN:
            msg += ' '

        totalsent = 0
        while(totalsent<len(msg)):
            sent = self.socket.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent += sent


    def receive(self):
        msg = ""
        size = MSGLEN
        while len(msg) < size:
            chunk = self.socket.recv(size-len(msg))
            if chunk == "":
                raise RuntimeError("socket connection broken")
            msg = msg + chunk
        return msg

    def do_get_size_of_stream(self, data):
        (pre, sep, username) = data.partition("STREAM ")
        (username, sep, after) = username.partition(" ")
        found=False
        for usernames, queue in self.known_users:
            if(usernames==username):
                found=True
                if(queue.qsize()>0):
                    self.send("0x%08x"%(queue.qsize()*0x1000))
                else:
                    self.send("0x00000000")
                break
        if(found==False):
            self.send("0x00000000")

    def do_get_stream(self, data):
        (pre, sep, data) = data.partition("STREAM ")
        (username, sep, data) = data.partition(" ")
        (numbytes, sep, data) = data.partition(" ")
        numbytes = int(numbytes, 16)
        found=False
        for usernames, queue in self.known_users:
            if(usernames==username):
                found=True
                if(queue.qsize()*MSGLEN>=numbytes):
                    buf = queue.get()
                    queue.task_done()
                    self.send(buf)
                else:
                    self.send('')
        if(not found):
            self.send('')

    def do_send_stream_from_client(self, data):
        (pre, sep, data) = data.partition("STREAM ")
        (numbytes, sep, data) = data.partition(" ")
        (username, sep, data) = data.partition(" ")
        self.send("OK")
        wf = self.receive()
        self.username = username
        if(len(self.known_users)==0):
            for t in threads:
                if(t.username != self.username):
                    self.known_users.append((t.username, Queue()))
        for t in threads:
            if(t.username != self.username):
                previously_known=False
                for other_username, queue in t.known_users:
                    if(other_username==username):
                        queue.put(wf)
                        previously_known=True
                if(not previously_known):
                    newqueue = Queue()
                    t.known_users.append((username, newqueue))
                    newqueue.put(wf)

    def get_user_info(self, data):
        (pre, sep, index) = data.partition("INFO ")
        (index, sep, remaining) = index.partition(" ")
        index = int(index, 16)

        if(index<len(threads) and len(self.known_users)>0):
            found_username=False
            for usernames, queue in self.known_users:
                if(usernames==threads[index].username):
                    found_username=True
                    if(queue.qsize()>0):
                        self.send("%s 0x%08x 0%08x" % (usernames, threads[index].rating, 1 ))
                    else:
                        self.send("%s 0x%08x 0%08x" % (usernames, threads[index].rating, 0 ))
                    break
            if(found_username==False):
                self.send("none 0 0")

        elif(len(self.known_users)==0 and index<len(threads)):
            self.send("%s 0x%08x 0" %(self.username, threads[index].rating))
        else:
            self.send("none 0 0")   

    def get_num_of_threads(self, data):
        self.send("0x%08x"%len(threads))

    def disconnect_user(self, data):
        (pre, sep, userinfo) = data.partition("USER ")
        (user, sep, remaining) = userinfo.partition(" ")
        found_username = False
        self.send("OK")
        for t in threads:
            if user == t.username:
                t.sock.close()
                t.disconnect=True
                break

    def set_user_info(self, data):
        (pre, sep, data) = data.partition("RATING ")
        (username, sep, data) = data.partition(" ")
        (rating, sep, data) = data.partition(" ")
        rating = int(rating, 16)

        found_username=False
        for x in range(len(threads)):
            if(threads[x].username==username):
                found_username=True
                threads[x].rating = rating
                break

        self.send("OK")

    def run(self):    
        print "Connection from : "+ip+":"+str(port)

        data = " "
        while(len(data)>0 and self.disconnect==False):
            data = self.receive()
            if(data.startswith("GET BYTES READY ON STREAM ")):
                self.do_get_size_of_stream(data)
            if(data.startswith("GET FROM STREAM ")):   
                self.do_get_stream(data)
            if(data.startswith("SEND TO STREAM ")):
                self.do_send_stream_from_client(data)
            if(data.startswith("GET NUMBER OF USERS")):
                self.get_num_of_threads(data)
            if(data.startswith("GET USER INFO ")):
                self.get_user_info(data)
            if(data.startswith("BAN USER ")):
                self.disconnect_user(data)
            if(data.startswith("UPDATE RATING ")):
                self.set_user_info(data)
                      

        print "Client disconnected..."

host = "0.0.0.0"
port = 6000

tcpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcpsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

tcpsock.bind((host,port))
threads = []

while True:
    tcpsock.listen(4)
    print "\nListening for incoming connections..."
    (sock, (ip, port)) = tcpsock.accept()
    newthread = ClientThread(ip, port, sock)
    newthread.start()
    threads.append(newthread)

for t in threads:
    t.join()
