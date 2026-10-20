from sigrif.worker import main


class FakeSession:
    def __init__(self, existing):
        self.existing = existing
        self.added = []
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def scalar(self, _):
        return self.existing

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.committed = True


def test_polygon_returns_wkt():
    wkt = main._polygon(-71.68, -33.06, -71.60, -33.01)
    assert wkt.startswith("MULTIPOLYGON(((")
    assert "-71.68 -33.06" in wkt
    assert "-71.6 -33.01" in wkt


def test_seed_inserts_zones(monkeypatch):
    session = FakeSession(existing=None)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)

    main.seed()

    assert len(session.added) == len(main.ZONES)
    assert session.committed is True
    assert {zone.name for zone in session.added} == {
        "Valparaiso",
        "Vina del Mar",
        "Quilpue",
        "Villa Alemana",
        "Concon",
        "Casablanca",
    }


def test_seed_skips_existing_zones(monkeypatch):
    session = FakeSession(existing=1)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)

    main.seed()

    assert session.added == []
    assert session.committed is False
