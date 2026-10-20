from sigrif.worker import main


class FakeSession:
    def __init__(self, existing):
        self.existing = existing
        self.added = []
        self.committed = False
        self.executed = []

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

    def execute(self, statement):
        self.executed.append(statement)


def test_multipolygon_wkt_from_polygon():
    geometry = {
        "type": "Polygon",
        "coordinates": [
            [
                [-71.0, -33.0],
                [-71.0, -33.1],
                [-70.9, -33.1],
                [-70.9, -33.0],
                [-71.0, -33.0],
            ]
        ],
    }
    wkt = main._multipolygon_wkt(geometry)
    assert wkt.startswith("MULTIPOLYGON(((")
    assert "-71.0 -33.0" in wkt


def test_load_zones_reads_geojson():
    zones = main.load_zones()
    assert len(zones) == 54
    assert zones[0][0] == "SECTOR CENTRO"
    assert len({zone[0] for zone in zones}) == 54


def test_seed_inserts_zones(monkeypatch):
    session = FakeSession(existing=0)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)

    main.seed()

    assert len(session.added) == 54
    assert session.committed is True


def test_seed_replaces_old_zones(monkeypatch):
    session = FakeSession(existing=6)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)

    main.seed()

    assert len(session.added) == 54
    assert len(session.executed) == 2


def test_seed_skips_existing_zones(monkeypatch):
    session = FakeSession(existing=54)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)

    main.seed()

    assert session.added == []
    assert session.committed is False
