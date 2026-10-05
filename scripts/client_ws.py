"""The Client Input Run's assertion channel (ADR-0019): a local WebSocket server the real client joins with
`/connect`. Commands sent over it return Bedrock's command responses (querytarget, scoreboard), and
subscribed events (PlayerMessage) arrive as they happen. Standard library only; one client; unencrypted
(the run turns the client's websocket_encryption option off for its duration).
"""
import base64
import hashlib
import json
import re
import socket
import struct
import threading
import time
import uuid

GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class ChannelError(Exception):
    pass


class WsChannel:
    def __init__(self, host="127.0.0.1", port=0):
        self._server = socket.create_server((host, port))
        self.port = self._server.getsockname()[1]
        self._conn = None
        self._connected = threading.Event()
        self._closed = threading.Event()
        self._lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._responses = {}
        self._events = []
        threading.Thread(target=self._serve, daemon=True).start()

    # ----- server side -----
    def _serve(self):
        try:
            conn, _ = self._server.accept()
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                request += chunk
            key = re.search(rb"(?im)^sec-websocket-key:\s*(\S+)", request)
            if not key:
                conn.close()
                return
            accept = base64.b64encode(hashlib.sha1(key.group(1) + GUID).digest())
            conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                         b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n")
            self._conn = conn
            self._connected.set()
            self._read(conn)
        except OSError:
            pass
        finally:
            self._closed.set()

    def _exact(self, conn, n):
        data = b""
        while len(data) < n:
            chunk = conn.recv(n - len(data))
            if not chunk:
                raise ConnectionError("client closed the connection")
            data += chunk
        return data

    def _read(self, conn):
        message = b""
        while True:
            b1, b2 = self._exact(conn, 2)
            opcode, length = b1 & 0x0F, b2 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._exact(conn, 2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._exact(conn, 8))[0]
            mask = self._exact(conn, 4) if b2 & 0x80 else b"\0\0\0\0"
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(self._exact(conn, length)))
            if opcode == 8:
                return
            if opcode == 9:
                self._send_frame(0x8A, payload)
                continue
            if opcode in (0, 1):
                message += payload
                if b1 & 0x80:
                    self._dispatch(json.loads(message))
                    message = b""

    def _dispatch(self, message):
        header = message.get("header", {})
        with self._lock:
            if header.get("messagePurpose") == "commandResponse" and "requestId" in header:
                self._responses[header["requestId"]] = message.get("body", {})
            elif header.get("messagePurpose") == "event":
                self._events.append(message)

    def _send_frame(self, first_byte, payload):
        if len(payload) < 126:
            header = bytes([first_byte, len(payload)])
        elif len(payload) < 1 << 16:
            header = bytes([first_byte, 126]) + struct.pack(">H", len(payload))
        else:
            header = bytes([first_byte, 127]) + struct.pack(">Q", len(payload))
        with self._send_lock:
            self._conn.sendall(header + payload)

    # ----- API -----
    def wait_connected(self, timeout):
        return self._connected.wait(timeout)

    def _send(self, message):
        if not self._connected.is_set() or self._closed.is_set():
            raise ChannelError("Minecraft is not connected to the test channel")
        try:
            self._send_frame(0x81, json.dumps(message).encode())
        except OSError as error:
            raise ChannelError(f"Sending to Minecraft failed: {error}") from error

    def command(self, line, timeout=5.0):
        """Run a command as the player; returns the response body (statusCode, statusMessage, ...)."""
        request_id = str(uuid.uuid4())
        self._send({"header": {"version": 1, "requestId": request_id, "messagePurpose": "commandRequest",
                               "messageType": "commandRequest"},
                    "body": {"version": 1, "commandLine": line, "origin": {"type": "player"}}})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if request_id in self._responses:
                    return self._responses.pop(request_id)
            if self._closed.is_set():
                raise ChannelError(f"Minecraft disconnected before answering {line!r}")
            time.sleep(0.01)
        raise ChannelError(f"no response to {line!r} within {timeout} s")

    def subscribe(self, event_name):
        self._send({"header": {"version": 1, "requestId": str(uuid.uuid4()), "messagePurpose": "subscribe",
                               "messageType": "commandRequest"}, "body": {"eventName": event_name}})

    def events(self):
        with self._lock:
            drained, self._events = self._events, []
        return drained

    def close(self):
        for sock in (self._conn, self._server):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass


def query_targets(body):
    """querytarget's targets (position, yRot, uniqueId); [] when the selector matched nothing."""
    if body.get("statusCode") != 0 or "details" not in body:
        return []
    return json.loads(body["details"])


def score(body, objective):
    """A participant's score in objective from a `scoreboard players list <name>` response, or None."""
    if body.get("statusCode") != 0:
        return None
    match = re.search(rf"(?m)^- {re.escape(objective)}: (-?\d+) ", body.get("statusMessage", ""))
    return int(match.group(1)) if match else None
