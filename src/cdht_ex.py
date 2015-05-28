#
# COMP3331 - Socket Programming Assignment
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
import re
import socket
import time
import threading
import ctypes

import curses;
from string import printable


#Global variables
LOCALHOST = "127.0.0.1"
BASE_PORT_OFFSET = 50000;
PINGREQ_TIMEOUT = 1.0; # How long sent ping will timeout
PINGMONITOR_TIMEOUT = 1.0; #How long to wait for a ping response to come in
PINGBUFFER = 7;
PINGSEND_FREQUENCY = 5.0; #How often to send a ping (seconds)
FILEMONITOR_TIMEOUT = 1.0;
THREADKILLTIME = 2.0; #How long to wait before terminating program (to allow thread to terminate)
MAXPEERNUM = 255;

SEQMAX = 1000;

#Curses vars
PRINTABLE = map(ord, printable)
COLOR_DEFAULT = -1;
MIN_REC_WIDTH = 110;

# Enumeration type definition
def enum(**enums):
  return type('Enum', (), enums);

# Enumns
Ping = enum(REQ=0, RES=1);
FT = enum(REQ=0, FORWARD=1, FORWARDNEXT=2, RES=3); #TCP Control codes
PEER = enum(INVALID=-1, DEAD=-2);
PEERCHURN = enum(QUIT=4, QUERYREQ=5, QUERYRES=6); #TCP Control codes
FILECHECK = enum(NOTAVAILABLE=0, AVAILABLE=1, NEXTAVAILABLE = 2);
Colours = enum(STATUS=1, WARNING=2, COMMAND=3, RED=4, GREEN=5, FILETRANSFER=6);


# Initialise application, check for valid arguments and initiate curses screen
def init(argv):

  # Not enough arguments
  if len(sys.argv) != 4:
    print >> sys.stderr, 'usage:', sys.argv[0], '[peer identifier] [successor #1 identifier] [successor #2 identifier]'
    exit(1);
  
  # Ensure all arguments are in [0, 255] range inclusive
  for argNum in range(1, len(sys.argv)):
    #Check for integer arguments and ensure within [0, 255] range
    if not (str.isdigit(sys.argv[argNum])) or not (0 <= int(sys.argv[argNum]) <= 255):
      print >> sys.stderr, 'error: provided identifier (' + sys.argv[argNum] +') in argument', argNum ,'was not an integer in [0,255] (inclusive).'
      exit(1);

  #Set all important arguments
  global myPeer, myPort, succ1, succ2, pred1, pred2;
  
  myPeer = int(sys.argv[1]);
  myPort = peerToPort(myPeer);
  succ1 = int(sys.argv[2]);
  succ2 = int(sys.argv[3]);
  pred1 = PEER.INVALID;
  pred2 = PEER.INVALID;

  curses.wrapper(main);


