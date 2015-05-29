# We use "$PWD" to allow for spaces in directory path.
#
# This setup script can be used to run the circular DHT python script 'cdht_ex.py'
#
# Xterm windows are set to width 111 characters so all text is displayed properly (and not truncated).
#
#!/bin/bash

xterm -geometry 111x24 -hold -title "Peer 1" -e "python '$PWD'/cdht_ex.py 1 3 4" &
xterm -geometry 111x24 -hold -title "Peer 3" -e "python '$PWD'/cdht_ex.py 3 4 5" &
xterm -geometry 111x24 -hold -title "Peer 4" -e "python '$PWD'/cdht_ex.py 4 5 8" &
xterm -geometry 111x24 -hold -title "Peer 5" -e "python '$PWD'/cdht_ex.py 5 8 10" &
xterm -geometry 111x24 -hold -title "Peer 8" -e "python '$PWD'/cdht_ex.py 8 10 12" &
xterm -geometry 111x24 -hold -title "Peer 10" -e "python '$PWD'/cdht_ex.py 10 12 15" &
xterm -geometry 111x24 -hold -title "Peer 12" -e "python '$PWD'/cdht_ex.py 12 15 1" &
xterm -geometry 111x24 -hold -title "Peer 15" -e "python '$PWD'/cdht_ex.py 15 1 3" &
