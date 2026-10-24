"""Bounded newline framing for Pico USB serial; independent of ROS and JSON."""


class LineBuffer:
    """Keep partial reads and discard an oversized line through its delimiter."""

    def __init__(self, max_line_bytes=8192):
        if max_line_bytes < 1:
            raise ValueError("max_line_bytes must be positive")
        self.max_line_bytes = max_line_bytes
        self.pending = bytearray()
        self.discarding = False
        self.dropped_lines = 0

    def feed(self, data):
        frames = []
        pieces = data.split(b"\n")
        for index, piece in enumerate(pieces):
            if not self.discarding:
                if len(self.pending) + len(piece) > self.max_line_bytes:
                    self.pending.clear()
                    self.discarding = True
                    self.dropped_lines += 1
                else:
                    self.pending.extend(piece)
            if index < len(pieces) - 1:
                if not self.discarding:
                    frame = bytes(self.pending).rstrip(b"\r")
                    if frame:
                        frames.append(frame)
                self.pending.clear()
                self.discarding = False
        return frames
