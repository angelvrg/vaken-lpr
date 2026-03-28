"""
TENAX-LPR - Manager de conexiones WebSocket
"""

from fastapi import WebSocket


class ConexionManager:
    def __init__(self):
        self.activas: list[WebSocket] = []

    async def conectar(self, ws: WebSocket):
        await ws.accept()
        self.activas.append(ws)

    def desconectar(self, ws: WebSocket):
        self.activas.remove(ws)

    async def broadcast(self, mensaje: dict):
        for ws in self.activas:
            try:
                await ws.send_json(mensaje)
            except Exception:
                pass


# Instancia global compartida por todos los módulos
manager = ConexionManager()
