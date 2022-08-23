#!/bin/env bash

if [ -z "$1" ]; then echo "Usage: $0 <webrtc signaling server e.g. ws://172.19.221.117:8334> <turnserverip>"; exit 1; fi

TURN=""
if [ -z "$2" ]; then TURN="--turn turn://test:testpass@$2:3478?transport=udp"; fi


docker run --rm -it -v $PWD:/src -w /src --network host gstreamer-python:latest bash -c ". /venv/bin/activate && python3 webrtc_sendrecv.py --server $1 --videooutputsink fakesink --audiooutputsink fakesink $TURN 2"