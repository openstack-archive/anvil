# This is a primative starting point for generic upstart configuration files
# for various nova components.
author "DevstackPy"
description "This is the upstart file for %IMAGE%"

start on %START_EVENT%
stop on  %STOP_EVENT%

%RESPAWN%

exec python %BINDIR%/%IMAGE% --flagfile %CFGFILE%
