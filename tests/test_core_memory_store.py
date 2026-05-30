from opinion_trading.core.memory_store import JsonLineMemoryStore


def test_memory_store_append_and_read(tmp_path):
    ms = JsonLineMemoryStore(str(tmp_path))
    records = [{"a": 1}, {"b": 2}]
    ms.append_many("test.jsonl", records)
    rows = ms.read_all("test.jsonl")
    assert isinstance(rows, list)
    assert rows[0]["a"] == 1


def test_state_save_and_load(tmp_path):
    ms = JsonLineMemoryStore(str(tmp_path))
    state = {"cash": 1000}
    ms.save_state(state, file_name="state.json")
    loaded = ms.load_state("state.json")
    assert loaded["cash"] == 1000
