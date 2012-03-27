#!/bin/bash

set -o xtrace
set -o errexit

# Create a small network
%BIN_DIR%/nova-manage --flagfile %CFG_FILE% network create private %FIXED_RANGE% 1 %FIXED_NETWORK_SIZE%

if [[ "$ENABLED_SERVICES" =~ "quantum" ]]; then
    echo "Not creating floating IPs (not supported by Quantum)"
else
    # Create some floating ips
    %BIN_DIR%/nova-manage --flagfile %CFG_FILE% floating create %FLOATING_RANGE%

    # Create a second pool
    %BIN_DIR%/nova-manage --flagfile %CFG_FILE% floating create --ip_range=%TEST_FLOATING_RANGE% --pool=%TEST_FLOATING_POOL%
fi

