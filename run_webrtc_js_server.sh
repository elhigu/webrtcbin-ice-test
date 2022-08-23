#!/bin/env bash

if [ -z "$1" ]; then echo "Usage: $0 <rtc_configuration_json>"; exit 1; fi

echo -e 'var rtc_configuration = '$1';' > webrtc_recv_conf.js

#TODO: allow also giving websocket server url in casee if page is served from other host

npx http-serve
