try:
    import uhashlib
except ImportError:
    uhashlib = None

def init():
    c = getattr(uhashlib, "sha256", None)
    if not c:
        c = __import__("_sha256", None, None, (), 1)
        c = getattr(c, "sha256")
    globals()["sha256"] = c

init()


def new(algo, data=b""):
    try:
        c = globals()[algo]
        return c(data)
    except KeyError:
        raise ValueError(algo)
