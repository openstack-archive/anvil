#!/bin/bash

set -o xtrace
set -o errexit

# Create a small network
%NOVA_DIR%/bin/nova-manage --flagfile %CFG_FILE% network create private %FIXED_RANGE% 1 %FIXED_NETWORK_SIZE%

if [[ "$ENABLED_SERVICES" =~ "quantum-server" ]]; then
    echo "Not creating floating IPs (not supported by Quantum)"
else
    # Create some floating ips
    %NOVA_DIR%/bin/nova-manage --flagfile %CFG_FILE% floating create %FLOATING_RANGE%

    # Create a second pool
    %NOVA_DIR%/bin/nova-manage --flagfile %CFG_FILE% floating create --ip_range=%TEST_FLOATING_RANGE% --pool=%TEST_FLOATING_POOL%
fi

