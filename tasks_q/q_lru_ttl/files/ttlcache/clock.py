class FakeClock:
    """A clock for tests: call it to read the time, advance() to move it."""

    def __init__(self, t=0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt
