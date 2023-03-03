"""Skeleton code for sending to mastodon."""
import html
import json
import re
from logging import Logger
from os import path
from typing import Any, Callable, Dict, List, Optional

import mastodon

from .output_utils import OutputRecord, OutputSkeleton

class MastodonSkeleton(OutputSkeleton):
    def __init__(self) -> None:
        """Set up mastodon skeleton stuff."""
        self.name = "MASTODON"

    def cred_init(
            self,
            *,
            secrets_dir: str,
            log: Logger,
            bot_name: str="",
    ) -> None:
        """Initialize what requires credentials/secret files."""
        super().__init__(secrets_dir=secrets_dir, log=log, bot_name=bot_name)

        self.ldebug("Retrieving ACCESS_TOKEN ...")
        with open(path.join(self.secrets_dir, "ACCESS_TOKEN")) as f:
            ACCESS_TOKEN = f.read().strip()

        # Instance base url optional.
        self.ldebug("Looking for INSTANCE_BASE_URL ...")
        instance_base_url_path = path.join(self.secrets_dir, "INSTANCE_BASE_URL")
        if path.isfile(instance_base_url_path):
            with open(instance_base_url_path) as f:
                self.instance_base_url = f.read().strip()
        else:
            self.ldebug("Couldn't find INSTANCE_BASE_URL, defaulting to mastodon.social.")
            self.instance_base_url = "https://mastodon.social"

        self.api = mastodon.Mastodon(access_token=ACCESS_TOKEN,
                                     api_base_url=self.instance_base_url)
        self.html_re = re.compile("<.*?>")

    def send(
            self,
            *,
            text: str,
    ) -> List[OutputRecord]:
        """
        Send mastodon message.

        :param text: text to send in post.
        :returns: list of output records,
            each corresponding to either a single post,
            or an error.
        """
        try:
            status = self.api.status_post(status=text)

            return [TootRecord(record_data={
                "toot_id": status["id"],
                "text": text
            })]

        except mastodon.MastodonError as e:
            return [self.handle_error((f"Bot {self.bot_name} encountered an error when "
                                      f"sending post {text} without media:\n{e}\n"),
                                     e)]

    def send_with_media(
            self,
            *,
            text: str,
            files: List[str],
            captions: List[str]=[],
    ) -> List[OutputRecord]:
        """
        Upload media to mastodon,
        and send status and media,
        and captions if present.

        :param text: post text.
        :param files: list of files to upload with post.
        :param captions: list of captions to include as alt-text with files.
        :returns: list of output records,
            each corresponding to either a single post,
            or an error.
        """
        try:
            self.ldebug(f"Uploading files {files}.")
            if captions is None:
                captions = []

            if len(files) > len(captions):
                captions.extend([self.default_caption_message] * (len(files) - len(captions)))

            media_dicts = []
            for i, file in enumerate(files):
                caption = captions[i]
                media_dicts.append(self.api.media_post(file, description=caption))

            self.ldebug(f"Media ids {media_dicts}")

        except mastodon.MastodonError as e:
            return [self.handle_error(
                f"Bot {self.bot_name} encountered an error when uploading {files}:\n{e}\n", e
            )]

        try:
            status = self.api.status_post(status=text, media_ids=media_dicts)
            return [TootRecord(record_data={
                "toot_id": status["id"],
                "text": text,
                "media_ids": media_dicts,
                "captions": captions
            })]

        except mastodon.MastodonError as e:
            return [self.handle_error((f"Bot {self.bot_name} encountered an error when "
                                      f"sending post {text} with media dicts {media_dicts}:"
                                      f"\n{e}\n"),
                                     e)]

    def perform_batch_reply(
            self,
            *,
            callback: Callable[..., str],
            lookback_limit: int,
            target_handle: str,
    ) -> List[OutputRecord]:
        """
        Performs batch reply on target account.
        Looks up the recent messages of the target user,
        applies the callback,
        and replies with
        what the callback generates.

        :param callback: a callback taking a message id,
            message contents,
            and optional extra keys,
            and returning a message string.
        :param target: the id of the target account.
        :param lookback_limit: a lookback limit of how many messages to consider.
        :returns: list of output records,
            each corresponding to either a single post,
            or an error.
        """
        self.log.info(f"Attempting to batch reply to mastodon user {target_handle}")

        # target handle should be able to be provided either as @user or @user@domain
        # note that this produces an empty first chunk
        handle_chunks = target_handle.split("@")
        target_base_handle = handle_chunks[1]

        records: List[OutputRecord] = []
        our_id = self.api.account_verify_credentials()["id"]

        # be careful here - we're using a search to do this,
        # and if we're not careful we'll pull up people just mentioning the target.
        possible_accounts = self.api.account_search(target_handle, following=True)
        their_id = None
        for account in possible_accounts:
            if account["username"] == target_base_handle:
                their_id = account["id"]
                break

        if their_id is None:
            return [self.handle_error(f"Could not find target handle {target_handle}!", None)]

        statuses = self.api.account_statuses(their_id, limit=lookback_limit)
        for status in statuses:

            status_id = status.id

            # find possible replies we've made.
            our_statuses = self.api.account_statuses(our_id, since_id=status_id)
            in_reply_to_ids = list(map(lambda x: x.in_reply_to_id, our_statuses))
            if status_id not in in_reply_to_ids:

                encoded_status_text = re.sub(self.html_re, "", status.content)
                status_text = html.unescape(encoded_status_text)

                message = callback(message_id=status_id, message=status_text, extra_keys={})
                self.log.info(f"Replying {message} to status {status_id} from {target_handle}.")
                try:
                    new_status = self.api.status_post(status=message, in_reply_to_id=status_id)

                    records.append(TootRecord(record_data={
                        "toot_id": new_status.id,
                        "in_reply_to": target_handle,
                        "in_reply_to_id": status_id,
                        "text": message,
                    }))

                except mastodon.MastodonError as e:
                    records.append(
                        self.handle_error((f"Bot {self.bot_name} encountered an error when "
                                           f"sending post {message} during a batch reply "
                                           f":\n{e}\n"),
                                          e))
            else:
                self.log.info(f"Not replying to status {status_id} from {target_handle} "
                              f"- we already replied.")

        return records

    # TODO find a replacement/find out how mastodon DMs work.
    # def send_dm_sos(self, message):
    #     """Send DM to owner if something happens."""

    def handle_error(self, message: str, e: mastodon.MastodonError) -> OutputRecord:
        """Handle error while trying to do something."""
        self.lerror(f"Got an error! {e}")

        # Handle errors if we know how.
        try:
            code = e[0]["code"]
            if code in self.handled_errors:
                self.handled_errors[code]
            else:
                pass

        except Exception:
            pass

        return TootRecord(error=e)


class TootRecord(OutputRecord):
    def __init__(
            self,
            *,
            record_data: Dict[str, Any]={},
            error: mastodon.MastodonError = None,
    ) -> None:
        """
        Create toot record object.

        :param record_data: data to use to generate a TootRecord.
        :param error: error encountered while posting,
            to generate a record with.
        """
        super().__init__()
        self._type = self.__class__.__name__
        self.toot_id = record_data.get("toot_id", "")
        self.id = self.toot_id
        self.text = record_data.get("text", "")
        self.files = record_data.get("files", [])
        self.media_ids = record_data.get("media_ids", [])
        self.captions = record_data.get("captions", [])
        self.in_reply_to = record_data.get("in_reply_to", None)
        self.in_reply_to_id = record_data.get("in_reply_to_id", None)

        if error is not None:
            # So Python doesn't get upset when we try to json-dump the record later.
            self.error = json.dumps(error.__dict__)
            try:
                if isinstance(error.message, str):
                    self.error_message = error.message
                elif isinstance(error.message, list):
                    self.error_code = error.message[0]["code"]
                    self.error_message = error.message[0]["message"]
            except AttributeError:
                # fine, I didn't want it anyways.
                pass
