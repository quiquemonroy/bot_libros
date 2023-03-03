"""Tests for base botskeleton."""
import os
from shutil import copyfile
from typing import Generator

import pytest

import botskeleton

HERE = os.path.abspath(os.path.dirname(__file__))
JSON = os.path.join(HERE, "json")


def test_no_secrets_dir_fails(log: str) -> None:
    try:
        bs = botskeleton.BotSkeleton(log_filename=log)
        pytest.fail("Should throw exception for no secrets dir.")
    except botskeleton.BotSkeletonException as e:
        pass


def test_outputs_start_inactive(testdir: str, log: str) -> None:
    bs = botskeleton.BotSkeleton(secrets_dir=testdir, log_filename=log)

    # it would be funny to make this a mapped lambda
    for _, output in bs.outputs.items():
        assert not output["active"]


def test_load_null_history(testdir: str, log: str) -> None:
    name = "foobot"
    bs = botskeleton.BotSkeleton(bot_name=name, secrets_dir=testdir, log_filename=log)

    assert bs.history == []

    open(bs.history_filename, "w").close()
    bs.load_history()
    assert bs.history == []

    os.remove(bs.history_filename)
    os.remove(f"{bs.history_filename}.bak")


def test_load_existing_modern_history(testdir: str, testhist: str, log: str) -> None:
    bs = botskeleton.BotSkeleton(secrets_dir=testdir, history_filename=testhist, log_filename=log)
    bs.load_history()

    assert bs.history != []
    assert len(bs.history) == 2


def test_convert_legacy_history(testdir: str, legacyhist: str, hoistedhist: str, log: str) -> None:
    bs = botskeleton.BotSkeleton(secrets_dir=testdir, history_filename=legacyhist,
                                 log_filename=log)
    bs.load_history()

    assert bs.history != []

    mbs = botskeleton.BotSkeleton(secrets_dir=testdir, history_filename=hoistedhist,
                                  log_filename=log)
    mbs.load_history()

    assert len(bs.history) == len(mbs.history)
    for i, elem in enumerate(bs.history):
        melem = mbs.history[i]
        assert elem == melem


# regression test for the history corruption snafu.
def test_repair_corrupted_history(testdir: str, corruptedhist: str, repairedcorruptedhist: str,
                                  log: str
                                  ) -> None:
    bs = botskeleton.BotSkeleton(secrets_dir=testdir, history_filename=corruptedhist,
                                 log_filename=log)
    bs.load_history()

    assert bs.history != []

    # compare against repairedhist. they should be identical.
    mbs = botskeleton.BotSkeleton(secrets_dir=testdir, history_filename=repairedcorruptedhist,
                                  log_filename=log)
    mbs.load_history()

    assert mbs.history != []

    assert len(bs.history) == len(mbs.history)
    for i, elem in enumerate(bs.history):
        melem = mbs.history[i]
        for key, item in elem.__dict__.items():
            assert str(item) == str(melem.__dict__[key])


def test_idempotency(testdir: str, testhist: str, log: str) -> None:
    bs = botskeleton.BotSkeleton(secrets_dir=testdir, history_filename=testhist, log_filename=log)
    bs.load_history()

    # maybe find a less hacky way to do this.
    for entry in bs.history:
        entry._version = "9999"
    bs.update_history()

    identical = True
    hist_source = os.path.join(JSON, "test_entries.json")
    with open(testhist, "r") as f1, open(hist_source, "r") as f2:
        for line1, line2 in zip(f1, f2):
            if line1 != line2:
                identical = False
                break

    if not identical:
        pytest.fail("Test history changed when it shouldn't have been.")


@pytest.fixture(scope="function")
def testhist(testdir: str) -> Generator[str, str, None]:
    hist_source = os.path.join(JSON, "test_entries.json")
    hist_file = os.path.join(testdir, "test.json")
    copyfile(hist_source, hist_file)
    yield hist_file
    os.remove(hist_file)


@pytest.fixture(scope="function")
def legacyhist(testdir: str) -> Generator[str, str, None]:
    hist_source = os.path.join(JSON, "legacy_entries.json")
    hist_file = os.path.join(testdir, "legacy.json")
    copyfile(hist_source, hist_file)
    yield hist_file
    os.remove(hist_file)


@pytest.fixture(scope="function")
def hoistedhist(testdir: str) -> Generator[str, str, None]:
    hist_source = os.path.join(JSON, "legacy_hoisted_entries.json")
    hist_file = os.path.join(testdir, "hoisted.json")
    copyfile(hist_source, hist_file)
    yield hist_file
    os.remove(hist_file)


@pytest.fixture(scope="function")
def corruptedhist(testdir: str) -> Generator[str, str, None]:
    hist_source = os.path.join(JSON, "corrupted_entries.json")
    hist_file = os.path.join(testdir, "corrupted.json")
    copyfile(hist_source, hist_file)
    yield hist_file
    os.remove(hist_file)


@pytest.fixture(scope="function")
def repairedcorruptedhist(testdir: str) -> Generator[str, str, None]:
    hist_source = os.path.join(JSON, "repaired_corrupted_entries.json")
    hist_file = os.path.join(testdir, "repaired.json")
    copyfile(hist_source, hist_file)
    yield hist_file
    os.remove(hist_file)


@pytest.fixture(scope="module")
def log(testdir: str) -> Generator[str, str, None]:
    log = os.path.join(testdir, "log")
    open(log, "a").close()
    yield log
    os.remove(log)


@pytest.fixture(scope="module")
def testdir() -> Generator[str, str, None]:
    directory = os.path.join(HERE, "testing_playground")
    os.mkdir(directory)
    yield directory
    os.rmdir(directory)
