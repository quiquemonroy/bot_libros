"""Skeleton for twitter bots. Spooky."""
import json
import pkg_resources
import time
from datetime import datetime
from logging import Logger
from os import path
from shutil import copyfile
from typing import Any, Callable, Dict, List

import bottilities as util
from clint.textui import progress

from .outputs.output_birdsite import BirdsiteSkeleton, TweetRecord
from .outputs.output_mastodon import MastodonSkeleton, TootRecord
from .outputs.output_utils import OutputSkeleton, OutputRecord
from .error import BotSkeletonException

# Record of one round of media uploads.
class IterationRecord:
    """Record of one iteration. Includes records of all outputs."""
    def __init__(self, extra_keys: Dict[str, Any]={}) -> None:
        self._version = pkg_resources.require(__package__)[0].version
        self._type = self.__class__.__name__
        self.timestamp = datetime.now().isoformat()
        self.extra_keys = extra_keys
        self.output_records: Dict[str, OutputRecord] = {}

    def __str__(self) -> str:
        """Print object."""
        return str(self.__dict__)

    def __repr__(self) -> str:
        """repr object."""
        return str(self)

    def __eq__(self, other:Any) -> bool:
        """Equality."""
        if isinstance(other, IterationRecord):
            for key, value in self.__dict__.items():
                if value != other.__dict__[key]:
                    return False

                return True
        return False

    @classmethod
    def from_dict(cls, obj_dict: Dict[str, Any]) -> "IterationRecord":
        """Get object back from dict."""
        obj = cls()
        for key, item in obj_dict.items():
            obj.__dict__[key] = item

        return obj


