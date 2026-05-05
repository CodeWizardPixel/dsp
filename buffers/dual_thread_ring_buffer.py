from threading import Condition


class RingBufferDualThread:
    def __init__(self, capacity):
        if capacity < 2 or capacity > 512 or capacity % 2 != 0:
            raise ValueError(
                "Ring buffer capacity must be an even value between 2 and 512 bytes"
            )

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

    def read_sample(self, timeout=None):
        with self.condition:
            while self.size < 2 and not self.closed:
                if timeout is None:
                    self.condition.wait()
                elif timeout <= 0:
                    break
                else:
                    self.condition.wait(timeout)
                    break

            bytes_to_read = min(2, self.size)
            data = bytearray()

            while bytes_to_read > 0:
                chunk_size = min(bytes_to_read, self.capacity - self.read_index)
                data += self.buffer[self.read_index:self.read_index + chunk_size]
                self.read_index = (self.read_index + chunk_size) % self.capacity
                self.size -= chunk_size
                bytes_to_read -= chunk_size

            finished = self.closed and self.size == 0

            if len(data) < 2:
                data += bytes(2 - len(data))

            self.condition.notify_all()
            return bytes(data), finished

    def read_sample_nonblocking(self):
        return self.read(2)

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()

    def available(self):
        with self.condition:
            return self.size

    def free_space(self):
        with self.condition:
            return self.capacity - self.size

    def wait_for_free_space(self):
        with self.condition:
            while self.size == self.capacity and not self.closed:
                self.condition.wait()

            if self.closed:
                return 0

            return self.capacity - self.size
