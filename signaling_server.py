import asyncio
import websockets
from enum import Enum

peers = {}
sessions = {}

class SessionState(Enum):
    INIT = "INIT"
    WAITING_FOR_SDP_OFFER = "WAITING_FOR_SDP_OFFER"
    WAITING_FOR_SDP_ANSWER = "WAITING_FOR_SDP_ANSWER"
    SDP_NEGOTIATION_READY = "SDP_NEGOTIATION_READY"
    SESSION_CLOSED = "SESSION_CLOSED"

class SessionType(Enum):
    SESSION_CLIENT = "SESSION_CLIENT"
    SESSION_SERVER = "SESSION_SERVER"

class WebRTCSession:
    def __init__(self):
        self.server = None
        self.server_ready_for_sdp = None
        self.server_ice = []
        self.client = None
        self.client_ready_for_sdp = None
        self.client_ice = []
        self.sdp_offer = None
        self.sdp_answer = None
        self.state = SessionState.INIT

    async def close(self):
        try:
            await self.server.close()
        except:
            pass
        
        try:
            await self.client.close()
        except:
            pass

        self.state = SessionState.SESSION_CLOSED


    def add_peer(self, peerid, websocket):
        if self.server is None:
            self.server = websocket
            return SessionType.SESSION_SERVER.value

        if self.client is None:
            self.client = websocket
            return SessionType.SESSION_CLIENT.value            

        raise Exception("Too many peers")

    def set_offer(self, websocket, sdp):
        if self.server is websocket:
            self.sdp_offer = sdp
        else:
            raise Exception("SDP offer must be set by the server peer")

    def set_answer(self, websocket, sdp):
        if self.client is websocket:
            self.sdp_answer = sdp
        else:
            raise Exception("SDP answer must be set by the client peer")

    def ready_for_sdp(self, websocket):
        if websocket is self.server:
            self.server_ready_for_sdp = True
        if websocket is self.client:
            self.client_ready_for_sdp = True

    def role(self, websocket):
        return SessionType.SESSION_SERVER if websocket is self.server else SessionType.SESSION_CLIENT
    
    def pass_ice(self, websocket, ice):
        if websocket is self.server:
            self.server_ice.append(ice)
        if websocket is self.client:
            self.client_ice.append(ice)

    def setState(self, newState):
        if newState == SessionState.WAITING_FOR_SDP_OFFER: assert(self.state == SessionState.INIT)
        if newState == SessionState.WAITING_FOR_SDP_ANSWER: assert(self.state == SessionState.WAITING_FOR_SDP_OFFER)
        if newState == SessionState.SDP_NEGOTIATION_READY: assert(self.state == SessionState.WAITING_FOR_SDP_ANSWER)        
        print (f"Session state changed to {newState}")
        self.state = newState

    async def run_state_machine(self):
        if self.state == SessionState.INIT and self.server_ready_for_sdp and self.client_ready_for_sdp:
            self.setState(SessionState.WAITING_FOR_SDP_OFFER)
        
        if self.state == SessionState.WAITING_FOR_SDP_OFFER and self.sdp_offer:
            await self.client.send(self.sdp_offer)
            self.setState(SessionState.WAITING_FOR_SDP_ANSWER)

        if self.state == SessionState.WAITING_FOR_SDP_ANSWER and self.sdp_answer:
            await self.server.send(self.sdp_answer)
            self.setState(SessionState.SDP_NEGOTIATION_READY)
            
        if self.state == SessionState.SDP_NEGOTIATION_READY:
            while len(self.server_ice) > 0:
                await self.client.send(self.server_ice.pop(0))
            while len(self.client_ice) > 0:
                await self.server.send(self.client_ice.pop(0))

# create handler for each connection 
async def handler(websocket, path):    
    # async loop now handles the connected peer's websocket until the peer disconnects
    peerid = None
    sessionid = None
    session = None

    try:
        async for data in websocket:
            print(f"Got message: {data}")
            reply = "ok"

            if data.startswith("HELLO"):
                reply = "HELLO"
                peerid = data[6:]

            if data.startswith("SESSION"):
                sessionid = data[8:]
                session = sessions.get(sessionid, WebRTCSession())
                sessions[sessionid] = session
                try:
                    reply = session.add_peer(peerid, websocket)
                except:
                    # exit websocket communication handler loop without destroying the session for other 2 peers
                    sessionid = None
                    session = None
                    websocket.close()
                    break

            if data == "PIPELINE_READY":
                session.ready_for_sdp(websocket)

            # maybe I just should try to parse the message from json... but meh, good enough
            if data.replace(" ", "").startswith('{"sdp":{"type":"offer"'):
                session.set_offer(websocket, data)

            if data.replace(" ", "").startswith('{"sdp":{"type":"answer"'):
                session.set_answer(websocket, data)

            if data.replace(" ", "").startswith('{"ice":{"'):
                reply = f"{session.role(websocket)} sent ICE to other peer\n{data}"
                session.pass_ice(websocket, data)

            if session: await session.run_state_machine()
            await websocket.send(reply)

    except Exception as err:
        print (err)
 
    finally:
        # NOTE: this way of initializing / cleaning up session has race conditions where it will fail
        print (f"Peer did disconnected. Cleaning up session {sessionid}")
        try:
            del sessions[sessionid]
        except:
            pass
        if session: await session.close()
    
start_server = websockets.serve(handler, "0.0.0.0", 8443)
 
asyncio.get_event_loop().run_until_complete(start_server) 
asyncio.get_event_loop().run_forever()
