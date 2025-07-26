"""
Copyright (C) 2025, Sangoma Technologies Corporation
George T Joseph <gjoseph@sangoma.com>

This program is free software, distributed under the terms of
the Apache License Version 2.0.
"""

import asyncio
import io
import logging
from logging import INFO, WARNING, ERROR, DEBUG, NOTSET
import traceback
from websockets.asyncio.server import serve
from websockets.asyncio.server import basic_auth
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

class AstMediaWebSocket:
    def __init__(self, tag=None, log_level=None, forward_host=None, forward_port=None):
        """
        :param tag: Optional tag for logging.
        :param log_level: Optional log level.  One of logging.LOG_LEVEL.
        :param forward_host: Optional host to forward media data to.
        :param forward_port: Optional port to forward media data to.
        """
        self.logger = logging.getLogger(__name__)
        self.tag = tag
        self.optimal_frame_size = 0
        self.sending_file = False
        self.forward_host = forward_host
        self.forward_port = forward_port
        self.forwarding_mode = forward_host is not None and forward_port is not None
        if log_level is not None:
            self.logger.setLevel(log_level)

    def log(self, level, message):
        """
        Logs a message with the tag.
        :param level: The logging level (e.g., info, warning, error).
        :param message: The message to log.
        """
        tag = "" if self.tag is None else f"{self.tag}: "
        self.logger.log(level, f"{tag}{message}")

    async def send_file(self, ws_media, filename, lock, sent_data=None):
        """
        Sends a file over the media websocket.
        :param ws_media: The websocket connection to send the file over.
        :param filename: The path to the file to send.
        :param lock: An asyncio lock to use to throttle outgoing data.
        :param sent_data: Optional buffer to store sent data for verification.
        """
        buff_size = 1000
        f = io.open(filename, "rb", buffering=0)
        self.log(INFO, f"Playing '{filename}'")
        await ws_media.send("START_MEDIA_BUFFERING")
        while True:
            async with lock:
                buff = f.read(buff_size)
                if buff is None or len(buff) <= 0:
                    break
                # Send on the websocket
                await ws_media.send(buff)
                if sent_data is not None:
                    sent_data.write(buff)
        f.close()
        await ws_media.send(f"STOP_MEDIA_BUFFERING {filename}")
        self.log(INFO, f"Stopping '{filename}'")

    async def echo_timer(self, ws_media, filename, timeout, lock):
        await asyncio.sleep(timeout)
        self.sending_file = True
        asyncio.create_task(self.send_file(ws_media, filename, lock))

    async def forward_data(self, source_ws, target_ws, direction):
        """
        Forward data from source websocket to target websocket.
        :param source_ws: Source websocket connection
        :param target_ws: Target websocket connection  
        :param direction: String describing direction for logging
        """
        try:
            async for message in source_ws:
                if isinstance(message, str):
                    self.log(INFO, f"{direction} forwarding text message: {message[:100]}...")
                    await target_ws.send(message)
                else:
                    # Binary data (audio)
                    self.log(DEBUG, f"{direction} forwarding {len(message)} bytes of audio data")
                    await target_ws.send(message)
        except ConnectionClosed:
            self.log(INFO, f"{direction} connection closed")
        except Exception as e:
            self.log(ERROR, f"{direction} forwarding error: {e}")
            raise e

    async def process_media_with_forwarding(self, client_ws):
        """
        Processes media messages by forwarding only audio content to another websocket server.
        Control messages are handled locally, only binary audio data is forwarded.
        :param client_ws: The client websocket connection
        """
        connection_id = id(client_ws)
        self.log(INFO, f"Media forwarding connection {connection_id} from {client_ws.remote_address}")
        
        try:
            # Extract connection ID from path if available
            path = getattr(client_ws, 'path', '/media/default')
            media_conn_id = "default"
            if "/media/" in path:
                media_conn_id = path.split("/media/")[-1]
            
            # Connect to target media server
            target_uri = f"ws://{self.forward_host}:{self.forward_port}/media/{media_conn_id}"
            self.log(INFO, f"Connecting to target media server at {target_uri}")
            
            async with connect(target_uri, subprotocols=["media"]) as target_ws:
                self.log(INFO, f"Connected to target server, starting audio forwarding")
                
                # Start task to forward responses from target back to client
                target_to_client_task = asyncio.create_task(
                    self.forward_audio_from_target(target_ws, client_ws, connection_id)
                )
                
                # Process messages from client
                async for message in client_ws:
                    if isinstance(message, str):
                        # Handle control messages locally
                        self.log(INFO, f"Received control message: {message}")
                        await self.handle_control_message(message, client_ws, target_ws)
                    else:
                        # Forward binary audio data to target server
                        self.log(DEBUG, f"Forwarding {len(message)} bytes of audio to target")
                        await target_ws.send(message)
                
                # Cancel the response forwarding task when client disconnects
                target_to_client_task.cancel()
                    
        except Exception as e:
            self.log(ERROR, f"Media forwarding error for connection {connection_id}: {e}")
            traceback.print_exc()
        finally:
            self.log(INFO, f"Media forwarding connection {connection_id} closed")

    async def forward_audio_from_target(self, target_ws, client_ws, connection_id):
        """
        Forward audio responses from target server back to client.
        :param target_ws: Target websocket connection
        :param client_ws: Client websocket connection
        :param connection_id: Connection ID for logging
        """
        try:
            async for message in target_ws:
                if isinstance(message, str):
                    # Log control messages from target but don't forward them
                    self.log(INFO, f"Target control message: {message}")
                else:
                    # Forward binary audio data back to client
                    self.log(DEBUG, f"Forwarding {len(message)} bytes of audio from target to client")
                    await client_ws.send(message)
        except ConnectionClosed:
            self.log(INFO, f"Target connection closed for {connection_id}")
        except Exception as e:
            self.log(ERROR, f"Error forwarding from target: {e}")

    async def handle_control_message(self, message, client_ws, target_ws):
        """
        Handle control messages locally, inspired by the original process_media logic.
        :param message: The control message string
        :param client_ws: Client websocket connection
        :param target_ws: Target websocket connection
        """
        if "MEDIA_START" in message:
            self.log(INFO, f"Media session starting: {message}")
            # Parse media parameters
            ma = message.split(" ")
            for p in ma[1:]:
                v = p.split(":")
                if v[0] == "channel":
                    self.tag = v[1]
                elif v[0] == "optimal_frame_size":
                    self.optimal_frame_size = int(v[1])
            
            # Forward MEDIA_START to target so it knows about the session
            await target_ws.send(message)
            
        elif "MEDIA_XOFF" in message:
            self.log(INFO, "Media flow control: XOFF (pause)")
            # Could implement local flow control if needed
            
        elif "MEDIA_XON" in message:
            self.log(INFO, "Media flow control: XON (resume)")
            # Could implement local flow control if needed
            
        elif "MEDIA_BUFFERING_COMPLETED" in message:
            self.log(INFO, f"Media buffering completed: {message}")
            # Handle buffering completion locally
            
        else:
            self.log(INFO, f"Other control message: {message}")
            # Forward unknown control messages to target
            await target_ws.send(message)
        
    async def process_media(self, ws_media):
        """
        Processes media messages received on the websocket.
        If forwarding is enabled, forwards to target server.
        Otherwise, uses the original echo behavior.
        :param ws_media: The websocket connection to process media on.
        """
        if self.forwarding_mode:
            self.log(INFO, f"Using forwarding mode to {self.forward_host}:{self.forward_port}")
            await self.process_media_with_forwarding(ws_media)
            return
            
        # Original echo behavior
        self.log(INFO, f"Media websocket connection from {ws_media.remote_address}")
        try:
            lock = asyncio.Lock()
            async for message in ws_media:
                print(f"Received media message: {message}")
                if isinstance(message, str):
                    self.log(INFO, f"Received media notification {message}")
                    if "MEDIA_START" in message:
                        ma = message.split(" ")
                        for p in ma[1:]:
                            v = p.split(":")
                            if v[0] == "channel":
                                self.tag = v[1]
                            elif v[0] == "optimal_frame_size":
                                self.optimal_frame_size = int(v[1])
                        self.sending_file = True
                        asyncio.create_task(self.send_file(ws_media,
                            "echo-announce.ulaw", lock))
                    if "MEDIA_XOFF" in message:
                        await lock.acquire()
                    if "MEDIA_XON" in message:
                        lock.release()
                    if "MEDIA_BUFFERING_COMPLETED" in message:
                        self.sending_file = False
                        ca = message.split(" ")
                        if "zombies" in ca[1]:
                            await ws_media.send("HANGUP")
                            break
                        else:
                            asyncio.create_task(self.echo_timer(ws_media, 
                                "zombies.ulaw", 10, lock))
                    continue
                if not self.sending_file:
                    await ws_media.send(message)
        except Exception as e:
            self.log(ERROR, f"Media error {e}")
            traceback.print_exc()
            raise e
        finally:
            self.log(INFO, f"Media disconnected")