# Main function
# Attached to curse screen
# Loops indefinitely waiting for user input commands
def main(screen):
  Y, X = screen.getmaxyx()
  global max_lines;
  max_lines = (Y - 3)

  screen.clear(); #clear screen
  curses.use_default_colors(); #Use terminal default colours by default
  curses.start_color(); # allow colours in text

  # Colours pairs that will be used
  # Strings can use colour pair N by containing: colourN[str]
  # Where N is the pair number and str is the text to be coloured.
  curses.init_pair(Colours.STATUS, curses.COLOR_BLUE, curses.COLOR_WHITE);
  curses.init_pair(Colours.WARNING, curses.COLOR_RED, curses.COLOR_WHITE);
  curses.init_pair(Colours.COMMAND, curses.COLOR_CYAN, COLOR_DEFAULT);
  curses.init_pair(Colours.RED, curses.COLOR_RED, COLOR_DEFAULT);
  curses.init_pair(Colours.GREEN, curses.COLOR_GREEN, COLOR_DEFAULT);
  curses.init_pair(Colours.FILETRANSFER, curses.COLOR_WHITE, curses.COLOR_RED);

  # Create global lines that will store all visible lines on screen at any given time
  # Lines will contain tuples of command strings and message strings (ie lines acts like a 2D string array)
  global lines;
  lines = [];

  # Print message to let people know peer is joining the CDHT network
  consolePrint (screen, "[STATUS]", "Attempting to join the CDHT network as Peer (" + makeColComp(Colours.GREEN, str(myPeer)) + ")...");
  consolePrint (screen,  "[STATUS]", "Successfully joined CDHT network."); #simulate fake join message
  consolePrint (screen,  "[STATUS]", "Welcome to this CDHT network!");
  consolePrint (screen,  "[STATUS]", "Enter valid commands at the bottom of this terminal screen. Command " + makeColComp(Colours.COMMAND, "quit") + " will exit the application.");

  # Display error message if screen is too short
  height, width = screen.getmaxyx();
  if (width < MIN_REC_WIDTH):
    consolePrint (screen,  "[WARNING]", makeColComp(Colours.RED, "A minimum terminal width of " + str(MIN_REC_WIDTH) + " characters is recommended (current: " + str(width) + ")."));


  # Start ping monitor thread
  tPingMonitor = threading.Thread(target=pingMonitor, args=(screen, Ping));
  tPingMonitor.start();

  #Start file transfer monitor thread
  tTCPMonitor = threading.Thread(target=TCPMonitor, args=(screen, Ping));
  tTCPMonitor.start();

  #Loop indefinitely waiting for commands
  while True:

      s = prompt(screen, (Y - 1), 0);

      # Quit command
      if s == "quit":
        #This is a graceful exit, inform predecessors of exit
        sendChurnMessage(PEERCHURN.QUIT, succ1, succ2, myPeer, LOCALHOST, peerToPort(pred1));
        sendChurnMessage(PEERCHURN.QUIT, succ1, succ2, myPeer, LOCALHOST, peerToPort(pred2));

        terminate_thread(tPingMonitor); #kill threads
        terminate_thread(tTCPMonitor);
        consolePrint (screen, "[STATUS]", "Leaving CDHT network and terminating program. Please wait for running threads to terminate."); #quit message
        screen.refresh()  #Display last messages
        time.sleep(THREADKILLTIME); #Pause to allow thread to terminate        
        break;
      elif s.startswith("request"):
        reqFile = "";
        reqFileHash = -1;

        #Get file request parameter
        try:
          reqFile = s.split()[1];
        except:
          consolePrint (screen, "[STATUS]", "Invalid command parameters were provided. Provided command was: " + s);
          continue;

        #Ensure hash is valid
        try:
          reqFileHash = int(reqFile);
      
          # Check to see if integer is in valid range
          if not (0 <= reqFileHash <= 9999) or len(reqFile) != 4:
            raise ValueError('Invalid request file provided.') #throw exception
        except:
          consolePrint (screen, "[STATUS]", "Invalid file was requested. File name must be a 4 length numeral.");
          continue;

        #Check if this file is available at the next peer
        fileStatus = checkFileAvailable(reqFileHash);

        if fileStatus == FILECHECK.NOTAVAILABLE:
          #Send request normally
          sendFTMessage(reqFileHash, FT.REQ, myPeer, LOCALHOST, peerToPort(succ1));
        elif fileStatus == FILECHECK.AVAILABLE:
          #File is stored locally
          consolePrint (screen, "[FILE RES]",   "File " + makeColComp(Colours.RED, reqFile) + " is stored locally.");
          continue;
        elif fileStatus == FILECHECK.NEXTAVAILABLE:
          # The next peer has the file, send a special message
          sendFTMessage(reqFileHash, FT.FORWARDNEXT, myPeer, LOCALHOST, peerToPort(succ1));

        # Display file request sent message
        consolePrint (screen, "[FILE REQ]",   "File request message for " + makeColComp(Colours.RED, reqFile) + " has been sent to successor Peer (" + makeColComp(Colours.GREEN, str(succ1)) + ").");

      # Unknown command
      else:
        consolePrint (screen, "[STATUS]", "Invalid command '" + s + "' provided.");

      overflowCheck(screen);
      screen.refresh();

# Check if text has overflown and adjust screen accordingly
def overflowCheck(screen):
  global lines;
  global max_lines;
  
  if len(lines) >= max_lines:
    lines = lines[1:];


  # Clear all lines up to max_lines (this does not clear the command input line)
  for i in range(0, max_lines):
    screen.move(i, 0);
    screen.clrtoeol();

  for i, line in enumerate(lines):
      if i >= max_lines:
        break;
      consolePrintLine(screen, i, line[0], line[1]);


