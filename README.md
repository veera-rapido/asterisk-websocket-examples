# asterisk-websocket-examples

Historically, using ARI with Asterisk required connecting to Asterisk with a websocket to receive ARI events, then using HTTP to make REST requests.  Recently though support for websockets has expanded to allow Asterisk to initiate a websocket connection out to your external app ( [ARI Outbound WebSockets](https://docs.asterisk.org/Configuration/Interfaces/Asterisk-REST-Interface-ARI/ARI-Outbound-Websockets/) ) and to allow making REST requests over the same websocket ( [ARI REST over WebSockets](https://docs.asterisk.org/Configuration/Interfaces/Asterisk-REST-Interface-ARI/ARI-REST-over-WebSocket/) ).  Even more recently, the [chan_websocket](https://docs.asterisk.org/Configuration/Channel-Drivers/WebSocket/) channel driver has been aded which allows you to exchange media with Asterisk over a websocket.

The examples in this repo demonstrate all of those Asterisk websocket capabilities. Python's built-in asyncio capabilities are used to manage communications and the only external Python library used is ["websockets"](https://websockets.readthedocs.io/en/stable/index.html).  Everything else needed to run the examples (apart from an Asterisk test instance) is included here.

## Capabilities Demonstrated

* ARI Outbound Websockets
* ARI Inbound Websockets
* ARI REST over WebSockets
* Media over Outbound WebSockets
* Media over Inbound WebSockets

## Example Overview

* **ast_ari_websocket.py**:  A Python library that handles both client and server ARI connections with Asterisk that not only receives events but also allows making REST calls over the websocket.  This library is fairly generic and not specific to the actual examples.
<p>

* **ast_media_websocket.py**:  A Python library that handles both client and server connections with the Asterisk chan_websocket channel driver.  This library is somewhat customized for the examples but the demonstrated concepts are straightforward.
<p>

* **ast_ws_client_example.py**: This demonstrates...
    * Making an ARI websocket connection to Asterisk
    * Making REST calls over the websocket
    * Waiting for an incoming call
    * Creating a "WebSocket" channel using the REST "channels/create" API
    * Making a Media websocket connection to Asterisk
    * Echoing media and playing files over the websocket
<p>

* **ast_ws_server_example.py**: This demonstrates...
    * Creating an ARI websocket server instance
    * Creating a Media websocket server instance
    * Waiting for Asterisk to make an ARI websocket connection to the sample app as a result of receiving an incoming call
    * Making REST calls over the websocket
    * Creating a "WebSocket" channel using the REST "channels/externalMedia" API
    * Waiting for Asterisk to make a Media websocket connection to the sample app
    * Echoing media and playing files over the websocket
<p>

* **mow_echo_test_server.py**: A basic example that doesn't use ARI or either of the libraries that demonstrates...
    * Creating a Media websocket instance
    * Waiting for Asterisk to make a Media websocket connection to the sample app
    * Playing as test media file to the Asterisk Echo() dialplan app
    * Verifying that the echoed media matches what was sent

**NOTE:** The capabilities demonstrated are actually "mix and match".  Running an ARI server doesn't mean you have to also run a Media server.  They're independent so you can run one as a client and the other as a server or ARI without Media or Media without ARI. The choice of creating the Media WebSocket channel with `channels/create` or `channels/externalMedia` is also independent of whether you're running a Media server or client.

## Running the Examples

Start by creating a test instance of Asterisk then copy the example configuration files into /etc/asterisk.  You'll need a phone to call into Asterisk with so you'll have to set that up yourself.

If you don't have the Python "websockets" package installed, install that now using `pip` or your distro package manager as appropriate.  

### mow_echo_test_server.py

This is the easiest example to run because it doesn't require a phone.

* Start asterisk
* Run `./mow_echo_test_server.py`
* Run `channel originate WebSocket/media_connection1/c(ulaw) extension echo@default` from the Asterisk CLI.

### ast_ws_client_example.py

Usage:

```
./ast_ws_client_example.py [-h] [-ah ARI_HOST] [-ap ARI_PORT] -a STASIS_APP -aU ARI_USER -aP ARI_PASSWORD`
```

ARI_HOST and ARI_PORT default to "localhost" and 8088 respectively. Set them as appropriate for your test Asterisk instance.  STASIS_APP, ARI_USER and ARI_PASSWORD should be set to "test_inbound_connection", "asterisk" and "asterisk" respectively to match the sample config files.

To run the test, start Asterisk first, then ast_ws_client_example.py.  When both are running, dial "1118" from a phone.

### ast_ws_server_example.py

Usage: 

```
./ast_ws_server_example.py [-h] [-aa ARI_BIND_ADDRESS] -ap ARI_BIND_PORT [-awp ARI_WEBSOCKET_PROTOCOL] [-aU ARI_USER]
                                [-aP ARI_PASSWORD] [-ma MEDIA_BIND_ADDRESS] -mp MEDIA_BIND_PORT [-mwp MEDIA_WEBSOCKET_PROTOCOL]
                                [-mwi MEDIA_WEBSOCKET_ID] [-mU MEDIA_USER] [-mP MEDIA_PASSWORD]

```

The only two required parameters are ARI_BIND_PORT which should be set to 8765 and MEDIA_BIND_PORT which should be set to 8787 to match the example websocket_client.conf file.  The conf file does specify user and password for both ARI anbd Media so you can include them on the command line to have the servers verify them if desired.  Everything else can be left at the defaults.

To run the test, start Asterisk and ast_ws_server_example.py.  When both are running, dial "1117" from a phone.




