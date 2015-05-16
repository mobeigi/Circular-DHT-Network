#
# COMP3331 - Socker Programming Assignment
#
# Circular DHT Program capable of peer churn (leave) and sending/receiving ping/file transfer signals.
#
# The extended version of the assignment has been attempted (cdht_ex).
#
# Tested and developed on: Python 2.7
#
# Developed By: Mohammad Ghasembeigi (z3464208)
#

#! /usr/bin/python

import sys
import colors #for important number highlighting, by Jossef Harush, source: https://gist.github.com/Jossef/0ee20314577925b4027f
import socket
import time
import threading
import ctypes

#Global definitions
LOCALHOST = "127.0.0.1"
BASE_PORT_OFFSET = 50000;
PINGREQ_TIMEOUT = 1.0; # How long sent ping will timeout
PINGMONITOR_TIMEOUT = 1.0; #How long to wait for a ping response to come in
PINGBUFFER = 6;
PINGSEND_FREQUENCY = 5.0; #How often to send a ping (seconds)


# By Johan Dahlin, http://stackoverflow.com/questions/323972/is-there-any-way-to-kill-a-thread-in-python
def terminate_thread(thread):
    """Terminates a python thread from another thread.

    :param thread: a threading.Thread instance
    """
    if not thread.isAlive():
        return

    exc = ctypes.py_object(SystemExit)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(thread.ident), exc)
    if res == 0:
        raise ValueError("nonexistent thread id")
    elif res > 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


def main(argv):

  # Not enough arguments
  if len(sys.argv) != 4:
    print >> sys.stderr, 'usage:', sys.argv[0], '[peer identifier] [successor #1 identifier] [successor #2 identifier]'
    exit(1);
  
  # Ensure all arguments are in [0, 255] range inclusive
  for argNum in range(1, len(sys.argv)):
    #Check for integer arguments and ensure within [0, 255] range
    if not (str.isdigit(sys.argv[argNum])) or not (0 <= int(sys.argv[argNum]) <= 255):
      print >> sys.stderr, colors.error('error:'), 'provided identifier (' + sys.argv[argNum] +') in argument', argNum ,'was not an integer in [0,255] (inclusive).'
      exit(1);

  #Collect all important arguments
  myPeer = int(sys.argv[1]);
  myPort = peerToPort(myPeer);
  succ1 = int(sys.argv[2]);
  succ2 = int(sys.argv[3]);
  Ping = enum(REQ=0, RES=1);

  # Print message to let people know peer is joining the CDHT network
  cprint ("[STATUS]", "Peer (" + printPeer(myPeer) + ") is attempting to join the CDHT network...");
  cprint ("[STATUS]", "Sucessfully joined CDHT network."); #simulate fake join message

  cprint ("[STATUS]", "Welcome to this CDHT network! (instructions should go here) ");
  
  tPingMonitor = threading.Thread(target=pingMonitor, args=(myPeer, myPort, succ1, succ2, Ping));
  tPingMonitor.start();

  # Monitor stdin for commands
  while True:

    try:
      inputCommand = str.strip(sys.stdin.readline());

      # Check for valid input commands
      if inputCommand.lower() == "quit" or inputCommand.lower() == "q":
        terminate_thread(tPingMonitor); #kill threads
        cprint ("[STATUS]", "Leaving CDHT network and terminating program. Please wait for running threads to terminate."); #quit message
        exit(0);
      #Invalid command      
      else:
        cprint ("[STATUS]", "Invalid command provided."); #quit message

    except IOError:
      pass; 



def pingMonitor(myPeer, myPort, succ1, succ2, Ping):

  # Create socket that is to be used for listening for messages
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM);
  sock.settimeout(PINGMONITOR_TIMEOUT);
  sock.bind((LOCALHOST, myPort));

  lastPingsSent = 0;

  while True:
    # Send pings to successors at each PINGSENDTIME timestep
    if (time.time() - lastPingsSent) > PINGSEND_FREQUENCY:
      # Send pings requests to each successor
      sendPing(Ping.REQ, myPeer, LOCALHOST, peerToPort(succ1));
      sendPing(Ping.REQ, myPeer, LOCALHOST, peerToPort(succ2));

      #Update lastPingsSent time
      lastPingsSent = time.time();


    # Monitor myPort for incoming messages 
    #Get start time
    startTime = time.time();
    elapsed = 0.0; #time taken to receive a ping request (in this loop)

    try:
      data, addr = sock.recvfrom(PINGBUFFER);
      elapsed = time.time() - startTime;
      
      msgType = ord(data[0]); # get message type
      senderPeerID = data[1:]; #rest of message is the senders ID

      # Check for ping request message
      if msgType == Ping.REQ:
        cprint("[PING REQ]", "A ping request message was received from Peer " + printPeer(senderPeerID));

        #Send a ping response back (in response to ping request)
        sendPing(Ping.RES, myPeer, LOCALHOST, peerToPort(int(senderPeerID)));
      elif msgType == Ping.RES:
        cprint("[PING RES]", "A ping response message was received from Peer " + printPeer(senderPeerID));

      sys.stdout.flush();
    except socket.error:
      pass;


# Ping Functions (UDP)
# Sends a single ping to targetIP and targetPort using UDP
# Message format is as follows:
# Message Type - 0x00 for ping request
# Sender Identifier - must be sent as each client is also server (cant send ping over listening port).

def sendPing(msgType, myID, targetIP, targetPort):
  #start with default ping request message
  message = bytearray([msgType]);
  
  #append senders peer identifier
  message.extend(str(myID));
  
  #Send UDP datagram
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); #UDP
  sock.settimeout(PINGREQ_TIMEOUT);
  sock.sendto(message, (targetIP, targetPort));

# Convert peer ID to the port the peer will be using to listen for messages
def peerToPort(peerID):
  return BASE_PORT_OFFSET + peerID;

#Additional print functions

# Returns a tabular formated line with a control signal and an associated message
def cprint(control, message):
  formatedControl = printControl(control);

  for i in range(0, 8 - len(control)):
    formatedControl += " ";

  print '{:<8} {:<8}'.format(formatedControl, message);

def printPeer(peerID):
  return printGreen(peerID);

def printGreen(text):
  return colors.draw(str(text), fg_green=True);

def printControl(text):
  return colors.draw(text, fg_blue = True, bg_light_grey=True);


def enum(**enums):
  return type('Enum', (), enums);

if __name__ == "__main__":
  main(sys.argv[1:])
