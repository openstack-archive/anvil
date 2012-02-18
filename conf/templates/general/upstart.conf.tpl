# This is a primitive starting point for 
# generic upstart configuration files
# for various openstack components.

author "%AUTHOR%"
description "This is the upstart file for %SHORT_NAME% made on %MADE_DATE%"

start on %START_EVENT%
stop on  %STOP_EVENT%

%RESPAWN%

exec %PROGRAM_NAME% %PROGRAM_OPTIONS%
