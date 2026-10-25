from sapo.ratelimit import RateLimiter


def test_per_key_interval(clock):
    rl = RateLimiter(per_key=10, max_hits=100, window=60, clock=clock)
    assert rl.allow("petted")
    assert not rl.allow("petted")
    assert rl.allow("thrown")
    clock.now = 10
    assert rl.allow("petted")


def test_global_window(clock):
    rl = RateLimiter(per_key=0, max_hits=3, window=60, clock=clock)
    assert [rl.allow(str(i)) for i in range(5)] == [True, True, True, False, False]
    clock.now = 59.9
    assert not rl.allow("x")
    clock.now = 60
    assert rl.allow("x")


def test_denied_does_not_consume(clock):
    rl = RateLimiter(per_key=5, max_hits=2, window=60, clock=clock)
    assert rl.allow("a")
    assert not rl.allow("a")
    assert rl.allow("b")
    assert not rl.allow("c")
