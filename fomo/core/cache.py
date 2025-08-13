from collections import OrderedDict

class SliceCache:
    def __init__(self, capacity=128):
        self.capacity = capacity
        self._data = OrderedDict()

    def get(self, key):
        return self._data.get(key)

    def put(self, key, value):
        if key in self._data:
            self._data.pop(key)
        self._data[key] = value
        while len(self._data) > self.capacity:
            self._data.popitem(last=False)

    def clear(self):
        self._data.clear()