# Main class - handles sending and history management and such.
class BotSkeleton():
    def __init__(self, secrets_dir:str=None, log_filename:str=None, history_filename:str=None,
                 bot_name:str="A bot", delay:int=3600) -> None:
        """Set up generic skeleton stuff."""

        if secrets_dir is None:
            msg = "Please provide secrets dir!"
            raise BotSkeletonException(desc=msg)

        # some limits on skeleton action.
        self.lookback_limit=50

        self.secrets_dir = secrets_dir
        self.bot_name = bot_name
        self.delay = delay

        if log_filename is None:
            log_filename = path.join(self.secrets_dir, "log")
        self.log_filename = log_filename
        self.log = util.set_up_logging(
            log_filename=self.log_filename,
            use_date_logging=True,
        )

        if history_filename is None:
            history_filename = path.join(self.secrets_dir, f"{self.bot_name}-history.json")
        self.history_filename = history_filename

        self.extra_keys: Dict[str, Any] = {}
        self.history = self.load_history()

        self.outputs = {
            "birdsite": {
                "active": False,
                "obj": BirdsiteSkeleton()
            },
            "mastodon": {
                "active": False,
                "obj": MastodonSkeleton()
            },
        }

        self._setup_all_outputs()

    ###############################################################################################
    ####        PUBLIC API METHODS                                                             ####
    ###############################################################################################
    def send(
            self,
            *args: str,
            text: str=None,
    ) -> IterationRecord:
        """
        Post text-only to all outputs.

        :param args: positional arguments.
            expected: text to send as message in post.
            keyword text argument is preferred over this.
        :param text: text to send as message in post.
        :returns: new record of iteration
        """
        if text is not None:
            final_text = text
        else:
            if len(args) == 0:
                raise BotSkeletonException(("Please provide text either as a positional arg or "
                                            "as a keyword arg (text=TEXT)"))
            else:
                final_text = args[0]

        # TODO there could be some annotation stuff here.
        record = IterationRecord(extra_keys=self.extra_keys)
        for key, output in self.outputs.items():
            if output["active"]:
                self.log.info(f"Output {key} is active, calling send on it.")
                entry: Any = output["obj"]
                output_result = entry.send(text=final_text)
                record.output_records[key] = output_result

            else:
                self.log.info(f"Output {key} is inactive. Not sending.")

        self.history.append(record)
        self.update_history()

        return record

    def send_with_one_media(
            self,
            *args: str,
            text: str=None,
            file: str=None,
            caption: str=None,
    ) -> IterationRecord:
        """
        Post with one media item to all outputs.
        Provide filename so outputs can handle their own uploads.

        :param args: positional arguments.
            expected:
                text to send as message in post.
                file to be uploaded.
                caption to be paired with file.
            keyword arguments preferred over positional ones.
        :param text: text to send as message in post.
        :param file: file to be uploaded in post.
        :param caption: caption to be uploaded alongside file.
        :returns: new record of iteration
        """
        final_text = text
        if final_text is None:
            if len(args) < 1:
                raise TypeError(("Please provide either positional argument "
                                 "TEXT, or keyword argument text=TEXT"))
            else:
                final_text = args[0]

        final_file = file
        if final_file is None:
            if len(args) < 2:
                raise TypeError(("Please provide either positional argument "
                                            "FILE, or keyword argument file=FILE"))
            else:
                final_file = args[1]

        # this arg is ACTUALLY optional,
        # so the pattern is changed.
        final_caption = caption
        if final_caption is None:
            if len(args) >= 3:
                final_caption = args[2]

        # TODO more error checking like this.
        if final_caption is None or final_caption == "":
            captions:List[str] = []
        else:
            captions = [final_caption]

        record = IterationRecord(extra_keys=self.extra_keys)
        for key, output in self.outputs.items():
            if output["active"]:
                self.log.info(f"Output {key} is active, calling media send on it.")
                entry: Any = output["obj"]
                output_result = entry.send_with_media(text=final_text,
                                                      files=[final_file],
                                                      captions=captions)
                record.output_records[key] = output_result
            else:
                self.log.info(f"Output {key} is inactive. Not sending with media.")

        self.history.append(record)
        self.update_history()

        return record

    def send_with_many_media(
            self,
            *args: str,
            text: str=None,
            files: List[str]=None,
            captions: List[str]=[],
    ) -> IterationRecord:
        """
        Post with several media.
        Provide filenames so outputs can handle their own uploads.

        :param args: positional arguments.
            expected:
                text to send as message in post.
                files to be uploaded.
                captions to be paired with files.
            keyword arguments preferred over positional ones.
        :param text: text to send as message in post.
        :param files: files to be uploaded in post.
        :param captions: captions to be uploaded alongside files.
        :returns: new record of iteration
        """
        if text is None:
            if len(args) < 1:
                raise TypeError(("Please provide either required positional argument "
                                 "TEXT, or keyword argument text=TEXT"))
            else:
                final_text = args[0]
        else:
            final_text = text

        if files is None:
            if len(args) < 2:
                raise TypeError(("Please provide either positional argument "
                                 "FILES, or keyword argument files=FILES"))
            else:
                final_files = list(args[1:])
        else:
            final_files = files

        # captions have never been permitted to be provided as positional args
        # (kind of backed myself into that)
        # so they just get defaulted and it's fine.

        record = IterationRecord(extra_keys=self.extra_keys)
        for key, output in self.outputs.items():
            if output["active"]:
                self.log.info(f"Output {key} is active, calling media send on it.")
                entry: Any = output["obj"]
                output_result = entry.send_with_media(text=final_text,
                                                      files=final_files,
                                                      captions=captions)
                record.output_records[key] = output_result
            else:
                self.log.info(f"Output {key} is inactive. Not sending with media.")

        self.history.append(record)
        self.update_history()

        return record

    def perform_batch_reply(
            self,
            *,
            callback: Callable[..., str]=None,
            target_handles: Dict[str, str]=None,
            lookback_limit: int=20,
            per_service_lookback_limit: Dict[str, int]=None,
    ) -> IterationRecord:
        """
        Performs batch reply on target accounts.
        Looks up the recent messages of the target user,
        applies the callback,
        and replies with
        what the callback generates.

        :param callback: a callback taking a message id,
            message contents,
            and optional extra keys,
            and returning a message string.
        :param targets: a dictionary of service names to target handles
            (currently only one per service).
        :param lookback_limit: a lookback limit of how many messages to consider (optional).
        :param per_service_lookback: and a dictionary of service names to per-service
            lookback limits.
            takes preference over lookback_limit (optional).
        :returns: new record of iteration
        :raises BotSkeletonException: raises BotSkeletonException if batch reply fails or cannot be
            performed
        """
        if callback is None:
            raise BotSkeletonException("Callback must be provided.""")

        if target_handles is None:
            raise BotSkeletonException("Targets must be provided.""")

        if lookback_limit > self.lookback_limit:
            raise BotSkeletonException(
                f"Lookback_limit cannot exceed {self.lookback_limit}, " +
                f"but it was {lookback_limit}"
            )

        # use per-service lookback dict for convenience in a moment.
        # if necessary, use lookback_limit to fill it out.
        lookback_dict = per_service_lookback_limit
        if (lookback_dict is None):
            lookback_dict = {}

        record = IterationRecord(extra_keys=self.extra_keys)
        for key, output in self.outputs.items():
            if key not in lookback_dict:
                lookback_dict[key] = lookback_limit

            if target_handles.get(key, None) is None:
                self.log.info(f"No target for output {key}, skipping this output.")

            elif not output.get("active", False):
                self.log.info(f"Output {key} is inactive. Not calling batch reply.")

            elif output["active"]:
                self.log.info(f"Output {key} is active, calling batch reply on it.")
                entry: Any = output["obj"]
                output_result = entry.perform_batch_reply(callback=callback,
                                                          target_handle=target_handles[key],
                                                          lookback_limit=lookback_dict[key],
                                                          )
                record.output_records[key] = output_result

        self.history.append(record)
        self.update_history()

        return record

    def nap(self) -> None:
        """
        Go to sleep for the duration of self.delay.

        :returns: None
        """
        self.log.info(f"Sleeping for {self.delay} seconds.")
        for _ in progress.bar(range(self.delay)):
            time.sleep(1)

    def store_extra_info(self, key: str, value: Any) -> None:
        """
        Store some extra value in the messaging storage.

        :param key: key of dictionary entry to add.
        :param value: value of dictionary entry to add.
        :returns: None
        """
        self.extra_keys[key] = value

    def store_extra_keys(self, d: Dict[str, Any]) -> None:
        """
        Store several extra values in the messaging storage.

        :param d: dictionary entry to merge with current self.extra_keys.
        :returns: None
        """
        new_dict = dict(self.extra_keys, **d)
        self.extra_keys = new_dict.copy()

    def update_history(self) -> None:
        """
        Update messaging history on disk.

        :returns: None
        """

        jsons = []
        for item in self.history:
            json_item = item.__dict__

            # Convert sub-entries into JSON as well.
            json_item["output_records"] = self._parse_output_records(item)

            jsons.append(json_item)

        if not path.isfile(self.history_filename):
            open(self.history_filename, "a+").close()

        with open(self.history_filename, "w") as f:
            json.dump(jsons, f, default=lambda x: x.__dict__.copy(), sort_keys=True, indent=4)
            f.write("\n") # add trailing new line dump skips.

    def load_history(self) -> List["IterationRecord"]:
        """
        Load messaging history from disk to self.

        :returns: List of iteration records comprising history.
        """
        if path.isfile(self.history_filename):
            with open(self.history_filename, "r") as f:
                try:
                    dicts = json.load(f)

                except json.decoder.JSONDecodeError as e:
                    self.log.error(f"Got error \n{e}\n decoding JSON history, overwriting it.\n"
                                   f"Former history available in {self.history_filename}.bak")
                    copyfile(self.history_filename, f"{self.history_filename}.bak")
                    return []

                history: List[IterationRecord] = []
                for hdict_pre in dicts:

                    if "_type" in hdict_pre and hdict_pre["_type"] == IterationRecord.__name__:
                        # repair any corrupted entries
                        hdict = _repair(hdict_pre)
                        record = IterationRecord.from_dict(hdict)
                        history.append(record)

                    # Be sure to handle legacy tweetrecord-only histories.
                    # Assume anything without our new _type (which should have been there from the
                    # start, whoops) is a legacy history.
                    else:
                        item = IterationRecord()

                        # Lift extra keys up to upper record (if they exist).
                        extra_keys = hdict_pre.pop("extra_keys", {})
                        item.extra_keys = extra_keys

                        hdict_obj = TweetRecord.from_dict(hdict_pre)

                        # Lift timestamp up to upper record.
                        item.timestamp = hdict_obj.timestamp

                        item.output_records["birdsite"] = hdict_obj

                        history.append(item)

                return history

        else:
            return []

    ###############################################################################################
    ####        "PRIVATE" CLASS METHODS AND UTILITIES                                          ####
    ###############################################################################################
    def _setup_all_outputs(self) -> None:
        """Set up all output methods. Provide them credentials and anything else they need."""

        # The way this is gonna work is that we assume an output should be set up iff it has a
        # credentials_ directory under our secrets dir.
        for key in self.outputs.keys():
            credentials_dir = path.join(self.secrets_dir, f"credentials_{key}")

            # special-case birdsite for historical reasons.
            if key == "birdsite" and not path.isdir(credentials_dir) \
                    and path.isfile(path.join(self.secrets_dir, "CONSUMER_KEY")):
                credentials_dir = self.secrets_dir

            if path.isdir(credentials_dir):
                output_skeleton = self.outputs[key]

                output_skeleton["active"] = True

                obj: Any = output_skeleton["obj"]
                obj.cred_init(secrets_dir=credentials_dir, log=self.log, bot_name=self.bot_name)

                output_skeleton["obj"] = obj

                self.outputs[key] = output_skeleton

    def _parse_output_records(self, item: IterationRecord) -> Dict[str, Any]:
        """Parse output records into dicts ready for JSON."""
        output_records = {}
        for key, sub_item in item.output_records.items():
            if isinstance(sub_item, dict) or isinstance(sub_item, list):
                output_records[key] = sub_item
            else:
                output_records[key] = sub_item.__dict__

        return output_records


