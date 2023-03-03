import os
from shutil import copyfile
from typing import Any, Generator

import pytest

import botskeleton

HERE = os.path.abspath(os.path.dirname(__file__))

def test_birdsite_activates_correctly(testdir: str, credentials: str, log: str) -> None:
    bs = botskeleton.BotSkeleton(secrets_dir=testdir, log_filename=log)

    assert(bs.outputs["birdsite"]["active"])

def test_birdsite_activates_with_owner_id_correctly(testdir: str, credentials: str, log: str
                                                    ) -> None:
    # no owner set
    bs = botskeleton.BotSkeleton(secrets_dir=testdir, log_filename=log)

    assert(bs.outputs["birdsite"]["active"])
    birdsite_obj: Any = bs.outputs["birdsite"]["obj"]
    assert(birdsite_obj.owner_handle == "")

    TESTSTR = "foo"
    TESTFILE = os.path.join(credentials, "OWNER_HANDLE")
    with open(TESTFILE, "w") as f:
        f.write(TESTSTR)

    bs = botskeleton.BotSkeleton(secrets_dir=testdir, log_filename=log)

    assert(bs.outputs["birdsite"]["active"])
    birdsite_obj = bs.outputs["birdsite"]["obj"]
    assert(birdsite_obj.owner_handle == TESTSTR)

    os.remove(TESTFILE)


@pytest.fixture(scope="function")
def credentials(testdir: str) -> Generator[str, str, None]:
    credentials_birdsite = os.path.join(testdir, "credentials_birdsite")
    os.mkdir(credentials_birdsite)

    files = ["CONSUMER_KEY", "CONSUMER_SECRET", "ACCESS_SECRET", "ACCESS_TOKEN"]
    for file in files:
        open(os.path.join(credentials_birdsite, file), "a").close()

    yield credentials_birdsite

    for file in files:
        os.remove(os.path.join(credentials_birdsite, file))

    os.rmdir(credentials_birdsite)


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

    # make sure we clean up if the tests forgot.
    files = os.listdir(directory)
    for file in files:
        os.remove(os.path.join(directory, file))


    os.rmdir(directory)
