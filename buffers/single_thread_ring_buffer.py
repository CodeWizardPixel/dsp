class SingleThreadRingBuffer:
    def __init__(self, capacity):
        self.buffer = bytearray(capacity)
        self.capacity = capacity
        self.read_index = 0
        self.write_index = 0
        self.size = 0
        self.closed = False

    def write(self, data):
        offset = 0

        while offset < len(data) and not self.closed:
            free_space = self.capacity - self.size
            if free_space == 0:
                return

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

    def read(self, size):
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

        return bytes(data), finished

    def close(self):
        self.closed = True

    def available(self):
        return self.size