# Fetch user input (commands)
# By James Mills (http://stackoverflow.com/a/30259422/1800854)
def input(screen):
    ERASE = input.ERASE = getattr(input, "erasechar", ord(curses.erasechar()))
    Y, X = screen.getyx();
    s = [];

    while True:
        c = screen.getch();

        if c in (13, 10):
            break;
        elif c == ERASE or c == curses.KEY_BACKSPACE:
            y, x = screen.getyx();
            if x > X:
                del s[-1];
                screen.move(y, (x - 1));
                screen.clrtoeol();
                screen.refresh();
        elif c in PRINTABLE:
            s.append(chr(c));
            screen.addch(c);
        else:
            pass

    return "".join(s)

# Print input prompt on last line in curses screen
def prompt(screen, y, x, prompt=">> "):
    global myPeer;

    screen.move(y, x);
    screen.clrtoeol();
  
    # Print out input prompt line
    screen.addstr(y, x, prompt + "[PEER " + str(myPeer) + "]$ ");
    return input(screen);


# By Johan Dahlin (http://stackoverflow.com/a/15274929/1800854)
def terminate_thread(thread):
    if not thread.isAlive():
        return

    exc = ctypes.py_object(SystemExit);
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(thread.ident), exc);
    if res == 0:
        raise ValueError("nonexistent thread id");
    elif res > 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None);
        raise SystemError("PyThreadState_SetAsyncExc failed");


# Ping monitor worker thread
def pingMonitor(screen, Ping):

  global myPeer, myPort, succ1, succ2, pred1, pred2, lastDeadPeer;

  # Create socket that is to be used for listening for messages
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM);
  sock.settimeout(PINGMONITOR_TIMEOUT);
  sock.bind((LOCALHOST, myPort));

  lastPingsSent = 0;

  #Sequence numbers (Go from 0-SEQMAX)
  sequenceNum = 0;
  succ1LastAck = 0;
  succ2LastAck = 0;
  succ1JustDied = False;
  succ2JustDied = False;

  while True:
    # Send pings to successors at each PINGSENDTIME timestep
    if (time.time() - lastPingsSent) > PINGSEND_FREQUENCY:
      # Send pings requests to each successor if they are not dead
      if succ1 != PEER.DEAD:
        sendPing(Ping.REQ, sequenceNum, myPeer, LOCALHOST, peerToPort(succ1));
      if succ2 != PEER.DEAD:
        sendPing(Ping.REQ, sequenceNum, myPeer, LOCALHOST, peerToPort(succ2));

      sequenceNum = (sequenceNum + 1) % SEQMAX; #increment sequence number, wrapping to 0 if neccessary

      #Update lastPingsSent time
      lastPingsSent = time.time();

    #If a peer was recently declared dead and we have a new peer
    #Reset the sequence number so new peer is not instantly declared dead also
    if succ1JustDied and succ1 != PEER.DEAD:
      succ1LastAck = sequenceNum;
      succ1JustDied = False;

    if succ2JustDied and succ2 != PEER.DEAD:
      succ2LastAck = sequenceNum;
      succ2JustDied = False;

    #Check to see successors are still alive
    if succ1 != PEER.DEAD and sequenceNum - succ1LastAck >= 4:
      #Send TCP query to 2nd successor asking for its successors
      sendChurnMessage(PEERCHURN.QUERYREQ, 0, 0, myPeer, LOCALHOST, peerToPort(succ2));

      consolePrint(screen, "[PEER CRN]", "Peer (" + makeColComp(Colours.GREEN, str(succ1)) + ") is no longer alive.")

      lastDeadPeer = succ1;
      succ1 = PEER.DEAD;
      succ1JustDied = True;

    if succ2 != PEER.DEAD and sequenceNum - succ2LastAck >= 4:
      #Send TCP query to first successor, asking for its successors
      sendChurnMessage(PEERCHURN.QUERYREQ, 0, 0, myPeer, LOCALHOST, peerToPort(succ1));

      consolePrint(screen, "[PEER CRN]", "Peer (" + makeColComp(Colours.GREEN, str(succ2)) + ") is no longer alive.")
      
      lastDeadPeer = succ2;
      succ2 = PEER.DEAD;
      succ2JustDied = True;

    # Monitor myPort for incoming messages 
    #Get start time
    startTime = time.time();
    elapsed = 0.0; #time taken to receive a ping request (in this loop)

    try:
      data, addr = sock.recvfrom(PINGBUFFER);
      elapsed = time.time() - startTime;
      
      msgType = ord(data[0]); # get message type
      senderPeerID = int(data[1:4]); #get senders ID
      recSeq = int(data[4:7]); #get ping sequence number

      # Check for ping request message
      if msgType == Ping.REQ:
        consolePrint(screen, "[PING REQ]", "A ping request message was received from Peer (" + makeColComp(Colours.GREEN, str(senderPeerID)) + ")");

        #If sender peer is unknown (reset all pred information) ONLY if we currently have both NON-INVALID peers
        #This forces pred peers to update seeminglessly if they change
        if (pred1 != PEER.INVALID and pred2 != PEER.INVALID) and (senderPeerID != pred1 and senderPeerID != pred2):       
          pred1 = PEER.INVALID;
          pred2 = PEER.INVALID;

        #If predecessors are invalid, update them
        if pred1 == PEER.INVALID:
          pred1 = senderPeerID;
        elif pred2 == PEER.INVALID:
          #Ensure we don't add the same pred twice
          if senderPeerID != pred1:
            pred2 = senderPeerID;

        #Send a ping response back (in response to ping request)
        sendPing(Ping.RES, recSeq, myPeer, LOCALHOST, peerToPort(int(senderPeerID)));

      elif msgType == Ping.RES:
        #Update last received seq for peer
        if senderPeerID == succ1:
          succ1LastAck = recSeq;
        elif senderPeerID == succ2:
          succ2LastAck = recSeq;

        #Print response received message
        consolePrint(screen, "[PING RES]" , "A ping response message was received from Peer (" + makeColComp(Colours.GREEN, str(senderPeerID))+ ")")
    except socket.error:
      pass;


