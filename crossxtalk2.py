#!/usr/bin/env python
from gi.repository import Gtk, Gdk

from array import array
from struct import pack
from sys import byteorder
import copy
import pyaudio
import wave
from threading import Thread 
import socket
import time
from Queue import Queue
import subprocess

WIDTH = 2
RATE = 22050
CHANNELS = 2
CHUNK = 1024
RECORD_SECONDS = 20

MSGLEN= 4096

class EntryWindow(Gtk.Window):

    password = "password"
    port = "6000"
    server_address = "localhost"
    username = "username"
    recording = False
    audio_recording_thread  = ''
    sock=None
    q = ''
    audio_queue = ''
    connected=False
    connection_thread = ''
    users = []
    rating = 50
    last_currently_speaking_update=0

    current_user_end = 0

    def __init__(self):

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.q = Queue()
        self.rating=1
        self.audio_queue = Queue()

        self.builder = Gtk.Builder()
        self.builder.add_from_file("crossxtalk3.glade")
        self.builder.connect_signals(self)

        self.window = self.builder.get_object("window1")
        self.window.show_all()

        Gtk.main()

    def connect(self, host, port):
        self.sock.connect((host, port))

    def receive(self, size):
        msg = ''
        while len(msg) < size:
            chunk = self.sock.recv(size-len(msg))
            if chunk == '':
                raise RuntimeError("socket connection broken")
            msg = msg + chunk
        return msg

    def send(self, msg):

        while len(msg) < MSGLEN:
            msg += ' '

        totalsent = 0
        while(totalsent<len(msg)):
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            totalsent += sent

    def receive(self):
        msg = ''
        size = MSGLEN
        while len(msg) < size:
            chunk = self.sock.recv(size-len(msg))
            if chunk == '':
                raise RuntimeError("socket connection broken")
            msg = msg + chunk
        return msg    

    def do_external_process(self, command):
        print command

        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        output = process.communicate()
        retcode = process.poll()
        if retcode:
            raise subprocess.CalledProcessError(retcode, command, output=output[0])
        return output

    def train_new_user(self, filename, username):
        output = self.do_external_process('vid -s %s -g %s'%(username, filename))
        print output[0]

    def set_user_rating_thread(self, filename, username):
        output = self.do_external_process('vid -i %s'%filename)

        if(output[0].find('best speaker: S0 ('+username)!=-1):
            match=5
            output = self.do_external_process('vid -s %s -g %s'%(username, filename))
        else:
            match=-10

        for x in range(len(self.users)):
            if(self.users[x][0]==username):
                self.users[x][1]=self.users[x][1]+match
                print self.users[x][0]+' user\'s rating is now '+str(self.users[x][1])
                if(self.users[x][1]<0):
                    self.users[x][1]=0
                if(self.users[x][1]>100):
                    self.users[x][1]=100

        print output[0]


    def on_ban_clicked(self, button):
        for x in range(len(self.users)):
            if(button.get_label().find(self.users[x][0])==0 and self.users[x][1]<30):
                print("Ban performed on user %s, queue command to communication thread"%self.users[x][0])
                self.users[x][1]=0
            elif(button.get_label().find(self.users[x][0])==0):
                print("Ban not performed on user %s"%self.users[x][0])
                
    def gui_thread(self, index, newuser, current_rating, currently_speaking):
        listbox = self.builder.get_object('box4')
        labelbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        label_username = Gtk.Label('Username: '+newuser)
        label_rating = Gtk.Label('Rating: %d'%current_rating)
        label_speaking = Gtk.Label()
        if(currently_speaking>0):
            label_speaking.set_text("Currently speaking")
        else:
            label_speaking.set_text("Currently not speaking")
        
        label_username.set_justify(Gtk.Justification.LEFT)
        label_username.create_pango_layout('')
        label_username.set_alignment(0, 0)
        label_rating.set_justify(Gtk.Justification.LEFT)
        label_rating.set_alignment(0, 0)
        label_rating.create_pango_layout('')
        label_speaking.set_justify(Gtk.Justification.LEFT)
        label_speaking.set_alignment(0, 0)
        label_speaking.create_pango_layout('')

        button = Gtk.Button('Ban '+newuser)                        
        button.connect("clicked", self.on_ban_clicked)

        labelbox.set_spacing(2)
        labelbox.set_homogeneous(True)
        hbox.set_spacing(2)
        hbox.set_homogeneous(True)
        row.set_spacing(2)
        row.set_homogeneous(True)

        labelbox.pack_start(label_username, True, True, 0)
        labelbox.pack_start(label_rating, True, True, 0)
        labelbox.pack_start(label_speaking, True, True, 0)
        
        hbox.pack_start(labelbox, True, True, 0)
        hbox.pack_start(button, True, True, 0)
        
        row.pack_start(hbox, True, True, 0)
        listbox.pack_start(row, True, True, 0)

        row.show_all()
       
        
        while(self.users[index][5]==True and self.connected==True):
            label_rating.set_text('Rating: %d'%self.users[index][1])
            if(self.users[index][2]>0):
                label_speaking.set_text("Currently speaking")
            else:
                label_speaking.set_text("Currently not speaking")
            time.sleep(1)
        
        listbox.remove(row)

    def communication_thread(self):
        print("Trying to communicate with " + self.server_address + ":" + self.port )

        while(self.rating>0 and self.connected==True):
            if(self.q.qsize()>0):
                wf = self.q.get()
                self.q.task_done()
                self.send("SEND TO STREAM 0x%08x %s" %( len(wf), self.username))
                response = self.receive()
                if(response.startswith("OK")):
                    self.send(wf)

            self.send("GET NUMBER OF USERS")
            bytes_ready = self.receive()
            bytes_ready , sep , remaining = bytes_ready.partition(' ')
            if(int(bytes_ready, 16)>0):
                user_end_entry = int(bytes_ready, 16)
                for x in range(len(self.users)):
                    self.users[x][6]=False
                
                temp_index=0
                while(temp_index < user_end_entry):
                    self.send("GET USER INFO 0x%08x" % temp_index)
                    bytes_ready = self.receive()
                    newuser, sep, bytes_ready = bytes_ready.partition(" ")
                    current_rating, sep, bytes_ready = bytes_ready.partition(" ")
                    currently_speaking, sep, bytes_ready = bytes_ready.partition(" ")
                    wf = ''
                    
                    currently_speaking = int(currently_speaking, 16)
                    if(currently_speaking > 0):
                        currently_speaking = 1
                    if(currently_speaking <0):
                        currently_speaking = 0
                    
                    current_rating = int(current_rating, 16)
                    if(current_rating > 100):
                        current_rating = 100
                    if(current_rating < 0):
                        current_rating = 0

                    found=False                    
                    #immediatly download any audio packet information for the given user
                    if(newuser!=self.username and newuser!=''):
                        if(currently_speaking>0):
                            self.send("GET BYTES READY ON STREAM %s" % newuser)
                            bytes_ready = self.receive()
                            bytes_ready, sep, remaining = bytes_ready.partition(' ')
                            remaining_packets = int(bytes_ready, 16)
                            while(remaining_packets>0):
                                self.send("GET FROM STREAM %s 0x%08x" % (newuser, int(bytes_ready, 16)))
                                wf = self.receive()
                                remaining_packets=remaining_packets-len(wf)

                        for x in range(len(self.users)):
                            if(self.users[x][0]==newuser):
                                found=True
                                #first submit what the current users's rating is locally
                                if(self.users[x][1]==0):
                                    self.send("BAN USER "+self.users[x][0])
                                    response = self.receive()
                                else:
                                    self.send("UPDATE RATING "+self.users[x][0]+' '+str(self.users[x][1]))
                                    response = self.receive()

                                #then update new rating information, as well as update GUI content
                                if(self.users[x][1]!=current_rating):
                                    self.users[x][1]=current_rating
                                    print 'Updating current rating of %d'%current_rating

                                if(self.users[x][2]!=currently_speaking and time.clock() > self.last_currently_speaking_update+5):
                                    self.last_currently_speaking_update=time.clock()
                                    self.users[x][2] = currently_speaking
                                    print 'Updating currently speaking to %d'%currently_speaking
 
                                self.users[x][6] = True
                                
                                #if there are any packets only 
                                if(wf!=''):
                                    self.users[x][3].put(wf)
                                break
 
                        if(found==False):
                            self.last_gui_update = time.clock()
                            user_queue = Queue()
                            if(currently_speaking):
                                user_queue.put(wf)
                            t = Thread( target = self.play_audio_from_receive, args=(len(self.users), ))
                            gui_thread = Thread( target = self.gui_thread, args=(len(self.users),newuser, current_rating, currently_speaking, ))

                            print "adding %s row"%newuser

                            self.users.append([newuser, current_rating, currently_speaking, user_queue, t, True, True, gui_thread])
                            t.start()
                            gui_thread.start()
 
                    elif(self.username==newuser):
                        self.rating = current_rating

                    temp_index = temp_index+1

                for x in range(len(self.users)):
                    if(self.users[x][6]==False and self.users[x][5]==True and self.users[x][0]!='' and self.users[x][0]!=self.username):
                        self.users[x][5]=False
                        self.users[x][4].join()
                        print "audio playback thread has been joined"                        

            
    def play_audio_from_receive(self, index):
        print( "Playing Audio Stream %d"%index )

        p = pyaudio.PyAudio()

        stream = p.open(format=p.get_format_from_width(WIDTH), channels=CHANNELS, rate=RATE, input=False, output=True, frames_per_buffer=CHUNK)

        first_time=True

        count=int(RATE/CHUNK * RECORD_SECONDS)
        frames=[]
        while self.users[index][5]==True and self.connected==True:
            if( self.users[index][3].qsize()>0 ):
                buf = self.users[index][3].get()
                stream.write(buf, CHUNK)
                self.users[index][3].task_done()
                count-=1
                frames.append(buf)
                if(count==0):
                    filename=self.users[index][0]+str(time.time())+'.wav'
                    wf = wave.open(filename, 'wb')
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(WIDTH)
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(frames))
                    wf.close()
                    count=int(RATE/CHUNK * RECORD_SECONDS)
                    frames=[]


                    if(first_time):
                        t = Thread( target = self.train_new_user, args=(filename, self.users[index][0],  ))
                        t.start()                       
                    else:
                        t = Thread( target = self.set_user_rating_thread, args=(filename, self.users[index][0],  ))
                        t.start()

                    first_time=False
                    
        stream.stop_stream()
        stream.close()

        p.terminate()



    def record_and_send(self):
        """Record a word or words from the microphone and 
        return the data as an array of signed shorts."""
        p = pyaudio.PyAudio()

        stream = p.open(format=p.get_format_from_width(WIDTH), channels=CHANNELS, rate=RATE, input=True, output=False, frames_per_buffer=CHUNK)
        
        print( "Recording audio sample" )

        while self.recording==True and self.connected==True:
            buf = stream.read(CHUNK)
            self.q.put(buf)

        stream.stop_stream()
        stream.close()

        p.terminate()


	
    def onDeleteWindow(self, *args):
        self.rating=0
        Gtk.main_quit(*args)

    def onButtonPressed(self, button):
        if(self.server_address!='' and self.port!='' and self.connected==False):
            print("Trying to connect to " + self.server_address + ":" + self.port)
            self.connect(self.server_address, int(self.port))
            self.connected=True
            self.connection_thread = Thread( target = self.communication_thread )
            self.connection_thread.start()
            buf = ''
            while(len(buf)<CHUNK):
                buf+= '\x00'
            self.q.put(buf)


        else:
            self.connected=False
            self.connection_thread.join()
            self.sock.close()

            print("Disconnected")

    def onPasswordEntryChange(self, widget):
        entry = self.builder.get_object('password_entry')
        self.password = entry.get_text()

    def onUsernameEntryChange(self, widget):
        entry = self.builder.get_object('username_entry')		
        self.username = entry.get_text()

    def onServerAddressEntryChange(self, widget):
        entry = self.builder.get_object('server_address_entry')
        self.server_address = entry.get_text()

    def onPortEntryChange(self, widget):
        entry = self.builder.get_object('port_entry')
        self.port = entry.get_text()

    def onKeyPress(self, widget, ev, data=None):
        if ev.keyval == Gdk.KEY_Control_L: 
            print('key press')
            if(self.recording==False):
                self.recording = True
                self.audio_recording_thread = Thread(target = self.record_and_send )
                self.audio_recording_thread.start()

    def onKeyRelease(self, widget, ev, data=None):
        if ev.keyval == Gdk.KEY_Control_L:
            print('key release') 
            self.recording = False
            self.audio_recording_thread.join()

win = EntryWindow()





