import logging
import time

import websockets.sync.client

from scripts import msgpack_numpy


class WebsocketClientPolicy:
    """Implements the Policy interface by communicating with a server over websocket."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        self._uri = f"ws://{host}:{port}"
        self._packer = msgpack_numpy.Packer()
        self._ws = self._wait_for_server()

    def _wait_for_server(self) -> websockets.sync.client.ClientConnection:
        logging.info(f"Waiting for server at {self._uri}...")
        while True:
            try:
                return websockets.sync.client.connect(self._uri, compression=None, max_size=None)
            except ConnectionRefusedError:
                logging.info("Still waiting for server...")
                time.sleep(5)

    def infer(self, obs: dict) -> dict:
        data = self._packer.pack(obs)
        self._ws.send(data)
        response = self._ws.recv()
        if isinstance(response, str):
            # we're expecting bytes; if the server sends a string, it's an error.
            raise RuntimeError(f"Error in inference server:\n{response}")
        return msgpack_numpy.unpackb(response)
