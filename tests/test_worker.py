from types import SimpleNamespace

from sigrif.worker import main


class FakeScalars:
    def __init__(self, items=()):
        self.items = list(items)

    def all(self):
        return self.items


class FakeSession:
    def __init__(self, existing, zones=()):
        self.existing = existing
        self.zones = list(zones)
        self.added = []
        self.committed = False
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def scalar(self, _):
        return self.existing

    def scalars(self, _):
        return FakeScalars(self.zones)

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.committed = True

    def execute(self, statement):
        self.executed.append(statement)


def _cell_feature(index: str, zone_name: str = "SECTOR CENTRO", zone_id: int = 1):
    return {
        "type": "Feature",
        "geometry": {
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
        },
        "properties": {
            "h3": index,
            "zone_id": zone_id,
            "comuna": "Valparaíso",
            "provincia": "Valparaíso",
            "zone_name": zone_name,
            "dominant_fuel": "Matorral",
            "fuel_native": 0.1,
            "fuel_plantation": 0.2,
            "fuel_shrub": 0.3,
            "fuel_grass": 0.0,
            "fuel_agriculture": 0.0,
            "fuel_urban": 0.0,
            "slope": 21.5,
            "historical_fires": 4,
            "wui_distance_m": 120.0,
            "risk_level": "Medio",
            "risk_score": 0.45,
        },
    }


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
    assert len(zones) == 563
    assert zones[0]["name"] == "SECTOR CENTRO"
    assert len({zone["name"] for zone in zones}) == 563


def test_seed_inserts_zones(monkeypatch):
    session = FakeSession(existing=0)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)

    main.seed_zones()

    assert len(session.added) == 563
    assert session.committed is True


def test_seed_replaces_old_zones(monkeypatch):
    session = FakeSession(existing=6)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)

    main.seed_zones()

    assert len(session.added) == 563
    assert len(session.executed) == 3


def test_seed_skips_existing_zones(monkeypatch):
    session = FakeSession(existing=563)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)

    main.seed_zones()

    assert session.added == []
    assert session.committed is True


def test_cells_file_prefers_regional_mesh():
    assert main.CELLS_FILE == main.REGIONAL_CELLS_FILE
    assert main.REGIONAL_CELLS_FILE.exists()


def test_load_cells_reads_regional_geojson():
    cells = main.load_cells()
    assert 20000 <= len(cells) <= 26000
    properties = cells[0]["properties"]
    assert "h3" in properties
    assert "zone_name" in properties
    assert "comuna" in properties


def test_seed_cells_inserts(monkeypatch):
    session = FakeSession(existing=0)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        main, "load_cells", lambda: [_cell_feature("a"), _cell_feature("b", "OTRO")]
    )

    main.seed_cells()

    assert len(session.added) == 2
    assert session.committed is True
    first = session.added[0]
    assert first.h3 == "a"
    assert first.comuna == "Valparaíso"
    assert first.zone_name == "SECTOR CENTRO"
    assert first.slope == 21.5
    assert first.historical_fires == 4


def test_seed_cells_maps_zone_name_to_database_id(monkeypatch):
    zone = SimpleNamespace(name="SECTOR CENTRO", id=42)
    session = FakeSession(existing=0, zones=[zone])
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    monkeypatch.setattr(main, "load_cells", lambda: [_cell_feature("a", zone_id=1)])

    main.seed_cells()

    assert session.added[0].zone_id == 42


def test_seed_cells_skips_existing(monkeypatch):
    session = FakeSession(existing=2)
    monkeypatch.setattr(main, "SessionLocal", lambda: session)
    monkeypatch.setattr(main, "load_cells", lambda: [_cell_feature("a"), _cell_feature("b")])

    main.seed_cells()

    assert session.added == []
    assert session.committed is False
