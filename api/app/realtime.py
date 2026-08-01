from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from workers import DurableObject, Response

try:
    from realtime_contract import REALTIME_EVENTS, publish_realtime, should_deliver
except ImportError:
    from app.realtime_contract import REALTIME_EVENTS, publish_realtime, should_deliver


class HouseholdRealtime(DurableObject):
    async def fetch(self, request):
        url = urlparse(request.url)
        if request.method == "GET" and url.path == "/connect":
            if request.headers.get("Upgrade") != "websocket":
                return Response("Expected a WebSocket upgrade", status=426)

            params = parse_qs(url.query)
            metadata = {
                "familyId": params.get("familyId", [""])[0],
                "userId": params.get("userId", [""])[0],
                "role": params.get("role", [""])[0],
            }
            if not all(metadata.values()) or metadata["role"] not in {"PARENT", "CHILD"}:
                return Response("Invalid connection metadata", status=401)

            from js import WebSocketPair

            client, server = WebSocketPair.new().object_values()
            self.ctx.acceptWebSocket(server)
            server.serializeAttachment(json.dumps(metadata))
            return Response(None, status=101, web_socket=client)

        if request.method == "POST" and url.path == "/publish":
            event = json.loads(await request.text())
            if event.get("type") not in REALTIME_EVENTS:
                return Response("Unknown event", status=400)

            outgoing = json.dumps({"type": event["type"]})
            for socket in self.ctx.getWebSockets():
                try:
                    metadata = json.loads(str(socket.deserializeAttachment()))
                    if should_deliver(metadata, event):
                        socket.send(outgoing)
                except Exception as exc:
                    print(f"Realtime socket fan-out failed: {exc}")
            return Response(None, status=204)

        return Response("Not found", status=404)

    async def webSocketMessage(self, ws, message):
        # Events flow from authenticated REST mutations to clients. Client messages
        # are intentionally ignored so the socket cannot become a second API.
        return None

    async def webSocketClose(self, ws, code, reason, was_clean):
        ws.close(code, reason)

    async def webSocketError(self, ws, error):
        print(f"Realtime WebSocket error: {error}")
