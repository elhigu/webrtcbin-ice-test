import random
import ssl
import websockets
import asyncio
import os
import sys
import json
import argparse

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
gi.require_version('GstWebRTC', '1.0')
from gi.repository import GstWebRTC
gi.require_version('GstSdp', '1.0')
from gi.repository import GstSdp

from websockets.version import version as wsv

class WebRTCClient:
    def __init__(self, id_, peer_id, server, video_output_sink, audio_output_sink, stun, turn):
        self.id_ = id_
        self.conn = None
        self.pipe = None
        self.webrtc = None
        self.peer_id = peer_id
        self.server = server
        self.video_output_sink = video_output_sink
        self.audio_output_sink = audio_output_sink
        print (f"Using video_output_sink: {self.video_output_sink}")
        print (f"Using audio_output_sink: {self.audio_output_sink}")

        stun_parameter = f"stun-server={stun}" if len(stun) > 0 else "" 
        turn_parameter = f"turn-server={turn}" if len(turn) > 0 else ""
 
        self.PIPELINE_DESC = f'''        
            webrtcbin name=sendrecv bundle-policy=max-bundle {stun_parameter} {turn_parameter}
                videotestsrc is-live=true pattern=ball ! videoconvert ! queue ! vp8enc deadline=1 ! rtpvp8pay !
                    queue ! application/x-rtp,media=video,encoding-name=VP8,payload=97 ! sendrecv.
                audiotestsrc is-live=true wave=red-noise ! audioconvert ! audioresample ! queue ! opusenc ! rtpopuspay !
                    queue ! application/x-rtp,media=audio,encoding-name=OPUS,payload=96 ! sendrecv.
        '''

        print(f"Created pipeline description: {self.PIPELINE_DESC}")

    async def connect(self):
        # removed SSL requirement
        # sslctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)        
        # self.conn = await websockets.connect(self.server, ssl=sslctx)
        self.conn = await websockets.connect(self.server)
        await self.conn.send('HELLO %d' % self.id_)

    async def setup_call(self):
        await self.conn.send('SESSION {}'.format(self.peer_id))

    def send_sdp_offer(self, offer):
        text = offer.sdp.as_text()
        print ('Sending offer:\n%s' % text)
        msg = json.dumps({'sdp': {'type': 'offer', 'sdp': text}})
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send(msg))
        loop.close()

    def send_sdp_answer(self, sdp):
        text = sdp.sdp.as_text()
        print ('Sending answer:\n%s' % text)
        msg = json.dumps({'sdp': {'type': 'answer', 'sdp': text}})
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send(msg))
        loop.close()

    def on_offer_created(self, promise, _, __):
        promise.wait()
        reply = promise.get_reply()
        offer = reply.get_value('offer')
        promise = Gst.Promise.new()
        self.webrtc.emit('set-local-description', offer, promise)
        promise.interrupt()
        self.send_sdp_offer(offer)

    def on_negotiation_needed(self, element):
        promise = Gst.Promise.new_with_change_func(self.on_offer_created, element, None)
        element.emit('create-offer', None, promise)

    def send_ice_candidate_message(self, _, mlineindex, candidate):
        icemsg = json.dumps({'ice': {'candidate': candidate, 'sdpMLineIndex': mlineindex}})
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.conn.send(icemsg))
        loop.close()

    def on_incoming_decodebin_stream(self, _, pad):
        if not pad.has_current_caps():
            print (pad, 'has no caps, ignoring')
            return

        caps = pad.get_current_caps()
        print(f"Got caps {caps.to_string()}")
        s = caps.get_structure(0)
        name = s.get_name()

        if name.startswith('video'):
            print ("== creating backend for video")
            q = Gst.ElementFactory.make('queue')
            conv = Gst.ElementFactory.make('videoconvert')
            sink = Gst.ElementFactory.make(self.video_output_sink)
            self.pipe.add(q)
            self.pipe.add(conv)
            self.pipe.add(sink)
            self.pipe.sync_children_states()
            pad.link(q.get_static_pad('sink'))
            q.link(conv)
            conv.link(sink)

        elif name.startswith('audio'):
            print ("== creating backend for audio")
            q = Gst.ElementFactory.make('queue')
            conv = Gst.ElementFactory.make('audioconvert')
            resample = Gst.ElementFactory.make('audioresample')
            sink = Gst.ElementFactory.make(self.audio_output_sink)
            self.pipe.add(q)
            self.pipe.add(conv)
            self.pipe.add(resample)
            self.pipe.add(sink)
            self.pipe.sync_children_states()
            pad.link(q.get_static_pad('sink'))
            q.link(conv)
            conv.link(resample)
            resample.link(sink)

    def on_incoming_stream(self, _, pad):
        if pad.direction != Gst.PadDirection.SRC:
            return
        print ("== GOT incoming stream, connecting decodebin")
        decodebin = Gst.ElementFactory.make('decodebin')
        decodebin.connect('pad-added', self.on_incoming_decodebin_stream)
        self.pipe.add(decodebin)
        decodebin.sync_state_with_parent()
        self.webrtc.link(decodebin)

    def on_ice_gathering_state_notify(self, pspec, _):
        state = self.webrtc.get_property('ice-gathering-state')
        print(f'ICE gathering state changed to {state}')

    def on_ice_connection_state_notify(self, pspec, _):
        state = self.webrtc.get_property('ice-connection-state')
        print(f'ICE connection state changed to {state}')

    def start_pipeline(self, mode):
        print (f"Starting pipeline in mode: {mode}")
        self.pipe = Gst.parse_launch(self.PIPELINE_DESC)
        self.webrtc = self.pipe.get_by_name('sendrecv')

        self.webrtc.connect('notify::ice-gathering-state', self.on_ice_gathering_state_notify)
        self.webrtc.connect('notify::ice-connection-state', self.on_ice_connection_state_notify)

        # this is needed only when creating SDP offer        
        if mode == 'SESSION_SERVER': self.webrtc.connect('on-negotiation-needed', self.on_negotiation_needed)
        
        self.webrtc.connect('on-ice-candidate', self.send_ice_candidate_message)
        self.webrtc.connect('pad-added', self.on_incoming_stream)
        self.pipe.set_state(Gst.State.PLAYING)

    def handle_sdp_and_ice(self, message):
        assert (self.webrtc)
        msg = json.loads(message)
        if 'sdp' in msg:
            sdp_outer = msg['sdp']
            if sdp_outer['type'] == 'answer':
                sdp = sdp_outer['sdp']
                print ('Received answer:\n%s' % sdp)
                res, sdpmsg = GstSdp.SDPMessage.new()
                GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
                answer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdpmsg)
                promise = Gst.Promise.new()
                self.webrtc.emit('set-remote-description', answer, promise)
                promise.interrupt()

            elif sdp_outer['type'] == 'offer':
                sdp = sdp_outer['sdp']
                print ('Received SDP offer:\n%s' % sdp)
                res, sdpmsg = GstSdp.SDPMessage.new()
                GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), sdpmsg)
                offer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.OFFER, sdpmsg)
                promise = Gst.Promise.new()
                self.webrtc.emit('set-remote-description', offer, promise)
                promise.interrupt()
                self.create_sdp_answer()

        elif 'ice' in msg:
            ice = msg['ice']
            candidate = ice['candidate']
            sdpmlineindex = ice['sdpMLineIndex']
            print(f"Adding candidate to webrtcbin sdplineindex: {sdpmlineindex} {candidate}")
            self.webrtc.emit('add-ice-candidate', sdpmlineindex, candidate)

    def create_sdp_answer(self):
        promise = Gst.Promise.new_with_change_func(self.on_answer_created, self.webrtc, None)
        self.webrtc.emit('create-answer', None, promise)

    def on_answer_created(self, promise, _, __):
        promise.wait()
        reply = promise.get_reply()
        error = reply.get_value('error')
        if error:
            print(f'WebRTC: Error in answer: {error}')
        else:
            answer = reply.get_value('answer')
            promise = Gst.Promise.new()
            self.webrtc.emit('set-local-description', answer, promise)
            promise.interrupt()
            self.send_sdp_answer(answer)
    
    def close_pipeline(self):
        self.pipe.set_state(Gst.State.NULL)
        self.pipe = None
        self.webrtc = None

    async def loop(self):
        assert self.conn
        async for message in self.conn:
            print (f"Got message: {message}")
            if message == 'HELLO':
                await self.setup_call()
            elif message == 'SESSION_SERVER' or message == 'SESSION_CLIENT':
                self.start_pipeline(message)
                await self.conn.send("PIPELINE_READY")
            elif message.startswith('ERROR'):
                print (message)
                self.close_pipeline()
                return 1
            elif message.replace(" ", "").startswith('{"sdp":') or message.replace(" ", "").startswith('{"ice":'):
                self.handle_sdp_and_ice(message)
        self.close_pipeline()
        return 0

    async def stop(self):
        if self.conn:
            await self.conn.close()
        self.conn = None