# TCP Worker Thread
def TCPMonitor(screen, Ping):

  global myPeer, myPort, succ1, succ2, lastDeadPeer;

  # Create socket that is to be used for listening for messages
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
  sock.settimeout(FILEMONITOR_TIMEOUT);
  sock.bind((LOCALHOST, myPort));
  sock.listen(1);  

  # Continuously monitor for file transfer requests
  while True:
    try:
      conn, addr = sock.accept();

      while True:
        data = conn.recv(20);
        if not data: break

        msgType = ord(data[0]); # get message type
        senderPeerID = int(data[1:4]); #get senders ID
        
        # Check TCP message type
        if msgType == PEERCHURN.QUIT:
          #Get quitting peers successors
          quittingPeerSucc1 = int(data[4:7]); #succ1
          quittingPeerSucc2 = int(data[7:10]); #succ2

          #Peer quit message, a successor is quitting, update successors
          if senderPeerID == succ1:
            #If quitting peer is immediate succesor, simply inheirt their successors
            succ1 = quittingPeerSucc1;
            succ2 = quittingPeerSucc2;

          elif senderPeerID == succ2:
            #If quitting peer is secondary successor, we can simply replace secondary successor with
            #Quitting peers primary successor
            succ2 = quittingPeerSucc1;
  
          #Print churn message
          consolePrint(screen, "[PEER CRN]", "Peer (" + makeColComp(Colours.GREEN, str(senderPeerID)) + ") will depart from the network.");
          consolePrint(screen, "[PEER CRN]", "My first successor is now Peer (" + makeColComp(Colours.GREEN, str(succ1))  + ").");
          consolePrint(screen, "[PEER CRN]", "My second successor is now Peer (" + makeColComp(Colours.GREEN, str(succ2))  + ").");

        # A peer has asked for successor information        
        elif msgType == PEERCHURN.QUERYREQ:
          #Send response message to sender
          sendChurnMessage(PEERCHURN.QUERYRES, succ1, succ2, myPeer, LOCALHOST, peerToPort(senderPeerID));

        # A peer has responded with query information
        elif msgType == PEERCHURN.QUERYRES:
          #Get required peers
          nextPeerSucc1 = int(data[4:7]); #succ1
          nextPeerSucc2 = int(data[7:10]); #succ2

          #Update successors
          if succ1 == PEER.DEAD:
            succ1 = succ2; #succ2 is our new succ1
            succ2 = nextPeerSucc1; #our successors 1st successor is clearly our new 2nd successor
          elif succ2 == PEER.DEAD:
            if nextPeerSucc1 == lastDeadPeer: # In this case, next peer has not replaced dead peer yet, so its second successor is our new second succ
              succ2 = nextPeerSucc2;
            else: #Otherwise, peer has replaced the dead peer, its first successor is our new second successor
              succ2 = nextPeerSucc1;

          #Print change statuses
          consolePrint(screen, "[PEER CRN]", "My first successor is now Peer (" + makeColComp(Colours.GREEN, str(succ1))  + ").");
          consolePrint(screen, "[PEER CRN]", "My second successor is now Peer (" + makeColComp(Colours.GREEN, str(succ2))  + ").");

        else:
          #File transfer message
          filehash = data[4:]; # get file hash

          #Predecessor peer has detected we have file, send response
          if msgType == FT.FORWARDNEXT:
            # We have the file
            # Directory contact sender with response
            sendFTMessage(str(filehash), FT.RES, myPeer, LOCALHOST, peerToPort(senderPeerID));
            consolePrint(screen, "[FILE RES]", "File " + makeColComp(Colours.RED, str(filehash)) + " is stored here. A response message has been sent to Peer " + makeColComp(Colours.GREEN, str(senderPeerID))  + ".");

          #We received a response for a requested file request
          elif msgType == FT.RES:
            consolePrint(screen, "[FILE RES]", "Received a response message from Peer " + makeColComp(Colours.GREEN, str(senderPeerID))  + ", which has the file " + makeColComp(Colours.RED, str(filehash)) + ".");

          #Else perform regular processing
          else:
            #Check if this file is available here
            fileStatus = checkFileAvailable(str(filehash));

            if fileStatus == FILECHECK.NOTAVAILABLE:
              #Forward message to successor
              sendFTMessage(str(filehash), FT.FORWARD, senderPeerID, LOCALHOST, peerToPort(succ1));
              consolePrint(screen, "[FILE REQ]", "File " + makeColComp(Colours.RED, str(filehash)) + " is not stored here. File request message has been forwarded to successor Peer " + makeColComp(Colours.GREEN, str(succ1))  + ".");

            elif fileStatus == FILECHECK.AVAILABLE:
              # We have the file
              # Directory contact sender with response
              sendFTMessage(str(filehash), FT.RES, myPeer, LOCALHOST, peerToPort(senderPeerID));
              consolePrint(screen, "[FILE RES]", "File " + makeColComp(Colours.RED, str(filehash)) + " is stored here. A response message has been sent to Peer " + makeColComp(Colours.GREEN, str(succ1))  + ".");
        
            elif fileStatus == FILECHECK.NEXTAVAILABLE:
              # The next peer has the file, send a special message
              sendFTMessage(str(filehash), FT.FORWARDNEXT, senderPeerID, LOCALHOST, peerToPort(succ1));
              consolePrint(screen, "[FILE REQ]", "File " + makeColComp(Colours.RED, str(filehash)) + " is not stored here. File request message has been forwarded to successor Peer " + makeColComp(Colours.GREEN, str(succ1))  + ".");

      conn.close();
    except socket.error:
      pass;


