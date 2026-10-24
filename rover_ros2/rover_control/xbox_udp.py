"""Loopback-only Windows XInput receiver for a mirrored WSL ground station."""
import json
import socket


class XboxUDP:
    def __init__(self, port=15002):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(('127.0.0.1', port))
            self.socket.setblocking(False)
        except Exception:
            self.socket.close()
            raise
        self.session = None
        self.sequence = -1
        self.old_sessions = set()

    def poll(self):
        latest = None
        safety_event = False
        for _ in range(128):
            try:
                payload, sender = self.socket.recvfrom(4096)
            except BlockingIOError:
                return {'connected': False} if safety_event else latest
            if sender[0] != '127.0.0.1':
                continue
            try:
                item = json.loads(payload)
                if (not isinstance(item, dict) or item.get('version') != 1
                        or type(item.get('connected')) is not bool
                        or type(item.get('seq')) is not int or item['seq'] < 0
                        or not isinstance(item.get('session'), str)
                        or not 1 <= len(item['session']) <= 64):
                    raise ValueError('Invalid XInput frame')
                if item['session'] in self.old_sessions:
                    continue
                changed = self.session is not None and item['session'] != self.session
                if item['session'] != self.session:
                    if self.session is not None:
                        self.old_sessions.add(self.session)
                    self.session, self.sequence = item['session'], -1
                if item['seq'] <= self.sequence:
                    continue
                self.sequence = item['seq']
                # A restarted helper always produces a stop before accepting input.
                safety_event = safety_event or changed or not item['connected']
                latest = item
            except (ValueError, TypeError, UnicodeError):
                safety_event = True
                latest = {'connected': False}
        # A backlog/flood cannot become delayed movement commands.
        return {'connected': False}

    def close(self):
        self.socket.close()
