import json

import pytest

from sapo.personality import clip, parse_reply
from sapo.protocol import MAX_SAY, ProtocolError, action, decode, encode, say, thinking


def test_decode_hello_chat_event():
    assert decode('{"type":"hello","version":1}') == {"type": "hello", "version": 1}
    assert decode('{"type":"chat","text":"  hola  "}') == {"type": "chat", "text": "hola"}
    assert decode('{"type":"event","name":"petted","boredom":0.4}') == {"type": "event", "name": "petted", "boredom": 0.4}


def test_decode_clamps_boredom():
    assert decode('{"type":"event","name":"thrown","boredom":7}')["boredom"] == 1.0
    assert decode('{"type":"event","name":"thrown"}')["boredom"] == 0.0


@pytest.mark.parametrize(
    "raw",
    [
        "no json",
        "[1,2]",
        '{"type":"nada"}',
        '{"type":"chat","text":""}',
        '{"type":"chat"}',
        '{"type":"event","name":"explotar"}',
        '{"type":"event","name":"petted","boredom":"mucho"}',
        '{"type":"hello"}',
    ],
)
def test_decode_rejects(raw):
    with pytest.raises(ProtocolError):
        decode(raw)


def test_outgoing_messages():
    assert say("hola", "happy") == {"type": "say", "text": "hola", "mood": "happy"}
    assert say("x", "furioso")["mood"] == "sarcastic"
    assert len(say("a" * 200)["text"]) == MAX_SAY
    assert action("dance") == {"type": "action", "name": "dance"}
    assert action("volar") == {"type": "action", "name": "none"}
    assert thinking(True) == {"type": "thinking", "on": True}
    assert json.loads(encode(say("¿qué onda?"))) == {"type": "say", "text": "¿qué onda?", "mood": "sarcastic"}
    assert "¿" in encode(say("¿qué?"))


def test_parse_reply_variants():
    r = parse_reply('{"say":"Hola wey","mood":"annoyed","action":"jump","fact":"Se llama Dylan"}')
    assert (r.say, r.mood, r.action, r.fact) == ("Hola wey", "annoyed", "jump", "Se llama Dylan")
    r = parse_reply('<think>mmm</think>basura {"say":"ok","mood":"raro","action":"bailar"} fin')
    assert (r.say, r.mood, r.action) == ("ok", "sarcastic", "none")
    assert parse_reply("texto plano").say == "texto plano"


def test_clip_limit():
    long = "palabra " * 40
    out = clip(long)
    assert len(out) <= MAX_SAY
    assert out.endswith("…")
