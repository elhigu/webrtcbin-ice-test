# webrtcbin-ice-test

Small test setup to see if STUN and TURN ICE candidate resolving works between two webrtcbin processes

# Usage

```
turn and websocket servers  ------ LAN ------- -NAT1- peer machine 1
                                        '----- -NAT2- peer machine 2
```

Basically one needs to run some servers on the host machine and then create 2 virtual machines for peers whose IPs are behind NAT.


## Create virtual machines for 2 peers with Virtualbox (it allows to set different NAT for each machine pretty easily)

One can create new NATs to VirtualBox through File -> Preferences -> Network and click + sign

```
Nat1:
Network CIDR: 10.0.3.0/24
Supports DHCP enabled
IPv6 disabled

Nat2:
Network CIDR: 10.0.4.0/24
Supports DHCP enabled
IPv6 disabled
```

Then for each virtual machine one selects different NAT for the network adapter setting.

Both machines should be able to access the host machines LAN IP addresses.


## Setup signaling server, coturn server and webserver serving the browser client implementation running on host machine or some other machine in LAN

These servers will be run on the host machine with docker.

Before running any other commands one needs to build the docker image with required python libs and gstreamer etc:

    ./build_images.sh

and export host IP for other commands

    export HOST_IP=172.19.221.117

### Turn server

    ./run_coturn_server.sh <IP that is visible for peers>

for example: 

    ./run_coturn_server.sh $HOST_IP


### Web socket signaling server

Signaling server is used by 2 peers for negotiating SDP offers / answers and ICE candidates. Listens ws://localhost:8443 

    ./run_signaling_server.sh


### Browser's RTCPeerConnection client http server which serves HTML + Javascript for it

From peer machine one can open in browser `http://hostip:8080/webrtc_recv.html` 

    ./run_webrtc_js_server.sh '{ "iceServers": [{ "urls": "turn:'$HOST_IP':3478?transport=udp", "username": "test", "credential": "testpass" }, { "urls": "stun:'$HOST_IP':3478" }] }'


## Running webrtc clients on peer virtual machines

TODO: add info of peer parameters...