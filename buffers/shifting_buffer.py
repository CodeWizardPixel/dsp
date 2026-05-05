class ShiftingBuffer:
    def __init__(self, capacity):
        if capacity < 4 or capacity > 32 or capacity % 4 != 0:
            raise ValueError(
                "Shifting buffer capacity must be a multiple of 4 between 4 and 32 bytes"
            )

        self.capacity = capacity
        self.part_capacity = capacity // 2
        self.input_part = bytearray(self.part_capacity)
        self.output_part = bytearray(self.part_capacity)
        self.input_size = 0
        self.output_size = 0
        self.output_read_index = 0
        self.closed = False

    def write(self, data):
        offset = 0

        while offset < len(data) and not self.closed:
            if self.input_size == self.part_capacity:
                if not self.shift():
                    return

            free_space = self.part_capacity - self.input_size
            bytes_to_write = min(len(data) - offset, free_space)
            end = offset + bytes_to_write

            self.input_part[self.input_size:self.input_size + bytes_to_write] = data[
                offset:end
            ]
            self.input_size += bytes_to_write
            offset = end

            if self.input_size == self.part_capacity:
                self.shift()

    def shift(self):
        if self.input_size == 0 or self.output_size > 0:
            return False

        self.output_part[:self.input_size] = self.input_part[:self.input_size]
        self.output_size = self.input_size
        self.output_read_index = 0
        self.input_size = 0
        return True

    def read(self, size):
        if self.output_size == 0 and self.closed:
            self.shift()

        bytes_to_read = min(size, self.output_size)
        data = bytearray()

        while bytes_to_read > 0:
            chunk_size = min(
                bytes_to_read,
                self.output_size,
                self.part_capacity - self.output_read_index,
            )
            data += self.output_part[
                self.output_read_index:self.output_read_index + chunk_size
            ]
            self.output_read_index += chunk_size
            self.output_size -= chunk_size
            bytes_to_read -= chunk_size

            if self.output_size == 0:
                self.output_read_index = 0

        finished = self.closed and self.input_size == 0 and self.output_size == 0

        if len(data) < size:
            data += bytes(size - len(data))

        return bytes(data), finished

    def read_sample(self):
        return self.read(2)

    def read_sample_nonblocking(self):
        return self.read(2)

    def close(self):
        self.closed = True

    def available(self):
        if self.closed:
            return self.output_size + self.input_size

        return self.output_size