# Ping Functions (UDP)
# Sends a single ping to targetIP and targetPort using UDP
# Message format is as follows:
# Message Type - 0x00 for ping request, 0x01 for ping response
# Sender Identifier - must be sent as each client is also server (cant send ping over listening port).

def sendPing(msgType, seqNum, myID, targetIP, targetPort):
  #start with default ping request message
  message = bytearray([msgType]);
  
  #append senders peer identifier
  message.extend(str(myID).zfill(3));
  
  #append sequence number
  message.extend(str(seqNum).zfill(3));

  #Send UDP datagram
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); #UDP
  sock.settimeout(PINGREQ_TIMEOUT);
  sock.sendto(message, (targetIP, targetPort));

# File Transfer Messages (TCP)
# Send or forward a file transfer message
# Message Type - 0x00 for file request, 0x01 for forwarded message, 0x02 for file request response
def sendFTMessage(filehash, msgType, sourceID, targetIP, targetPort):
  #start with message type
  message = bytearray([msgType]);

  #append original senders peer identifier
  message.extend(str(sourceID).zfill(3));

  #append the file hash
  message.extend(str(filehash).zfill(4));

  #Send TCP message to target
  try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
    sock.connect((targetIP, targetPort));
    sock.send(message);
    sock.close();
  except socket.error:
    pass;


