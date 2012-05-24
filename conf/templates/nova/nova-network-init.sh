#!/bin/bash

# TODO - get rid of this, just use python...

set -o xtrace
set -o errexit

# Create a small network
nova-manage --config-file %CFG_FILE% network create private %FIXED_RANGE% 1 %FIXED_NETWORK_SIZE%

if [[ "$ENABLED_SERVICES" =~ "quantum" ]]; then
    echo "Not creating floating IPs (not supported by quantum server)"
else
    # Create some floating ips
    nova-manage --config-file %CFG_FILE% floating create %FLOATING_RANGE%

    # Create a second pool
    nova-manage --config-file %CFG_FILE% floating create --ip_range=%TEST_FLOATING_RANGE% --pool=%TEST_FLOATING_POOL%
fi

