#!/bin/bash

# This script cleans up the system as part of a nova uninstall

# Eventually it should be moved to python code...

# This was added (so that it dies on errors)
set -o errexit

if [[ "$ENABLED_SERVICES" =~ "net" ]]; then

    # Ignore any errors from shutting down dnsmasq
    # TODO shouldn't this be a service shutdown??
    killall dnsmasq || true
    
    # Delete rules
    iptables -S -v | sed "s/-c [0-9]* [0-9]* //g" | grep "nova" | grep "\-A" |  sed "s/-A/-D/g" | awk '{print "sudo iptables",$0}' | bash
    
    # Delete nat rules
    iptables -S -v -t nat | sed "s/-c [0-9]* [0-9]* //g" | grep "nova" |  grep "\-A" | sed "s/-A/-D/g" | awk '{print "sudo iptables -t nat",$0}' | bash
    
    # Delete chains
    iptables -S -v | sed "s/-c [0-9]* [0-9]* //g" | grep "nova" | grep "\-N" |  sed "s/-N/-X/g" | awk '{print "sudo iptables",$0}' | bash
    
    # Delete nat chains
    iptables -S -v -t nat | sed "s/-c [0-9]* [0-9]* //g" | grep "nova" |  grep "\-N" | sed "s/-N/-X/g" | awk '{print "sudo iptables -t nat",$0}' | bash

fi

if [[ "$ENABLED_SERVICES" =~ "vol" ]]; then

    # Logout and delete iscsi sessions
    iscsiadm --mode node | grep $VOLUME_NAME_PREFIX | cut -d " " -f2 | xargs sudo iscsiadm --mode node --logout || true
    iscsiadm --mode node | grep $VOLUME_NAME_PREFIX | cut -d " " -f2 | sudo iscsiadm --mode node --op delete || true

fi
