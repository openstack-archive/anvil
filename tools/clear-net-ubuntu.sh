#!/bin/bash -x

ETH_SRC="eth0"

echo "Clearing your network up."

if [[ -n `brctl show  | grep -i br100` ]]
then
    echo "Clearing br100 and making $ETH_SRC be the real interface."
    #sudo ifconfig $ETH_SRC down
    #sudo ifconfig br100 down
    #sudo brctl delif br100 $ETH_SRC
    #sudo brctl delbr br100
fi

if [[ -n `brctl show  | grep -i virbr0` ]]
then
    echo "Removing virbr0"
    sudo ifconfig virbr0 down
    sudo brctl delbr virbr0
fi

if [[ -z `grep "iface $ETH_SRC" /etc/network/interfaces` ]]
then

    echo "Readjusting /etc/network/interfaces to have DHCP on for $ETH_SRC"
    sudo cat > /etc/network/interfaces <<EOF
    auto $ETH_SRC
    iface $ETH_SRC inet dhcp
EOF

    cat /etc/network/interfaces
fi

echo "Bringing back up $ETH_SRC"
sudo ifup $ETH_SRC


