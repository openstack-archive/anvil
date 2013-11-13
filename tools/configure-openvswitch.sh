#!/bin/bash

# This is a sample script to configure OpenVSwitch for
# development needs.

echo 'Startig openvswitch service'
sudo /etc/init.d/openvswitch start

echo "Creating internal bridge 'br-int'"
sudo ovs-vsctl add-br br-int

echo "Creating external bridge 'br-ex'"
sudo ovs-vsctl add-br br-ex

echo "Adding a network interface 'eth1'"
sudo ovs-vsctl add-port br-ex eth1