# Peer Churn Graceful Exit Message (TCP)
# Send a message to predecessors informing them of exit or querying for information
def sendChurnMessage(msgType, succ1, succ2, sourceID, targetIP, targetPort):
  #start with message type
  message = bytearray([msgType]);

  #append original senders peer identifier
  message.extend(str(sourceID).zfill(3));

  #append succ1 indentifier
  message.extend(str(succ1).zfill(3));

  #append succ2 indentifier
  message.extend(str(succ2).zfill(3));

  #Send TCP message to target
  try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
    sock.connect((targetIP, targetPort));
    sock.send(message);
    sock.close();
  except socket.error:
    pass;

#Checks if file is available here
#Returns values to say if file should be forwarded, if file is available here 
#or if file will be available at the next peer
def checkFileAvailable(filehash):
  hashedPeer = int(filehash) % (MAXPEERNUM + 1);

  #Check if current peer holds file
  if hashedPeer == myPeer:
    return FILECHECK.AVAILABLE;

  #Check special wrap around case
  if succ1 < myPeer:
    if myPeer < hashedPeer <= MAXPEERNUM or 0 <= hashedPeer <= succ1:
      return FILECHECK.NEXTAVAILABLE;

  #Check if succ will have file
  if myPeer < hashedPeer <= succ1:
    return FILECHECK.NEXTAVAILABLE;

  #File must be forwarded
  return FILECHECK.NOTAVAILABLE;

# Convert peer ID to the port the peer will be using to listen for messages
def peerToPort(peerID):
  return BASE_PORT_OFFSET + int(peerID);

# Make colour component
def makeColComp(colour, text):
  return "colour" + str(colour) + "[" + text + "]";

# console print helper function
def consolePrintLine (screen, pos, control, message):
  # Print different colours for different control messages
  if control == "[WARNING]":
    screen.addstr(pos, 0, control, curses.color_pair(Colours.WARNING));
  elif control == "[FILE REQ]" or control == "[FILE RES]":
    screen.addstr(pos, 0, control, curses.color_pair(Colours.FILETRANSFER));
  else:
    screen.addstr(pos, 0, control, curses.color_pair(Colours.STATUS));

  # Print message by parsing any colour tags: colourN[str]
  # Split messages based on colour components
  newMes = re.split("(colour\d\[.*?\])", message);

  totalOut = 12; # first column offset

  for line in newMes:

    colMatch = re.match("colour(\d{1})\[(.*)\]", line);

    str = "";
    colourPairNum = 0;

    if colMatch:
      colourPairNum = int((colMatch.groups()[0]));
      str = colMatch.groups()[1];
    else:
      str = line;

    # Check to ensure we don't attempt to write offscreen
    height, width = screen.getmaxyx();

    if (totalOut + len(str) >= width):
      truncVal = width - totalOut;
      truncStr = (str)[:truncVal]

      if colMatch:
        screen.addstr(pos, totalOut, truncStr, curses.color_pair(colourPairNum));
      else:
        screen.addstr(pos, totalOut, truncStr);

      break;

    #Print contents normally
    if colMatch:
      screen.addstr(pos, totalOut, str, curses.color_pair(colourPairNum));
    else:
      screen.addstr(pos, totalOut, str);
  
    totalOut += len(str);


# Prints a control message and info message to the given screen
def consolePrint (screen, control, message):

  global lines;
  global max_lines;

  myY, myX = screen.getyx(); #save cursor pos

  # Print line
  consolePrintLine(screen, len(lines), control, message);
  lines.append([control, message]);

  overflowCheck(screen);
  
  screen.move(myY, myX); #restore cursor pos
  screen.refresh();


# define program entry point
if __name__ == "__main__":
  init(sys.argv[1:])
