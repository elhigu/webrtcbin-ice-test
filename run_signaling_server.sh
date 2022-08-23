#!/bin/env bash
echo "Running server on 0.0.0.0:8334"
docker run --rm -it -v $PWD:/src -w /src --network host gstreamer-python:latest bash -c ". /venv/bin/activate && python3 signaling_server.py"
