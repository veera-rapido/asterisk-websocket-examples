#!/usr/bin/env python3

"""
Copyright (C) 2025, Sangoma Technologies Corporation
George T Joseph <gjoseph@sangoma.com>

This program is free software, distributed under the terms of
the Apache License Version 2.0.
"""

from argparse import ArgumentParser as ArgParser
import asyncio
import json
import logging
import sys
import uuid
import traceback
from ast_media_websocket import AstMediaWebSocketClient
from ast_ari_websocket import AstAriWebSocketClient

logger = logging.getLogger(__name__)
logging.basicConfig(
    format="%(asctime)s %(message)s",
    datefmt="[%Y-%m-%d %H:%M:%S]",
    level=logging.INFO,
)

class session():
    def __init__(self, incoming, incoming_name):
        self.incoming_channel = incoming
        self.incoming_channel_name = incoming_name
        self.ws_channel = None
        self.ws_channel_name = None
        self.bridge_id = None
        self.conn_id = None

class ast_ws_client(AstAriWebSocketClient):
    def __init__(self, host, port, app, credentials, tag=None, log_level=logging.INFO):
        super().__init__(host, port, app, credentials, tag, log_level)
        self.sessions_by_incoming = {}
        self.sessions_by_websocket = {}
        self.tag = tag
        self.log_level = log_level

    async def handle_stasisstart(self, msg):
        if "incoming" in msg['channel']['dialplan']['app_data']:
            incoming_id = msg['channel']['id']
            sess = session(incoming_id, msg['channel']['name'])
            self.sessions_by_incoming[incoming_id] = sess
            logger.info("Creating websocket channel")
            resp = await self.send_request("POST", "channels/create", 
                      query_strings=[
                      { "name": "endpoint", "value": "WebSocket/INCOMING/c(ulaw)" },
                      { "name": "app", "value": self.app },
                      { "name": "appArgs", "value": "websocket" },
                      { "name": "originator", "value": incoming_id },
                      ])
            msg_body = json.loads(resp.get('message_body'))
            sess.ws_channel = msg_body['id']
            sess.ws_channel_name = msg_body['name']
            self.sessions_by_websocket[sess.ws_channel] = sess

            logger.info("Dialing websocket channel")
            resp = await self.send_request("POST", f"channels/{sess.ws_channel}/dial?caller={incoming_id}&timeout=5")

        if "websocket" in msg['channel']['dialplan']['app_data']:
            sess.bridge_id = str(uuid.uuid4())
            logger.info(f"Creating bridge {sess.bridge_id}")
            resp = await self.send_request("POST", f"bridges/{sess.bridge_id}?type=mixing")
            await self.send_request("POST", f"bridges/{sess.bridge_id}/addChannel?channel={sess.incoming_channel}")
            await self.send_request("POST", f"bridges/{sess.bridge_id}/addChannel?channel={sess.ws_channel}")

    async def handle_dial(self, msg):
        chan_name = msg['peer']['name']
        if "WebSocket/" not in chan_name:
            return
        logger.info(f"Dial: {chan_name} Status: '{msg['dialstatus']}' websocket")

        if msg['dialstatus'] == "":
            conn_id = msg['peer']['channelvars']['MEDIA_WEBSOCKET_CONNECTION_ID']
            mwc = AstMediaWebSocketClient(self.host, self.port, conn_id,
                    tag=self.tag, log_level=logging.INFO)
            asyncio.create_task(mwc.connect())

        elif msg['dialstatus'] == "ANSWER":
            sess = self.sessions_by_websocket.get(msg['peer']['id'])
            sess.bridge_id = str(uuid.uuid4())
            logger.info(f"Creating bridge {sess.bridge_id}")
            resp = await self.send_request("POST", f"bridges/{sess.bridge_id}?type=mixing")
            await self.send_request("POST", f"bridges/{sess.bridge_id}/addChannel?channel={sess.incoming_channel}")
            await self.send_request("POST", f"bridges/{sess.bridge_id}/addChannel?channel={sess.ws_channel}")

            logger.info(f"Answering {sess.incoming_channel_name}")
            resp = await self.send_request("POST", f"channels/{sess.incoming_channel}/answer")

    async def handle_stasisend(self, msg):
        sess = None
        if "incoming" in msg['channel']['dialplan']['app_data']:
            sess = self.sessions_by_incoming.get(msg['channel']['id'])
            if sess is not None:
                if sess.ws_channel is not None:
                    logger.info("Hanging up ws %s" % sess.ws_channel)
                    await self.send_request("DELETE", "channels/%s" % sess.ws_channel)
                del self.sessions_by_incoming[sess.incoming_channel]
                sess.incoming_channel = None
        if "websocket" in msg['channel']['dialplan']['app_data']:
            sess = self.sessions_by_websocket.get(msg['channel']['id'])
            if sess is not None:
                if sess.incoming_channel is not None:
                    logger.info("Hanging up pj %s" % sess.incoming_channel)
                    await self.send_request("DELETE", "channels/%s" % sess.incoming_channel)
                del self.sessions_by_websocket[sess.ws_channel]
                sess.ws_channel = None

        if sess is not None and sess.bridge_id is not None:
            await self.send_request("DELETE", "bridges/%s" % sess.bridge_id)
            sess.bridge_id = None


async def main(args):
    event_handler = ast_ws_client(args.ari_host, args.ari_port, args.stasis_app,
                        (args.ari_user, args.ari_password), log_level=logging.INFO)
    try:
        await event_handler.connect()
    except KeyboardInterrupt:
        return
    except Exception as e:
        logger.error(f"Error connecting to ARI: {e}")
        traceback.print_exc()
        return

if __name__ == "__main__":
    description = (
        'Command line utility to test ARI and media websocket client connections'
    )

    parser = ArgParser(description=description)
    parser.add_argument("-ah", "--ari-host", type=str, help="Asterisk ARI Host to connect to", required=False, default="localhost")
    parser.add_argument("-ap", "--ari-port", type=str, help="Port to connect to", required=False, default="8088")
    parser.add_argument("-a", "--stasis-app", type=str, help="Stasis app to register as", required=True)
    parser.add_argument("-aU", "--ari-user", type=str, help="ARI user to authenticate as", required=True)
    parser.add_argument("-aP", "--ari-password", type=str, help="Password for ARI user", required=True)
    args = parser.parse_args()
    if not args:
        sys.exit(1)
    
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Error connecting to ARI: {e}")
        traceback.print_exc()
    sys.exit(0)
