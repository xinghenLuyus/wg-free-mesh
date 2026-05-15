from app.data.database import table_names
from app.data.store import store


def test_database_initializes_required_tables(client) -> None:
    assert {
        "backups",
        "configs",
        "nodes",
        "peer_links",
        "system_settings",
    }.issubset(set(table_names()))


def test_store_default_mqtt_setting_uses_environment_defaults(client) -> None:
    assert store.read_setting_json("mqtt_client", {}) == {}
