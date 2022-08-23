#!/bin/env bash

if [ -z "$1" ]; then echo "Usage: $0 <external host ip>"; exit 1; fi

docker run --rm -it --mount "type=bind,source=$PWD/turnserver.conf,target=/etc/coturn/turnserver.conf" --network host coturn/coturn:4.5.2-r7-debian --log-file=stdout --lt-cred-mech --external=$1 --prometheus