class AstMediaWebSocketServer(AstMediaWebSocket):
    def __init__(self, host, port, credentials, protocol, tag=None, log_level=None, 
                 forward_host=None, forward_port=None):
        """
        Initializes the media websocket server.
        :param host: The host address to bind the server to.
        :param port: The port to bind the server to.
        :param credentials: Optional credential tuple for authentication ("username", "password")
        :param protocol: The protocol to use for the websocket. Default "media".
        :param tag: Optional tag for logging.
        :param log_level: Optional logging level.
        :param forward_host: Optional host to forward media data to.
        :param forward_port: Optional port to forward media data to.
        """
        super().__init__(tag, log_level, forward_host, forward_port)
        self.host = host
        self.port = port
        self.protocol = protocol
        self.credentials = credentials
        self.server = None

    async def listen(self):
        """
        Starts the media websocket server and listens for incoming connections.
        """
        self.log(INFO, f"Starting media server")
        auth = None
        if self.credentials is not None:
            auth =  basic_auth(realm="asterisk", credentials=self.credentials)

        async with serve(self.process_media, self.host, self.port,
                         subprotocols=[self.protocol],
                         process_request=auth) as server:
            self.server = server
            await server.wait_closed()

    async def stop(self):
        if self.server is not None:
            self.log(INFO, "Stopping Media server")
            self.server.close()
            await self.server.wait_closed()
            self.server = None

class AstMediaWebSocketClient(AstMediaWebSocket):
    def __init__(self, host, port, connection_id, tag=None, log_level=None,
                 forward_host=None, forward_port=None):
        """
        Initializes the media websocket client.
        :param host: The host to connect to.
        :param port: The port to connect to.
        :param connection_id: The connection ID for the media websocket.
        :param tag: Optional tag for logging.
        :param log_level: Optional logging level.
        :param forward_host: Optional host to forward media data to.
        :param forward_port: Optional port to forward media data to.
        """
        super().__init__(tag, log_level, forward_host, forward_port)
        self.host = host
        self.port = port
        self.connection_id = connection_id

    async def connect(self):
        """
        Connects to the media websocket and starts processing media.
        """
        uri = f"ws://{self.host}:{self.port}/media/{self.connection_id}"
        self.log(INFO, f"Connecting to Media at {uri}")
        async with connect(uri, subprotocols=["media"]) as ws_media:
            await self.process_media(ws_media)

