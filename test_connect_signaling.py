import asyncio
import websockets
 
async def test():
    async with websockets.connect('ws://localhost:8443') as websocket:
        try:
            await websocket.send("HELLO")
            response = await websocket.recv()
            print(response)
            await websocket.ping()
            await websocket.send("SESSION")
            response = await websocket.recv()
            print(response)
        except websockets.ConnectionClosed:
            print ("Connection was closed unexpectedly")

asyncio.get_event_loop().run_until_complete(test())