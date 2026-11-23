import pytest

from ceridwen import db

ROUND_TRIP = [
    {"role": "user", "content": "What time is it?"},
    {"role": "assistant", "content": "", "tool_calls": [
        {"id": "call_abc", "function": {"name": "current_time", "arguments": {}}}
    ]},
    {"role": "tool", "content": "2026-11-23T06:23:00+00:00", "tool_name": "current_time"},
    {"role": "assistant", "content": "It's 06:23 UTC."},
]


@pytest.fixture
def path(tmp_path):
    # A fresh database file per test, inside pytest's temporary directory.
    p = tmp_path / "data" / "test.db"
    db.init_db(p)
    return p


# --- setup ---

def test_init_db_creates_missing_folders(tmp_path):
    p = tmp_path / "does" / "not" / "exist" / "test.db"
    db.init_db(p)
    assert p.exists()


def test_init_db_is_safe_to_run_twice(path):
    db.init_db(path)  # must not raise "table already exists"


# --- threads ---

def test_new_database_has_no_threads(path):
    assert db.list_threads(path) == []


def test_create_thread_returns_unique_ids(path):
    a, b = db.create_thread(path), db.create_thread(path)
    assert a != b
    assert {t["id"] for t in db.list_threads(path)} == {a, b}


def test_list_threads_returns_plain_dicts(path):
    db.create_thread(path)
    [thread] = db.list_threads(path)
    assert type(thread) is dict
    assert set(thread) == {"id", "title", "created_at", "updated_at"}


def test_list_threads_most_recently_updated_first(path):
    old, new = db.create_thread(path), db.create_thread(path)
    db.add_messages(path, old, [{"role": "user", "content": "bump"}])

    assert [t["id"] for t in db.list_threads(path)] == [old, new]


def test_delete_thread_removes_it_and_its_messages(path):
    keep, gone = db.create_thread(path), db.create_thread(path)
    db.add_messages(path, keep, [{"role": "user", "content": "stay"}])
    db.add_messages(path, gone, [{"role": "user", "content": "go"}])

    db.delete_thread(path, gone)

    assert [t["id"] for t in db.list_threads(path)] == [keep]
    assert db.get_messages(path, gone) == []         # cascade took the messages too
    assert db.get_messages(path, keep) == [{"role": "user", "content": "stay"}]


# --- messages ---

def test_new_thread_has_no_messages(path):
    assert db.get_messages(path, db.create_thread(path)) == []


def test_round_trip_returns_exactly_what_was_saved(path):
    thread = db.create_thread(path)
    db.add_messages(path, thread, ROUND_TRIP)

    assert db.get_messages(path, thread) == ROUND_TRIP


def test_plain_messages_have_no_optional_keys(path):
    thread = db.create_thread(path)
    db.add_messages(path, thread, [{"role": "user", "content": "Hi"}])

    [message] = db.get_messages(path, thread)
    assert set(message) == {"role", "content"}       # no tool_calls/tool_name keys at all


def test_empty_content_stays_an_empty_string(path):
    thread = db.create_thread(path)
    db.add_messages(path, thread, [ROUND_TRIP[1]])   # assistant tool call with content ""

    assert db.get_messages(path, thread)[0]["content"] == ""


def test_tool_calls_come_back_as_a_list_not_a_string(path):
    thread = db.create_thread(path)
    db.add_messages(path, thread, [ROUND_TRIP[1]])

    assert db.get_messages(path, thread)[0]["tool_calls"] == ROUND_TRIP[1]["tool_calls"]


def test_messages_keep_their_order_across_several_saves(path):
    thread = db.create_thread(path)
    for i in range(5):
        db.add_messages(path, thread, [{"role": "user", "content": str(i)}])

    assert [m["content"] for m in db.get_messages(path, thread)] == ["0", "1", "2", "3", "4"]


def test_messages_are_kept_per_thread(path):
    a, b = db.create_thread(path), db.create_thread(path)
    db.add_messages(path, a, [{"role": "user", "content": "for a"}])
    db.add_messages(path, b, [{"role": "user", "content": "for b"}])

    assert db.get_messages(path, a) == [{"role": "user", "content": "for a"}]


def test_add_messages_bumps_updated_at(path):
    thread = db.create_thread(path)
    [before] = db.list_threads(path)

    db.add_messages(path, thread, [{"role": "user", "content": "Hi"}])

    [after] = db.list_threads(path)
    assert after["updated_at"] > before["updated_at"]


def test_message_missing_role_saves_nothing(path):
    thread = db.create_thread(path)

    with pytest.raises(KeyError):
        db.add_messages(path, thread, [{"role": "user", "content": "ok"}, {"content": "no role"}])

    assert db.get_messages(path, thread) == []       # all or nothing


def test_messages_for_unknown_thread_are_rejected(path):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):      # foreign keys are actually on
        db.add_messages(path, "no-such-thread", [{"role": "user", "content": "Hi"}])


def test_missing_content_comes_back_as_empty_string(path):
    # Ollama expects content to be a string, never None.
    thread = db.create_thread(path)
    db.add_messages(path, thread, [{"role": "assistant", "tool_calls": [
        {"function": {"name": "current_time", "arguments": {}}}
    ]}])

    assert db.get_messages(path, thread)[0]["content"] == ""
