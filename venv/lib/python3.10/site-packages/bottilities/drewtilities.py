"""Utility methods for Python packages (written with puckfetcher and botskeleton in mind)."""
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import math
import os
import random
import sys
import time
from typing import Any, Callable, Dict, List, Set

import requests

import clint.textui as tui

HERE = os.path.abspath(os.path.dirname(__file__))
LOG = logging.getLogger("root")

CHUNK_SIZE=1024
FORCED_ENCODING = "UTF-8"
LAST_CALLED: Dict[str, float] = {}

def ensure_dir(directory: str) -> None:
    """Create a directory if it doesn't exist."""
    if not os.path.isdir(directory):
        LOG.debug(f"Directory {directory} does not exist, creating it.")
        os.makedirs(directory)

def expand(directory: str) -> str:
    """Apply expanduser and expandvars to directory to expand '~' and env vars."""
    temp1 = os.path.expanduser(directory)
    return os.path.expandvars(temp1)

def generate_downloader(headers: Dict[str, str], args: Any, max_per_hour: int=30
                        ) -> Callable[..., None]:
    """Create function to download with rate limiting and text progress."""

    def _downloader(url: str, dest: str) -> None:

        @rate_limited(max_per_hour, args)
        def _rate_limited_download() -> None:

            # Create parent directory of file, and its parents, if they don't exist.
            parent = os.path.dirname(dest)
            if not os.path.exists(parent):
                os.makedirs(parent)

            response = requests.get(url, headers=headers, stream=True)
            LOG.info(f"Downloading from '{url}'.")
            LOG.info(f"Trying to save to '{dest}'.")

            length = response.headers.get("content-length")
            if length is None:
                total_length = 0
            else:
                total_length = int(length)

            expected_size = (total_length / CHUNK_SIZE) + 1
            chunks = response.iter_content(chunk_size=CHUNK_SIZE)

            open(dest, "a", encoding=FORCED_ENCODING).close()
            # per http://stackoverflow.com/a/20943461
            with open(dest, "wb") as stream:
                for chunk in tui.progress.bar(chunks, expected_size=expected_size):
                    if not chunk:
                        return
                    stream.write(chunk)
                    stream.flush()

        _rate_limited_download()

    return _downloader

def max_clamp(val: int, limit: int) -> int:
    """Clamp int to limit."""
    return min(val, limit)

def parse_int_string(int_string: str) -> List[int]:
    """
    Given a string like "1 23 4-8 32 1", return a unique list of those integers in the string and
    the integers in the ranges in the string.
    Non-numbers ignored. Not necessarily sorted
    """
    cleaned = " ".join(int_string.strip().split())
    cleaned = cleaned.replace(" - ", "-")
    cleaned = cleaned.replace(",", " ")

    tokens = cleaned.split(" ")
    indices: Set[int] = set()
    for token in tokens:
        if "-" in token:
            endpoints = token.split("-")
            if len(endpoints) != 2:
                LOG.info(f"Dropping '{token}' as invalid - weird range.")
                continue

            start = int(endpoints[0])
            end = int(endpoints[1]) + 1

            indices = indices.union(indices, set(range(start, end)))

        else:
            try:
                indices.add(int(token))
            except ValueError:
                LOG.info(f"Dropping '{token}' as invalid - not an int.")

    return list(indices)

# Modified from https://stackoverflow.com/a/667706
def rate_limited(max_per_hour: int, *args: Any) -> Callable[..., Any]:
    """Decorator to limit function to N calls/hour."""
    min_interval = 3600.0 / float(max_per_hour)

    def _decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        things = [func.__name__]
        things.extend(args)
        key = "".join(things)
        LOG.debug(f"Rate limiter called for '{key}'.")
        if key not in LAST_CALLED:
            LOG.debug(f"Initializing entry for '{key}'.")
            LAST_CALLED[key] = 0.0

        def _rate_limited_function(*args: Any, **kargs: Any) -> Any:
            last_called = LAST_CALLED[key]
            now = time.time()
            elapsed = now - last_called
            remaining = min_interval - elapsed
            LOG.debug(f"Rate limiter last called for '{key}' at {last_called}.")
            LOG.debug(f"Remaining cooldown time for '{key}' is {remaining}.")

            if remaining > 0 and last_called > 0.0:
                LOG.info(f"Self-enforced rate limit hit, sleeping {remaining} seconds.")
                for i in tui.progress.bar(range(math.ceil(remaining))):
                    time.sleep(1)

            LAST_CALLED[key] = time.time()
            ret = func(*args, **kargs)
            LOG.debug(f"Updating rate limiter last called for '{key}' to {now}.")
            return ret

        return _rate_limited_function
    return _decorate

def sanitize(filename: str, platform: str=None) -> str:
    """
    Remove disallowed characters from potential filename. Currently only guaranteed on Linux and
    OS X.
    """
    win_map = {
        # taken from samba Catia module.
        # https://www.samba.org/samba/docs/current/man-html/vfs_catia.8.html
        "\"": "¨",
        "*": "¤",
        "/": "ÿ",
        ":": "÷",
        "<": "«",
        ">": "»",
        "?": "¿",
        "\\": "ÿ",
        "|": "¦",
    }

    posix_map = {
        "/": "-",
    }

    if platform is None:
        platform = sys.platform

    if platform.startswith("win32"):
        replace_map = win_map
    else:
        replace_map = posix_map

    for key, entry in replace_map.items():
        filename = filename.replace(key, entry)

    return filename

def set_up_logging(
        *,
        log_filename: str = "log",
        verbosity: int = 0,
        use_date_logging: bool = False,
) ->logging.Logger:
    """Set up proper logging."""

    # log everything verbosely
    LOG.setLevel(logging.DEBUG)

    logging.Formatter.converter = time.gmtime

    handler: Any
    if use_date_logging:
        handler = TimedRotatingFileHandler(
            filename=log_filename,
            when="D",
            utc=True,
        )

    else:
        handler = RotatingFileHandler(
            filename=log_filename,
            maxBytes=1024000000,
            backupCount=10,
        )

    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03dZ - %(levelname)s - %(module)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)
    LOG.addHandler(handler)

    # Provide a stdout handler logging at INFO.
    stream_handler = logging.StreamHandler(sys.stdout)
    simple_form = logging.Formatter(fmt="%(message)s")
    stream_handler.setFormatter(simple_form)

    if verbosity > 0:
        stream_handler.setLevel(logging.DEBUG)
    else:
        stream_handler.setLevel(logging.INFO)

    LOG.addHandler(stream_handler)

    return LOG

def random_line(file_path: str, encoding: str = FORCED_ENCODING) -> str:
    """Get random line from a file."""
    # Fancy alg from http://stackoverflow.com/a/35579149 to avoid loading full file.
    line_num = 0
    selected_line = ""
    with open(file_path, encoding=encoding) as stream:
        while True:
            line = stream.readline()
            if not line:
                break
            line_num += 1
            if random.uniform(0, line_num) < 1:
                selected_line = line

    return selected_line.strip()
