#!/bin/bash

### This is a utility script that can be used to resize a vm's disk
### image in case that image is just a bare filesystem with no
### partition table or boot record.  You should shutdown the vm prior
### to using this script.

if [ $# -lt 2 ]; then
    echo "Usage: resize.sh <img> <size>  (e.g., resize.sh disk 500G)" 1>&2
    exit 1
fi

DISK="$1"
SIZE="$2"

echo "Will attempt to resize $DISK to $SIZE."

if [ ! -w "$DISK" ]; then
    echo "Error: Cannot write to $DISK, maybe you need to sudo."
    exit 1
fi

TMPDISK="$DISK.$RANDOM"

if !(cp "$DISK" "$TMPDISK"); then
    echo "Error: unable to make a temporary copy of $DISK named $TMPDISK." 1>&2
    exit 1
fi

if !(qemu-img resize "$TMPDISK" "$SIZE"); then
    echo "Error: qemu-img failed." 1>&2
    exit 1
fi

echo "Attempting guestfs resize... this might take a few minutes."

guestfish <<EOF
add $TMPDISK
run
e2fsck /dev/vda forceall:true
resize2fs /dev/vda
sync
umount-all
EOF
if [ $? -ne 0 ]; then
    echo "Error: guestfish resize failed." 1>&2
    exit 1
fi

if !(mv "$TMPDISK" "$DISK"); then
    echo "Error: unable to move $TMPDISK back on top of $DISK." 1>&2
    exit 1
fi

echo "Great success."

