Circular DHT Network
=========
Circular DHT Program capable of graceful and ungraceful peer churn (leave) and sending/receiving ping/file transfer signals.  
Each peer in the network keeps track of its 2 successors and constantly pings them to see if they are alive.

Basic 'file request' messages can also be sent across the network by any peer and peers forward the request to their successors until a peer is reached that has the request file.  

Curses is used to display all output (refer to images).

Refer to **doc/report.pdf** for further documentation.

Images
----
<h4>Curses screen of Peer 50 in CDHT network:</h4>

![Peer 50 Terminal](/../screenshots/screenshots/peerinstance.png?raw=true "Peer 50 Terminal")

License
----
All rights reserved.
