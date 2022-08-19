FROM ubuntu:20.04

ARG GSTREAMER_VERSION=1.20.3
ARG BUILD_TYPE=debug
ARG INSTALL_DIR=/gstreamer
ENV PKG_CONFIG_PATH=$INSTALL_DIR/lib/x86_64-linux-gnu/pkgconfig
ENV GI_TYPELIB_PATH=$INSTALL_DIR/lib/x86_64-linux-gnu/girepository-1.0/
ENV PYTHONPATH=/:${INSTALL_DIR}/lib/python3/dist-packages
ENV GST_PLUGIN_PATH=$INSTALL_DIR/lib/x86_64-linux-gnu/gstreamer-1.0
ENV LD_LIBRARY_PATH=$INSTALL_DIR/lib/x86_64-linux-gnu
ARG LIBNICE_COMMIT=0.1.19

# Origins of some dependencies:
# gstreamer        libglib2.0-dev flex bison python3-pip
# plugins_ugly     libx264-dev
# plugins_base     libx11-xcb-dev
# plugins_good     liborc-0.4-dev
# gst-libav        libavfilter-dev
# libnice          libssl-dev libgnutls28-dev  libgupnp-igd-1.0-dev
# gst-python       python-gi-dev python3-venv libpython3.8-dev
# gstreamer-python libcairo-dev libgirepository1.0-dev
# python eventlet  netbase
# gst-shark        autoconf libtool graphviz-dev

# TODO  More likely this list has some extra than too few packages, and could be optimized further.
RUN apt-get -y update && \
DEBIAN_FRONTEND=noninteractive apt-get -y install \
alsa-base alsa-tools apt-transport-https autopoint bison cmake curl flex gettext git gnupg \
gobject-introspection libasound2-dev libatlas-base-dev libavfilter-dev libcairo-dev libcap-dev \
libcrypto++-dev libdc1394-22-dev libde265-dev libdw-dev libgbm-dev libgirepository1.0-dev libglib2.0-dev \
libgmp-dev libgphoto2-dev libgraphene-1.0-dev libgsl-dev libgtk-3-dev libjpeg-dev libjson-glib-dev \
libopengl-dev libopus-dev liborc-0.4-dev libpango1.0-dev libpng-dev libpython3.8-dev libprotobuf-dev libsrtp2-dev \
libssl-dev libtheora-bin libtheora-dev libtiff-dev libunwind-dev libvdpau-dev libvisual-0.4-dev libvorbis-dev \
libvpx-dev libwebrtc-audio-processing-dev libx11-dev libx11-xcb-dev libx264-dev libx265-dev lsb-release \
mesa-utils mongodb-clients nasm netbase ninja-build opencl-dev openssl pkg-config protobuf-compiler python3-pip \
python3-setuptools python3-venv python3-wheel python-gi-dev qt5-default sox sudo unzip wget xorg-dev yasm \
libgnutls28-dev libgupnp-igd-1.0-dev libflac-dev ssh libproxy-dev libavdevice-dev autoconf libtool graphviz-dev \
&& rm -rf /var/lib/apt/lists/*

# Setup python virtual environment
RUN python3 -m venv /venv

# Install meson
RUN . /venv/bin/activate && pip3 install wheel meson

# GStreamer
WORKDIR /build
RUN git clone https://gitlab.freedesktop.org/gstreamer/gstreamer.git && \
    cd gstreamer && \
    git checkout $GSTREAMER_VERSION
WORKDIR /build/gstreamer/build
RUN . /venv/bin/activate && meson -Dgpl=enabled --prefix=$INSTALL_DIR -Dbuildtype=${BUILD_TYPE} && ninja && ninja install

# gstreamer-python
WORKDIR /build
RUN git clone https://github.com/yuyou/gstreamer-python.git
WORKDIR /build/gstreamer-python
RUN . /venv/bin/activate && \
    pip3 install -r requirements.txt && \
    python3 setup.py install

# Build libproxy (maybe not needed)
#COPY ./libproxy /libproxy
#RUN rm -rf /libproxy/build && \
#    cd /libproxy && \
#    . /venv/bin/activate && meson --prefix=$INSTALL_DIR -Dbuildtype=${BUILD_TYPE} build && \
#    ninja -C build

RUN apt-get -y update && \
DEBIAN_FRONTEND=noninteractive apt-get -y --no-install-recommends  install python3-venv libgirepository1.0 libunwind8 libdw1 \
libpython3.8 liborc-0.4-0 libopus0 libvisual-0.4-0 libx265-179 libxv1 libpangocairo-1.0-0 libxdamage1 \
libwebrtc-audio-processing1 libasound2 libgupnp-igd-1.0-4 libavfilter-extra7 libogg0  libjpeg-turbo8 libde265-0 libdc1394-22 \
libflac8 libsrtp2-1 gobject-introspection libgtk-3-dev libgraphene-1.0-dev netbase libgphoto2-6 \
alsa-utils libgvc6 \
&& rm -rf /var/lib/apt/lists/*

RUN . /venv/bin/activate && pip3 install websockets