###################################################################################################
####        RE-EXPOSED PUBLIC API METHODS                                                      ####
###################################################################################################
def rate_limited(max_per_hour: int, *args: Any) -> Callable[..., Any]:
    """Rate limit a function."""
    return util.rate_limited(max_per_hour, *args)


def set_up_logging(*args: Any, **kwargs: Any) -> Logger:
    """Set up proper logging."""
    return util.set_up_logging(kwargs)


def random_line(file_path: str) -> str:
    """Get random line from file."""
    return util.random_line(file_path=file_path)


###################################################################################################
####      "PRIVATE" MODULE METHODS, NOT INTENDED FOR PUBLIC USE                                ####
###################################################################################################
def _repair(record: Dict[str, Any]) -> Dict[str, Any]:
    """Repair a corrupted IterationRecord with a specific known issue."""
    output_records = record.get("output_records")
    if record.get("_type", None) == "IterationRecord" and output_records is not None:
        birdsite_record = output_records.get("birdsite")

        # check for the bug
        if isinstance(birdsite_record, dict) and birdsite_record.get("_type") == "IterationRecord":

            # get to the bottom of the corrupted record
            failed = False
            while birdsite_record.get("_type") == "IterationRecord":
                sub_record = birdsite_record.get("output_records")
                if sub_record is None:
                    failed = True
                    break

                birdsite_record = sub_record.get("birdsite")
                if birdsite_record is None:
                    failed = True
                    break

            if failed:
                return record

            # add type
            birdsite_record["_type"] = TweetRecord.__name__

            # lift extra keys, just in case
            if "extra_keys" in birdsite_record:
                record_extra_values = record.get("extra_keys", {})
                for key, value in birdsite_record["extra_keys"].items():
                    if key not in record_extra_values:
                        record_extra_values[key] = value

                record["extra_keys"] = record_extra_values

                del birdsite_record["extra_keys"]

            output_records["birdsite"] = birdsite_record

        # pull that correct record up to the top level, fixing corruption
        record["output_records"] = output_records

    return record