def check_plugins():
    needed = ["opus", "vpx", "nice", "webrtc", "dtls", "srtp", "rtp",
              "rtpmanager", "videotestsrc", "audiotestsrc"]
    missing = list(filter(lambda p: Gst.Registry.get().find_plugin(p) is None, needed))
    if len(missing):
        print('Missing gstreamer plugins:', missing)
        return False
    return True


if __name__=='__main__':
    Gst.init(None)
    if not check_plugins():
        sys.exit(1)
    parser = argparse.ArgumentParser()
    parser.add_argument('peerid', help='Session ID which to connect')
    parser.add_argument('--server', help='Signalling server (running signaling_server.py) to connect to, eg "ws://127.0.0.1:8443"')
    parser.add_argument('--videooutputsink', help='Sink element that is used to output video stream', default='autovideosink')
    parser.add_argument('--audiooutputsink', help='Sink element that is used to output audio stream', default='autoaudiosink')
    parser.add_argument('--stun', help='stun-server parameter for webrtcbin e.g. stun://turnserver:3478', default="")
    parser.add_argument('--turn', help='turn-server parameter for webrtcbin e.g. turn://<user>:<pass>@turnserver:3478?transport=udp', default="")
    args = parser.parse_args()
    our_id = random.randrange(10, 10000)
    c = WebRTCClient(our_id, args.peerid, args.server, args.videooutputsink, args.audiooutputsink, args.stun, args.turn)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(c.connect())
    res = loop.run_until_complete(c.loop())
    sys.exit(res)
