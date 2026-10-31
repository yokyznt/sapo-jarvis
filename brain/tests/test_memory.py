from sapo.memory import Memory


def test_messages_order_and_limit(memory):
    for i in range(10):
        memory.add_message("user" if i % 2 == 0 else "sapo", f"m{i}")
    assert memory.recent_messages(3) == [("sapo", "m7"), ("user", "m8"), ("sapo", "m9")]


def test_events(memory):
    memory.add_event("petted", 0.2)
    memory.add_event("thrown", 0.9)
    assert memory.recent_events(5) == [("petted", 0.2), ("thrown", 0.9)]


def test_facts_dedupe_and_search(memory):
    assert memory.add_fact("Le gusta Roblox")
    assert not memory.add_fact("Le  gusta   Roblox")
    assert not memory.add_fact("   ")
    memory.add_fact("Se llama Dylan")
    assert memory.facts() == ["Le gusta Roblox", "Se llama Dylan"]
    assert memory.search("juega roblox?") == ["Le gusta Roblox"]


def test_persists_on_disk(tmp_path):
    path = tmp_path / "Sapo" / "memoria.db"
    m = Memory(path)
    m.add_message("user", "hola")
    m.add_fact("tiene un perro")
    m.close()
    m2 = Memory(path)
    assert m2.recent_messages(5) == [("user", "hola")]
    assert m2.facts() == ["tiene un perro"]
    assert m2.last_chat_age() is not None
    m2.close()


def test_custom_retriever_receives_index_calls():
    class Spy:
        def __init__(self):
            self.seen = []

        def index(self, kind, rowid, text):
            self.seen.append((kind, text))

        def search(self, query, k):
            return ["vector"]

    spy = Spy()
    m = Memory(":memory:", retriever=spy)
    m.add_message("user", "hola")
    m.add_fact("dato")
    assert spy.seen == [("message", "hola"), ("fact", "dato")]
    assert m.search("x") == ["vector"]
    m.close()
