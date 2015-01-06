#!/bin/bash -x

echo "Clearing your dns"

for pid in `ps -elf | grep -i dnsmasq | grep nova | perl -le 'while (<>) { my $pid = (split /\s+/)[3]; print $pid; }'`; do
    echo "Killing leftover nova dnsmasq process with process id $pid"
    kill -9 $pid
done

