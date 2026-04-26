from threading import Condition


class RingBufferDualThread:
    def __init__(self, capacity):
        self.buffer = bytearray(capacity)
        self.capacity = capacity
        self.read_index = 0
        self.write_index = 0
        self.size = 0
        self.closed = False
        self.condition = Condition()

    def write(self, data):
        offset = 0

        with self.condition:
            while offset < len(data):
                while self.size == self.capacity and not self.closed:
                    self.condition.wait()

                if self.closed:
                    return

                free_space = self.capacity - self.size
                bytes_to_write = min(
                    len(data) - offset,
                    free_space,
                    self.capacity - self.write_index,
                )

                end = offset + bytes_to_write
                self.buffer[
                    self.write_index:self.write_index + bytes_to_write
                ] = data[offset:end]
                self.write_index = (self.write_index + bytes_to_write) % self.capacity
                self.size += bytes_to_write
                offset = end
                self.condition.notify_all()

    def read(self, size):
        with self.condition:
            bytes_to_read = min(size, self.size)
            data = bytearray()

            while bytes_to_read > 0:
                chunk_size = min(bytes_to_read, self.capacity - self.read_index)
                data += self.buffer[self.read_index:self.read_index + chunk_size]
                self.read_index = (self.read_index + chunk_size) % self.capacity
                self.size -= chunk_size
                bytes_to_read -= chunk_size

            finished = self.closed and self.size == 0

            if len(data) < size:
                data += bytes(size - len(data))

            self.condition.notify_all()
            return bytes(data), finished

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()

    def available(self):
        with self.condition:
            return self.size
