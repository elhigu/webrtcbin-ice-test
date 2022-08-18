#!/bin/bash

set -e

BUILD_TYPE="${1:-debug}"
echo "Building $BUILD_TYPE build"

docker build --build-arg BUILD_TYPE=$BUILD_TYPE -t gstreamer-python:latest -f Dockerfile .
