"""Skeleton code for sending to the bad bird site."""
import html
import json
from logging import Logger
from os import path
from typing import Any, Callable, Dict, List, Optional, Tuple

import tweepy

from .output_utils import OutputRecord, OutputSkeleton


class BirdsiteSkeleton(OutputSkeleton):
    def __init__(self) -> None:
        """Set up birdsite skeleton stuff."""
        self.name = "BIRDSITE"

        self.handled_errors = {
            187: self.default_duplicate_handler,
        }

    ## API implementation methods.
    def cred_init(
            self,
            *,
            secrets_dir: str,
            log: Logger,
            bot_name: str,
    ) -> None:
        """
        Initialize what requires credentials/secret files.

        :param secrets_dir: dir to expect credentials in and store logs/history in.
        :param log: logger to use for log output.
        :param bot_name: name of this bot,
            used for various kinds of labelling.
        :returns: none.
        """
        super().__init__(secrets_dir=secrets_dir, log=log, bot_name=bot_name)

        self.ldebug("Retrieving CONSUMER_KEY...")
        with open(path.join(self.secrets_dir, "CONSUMER_KEY")) as f:
            CONSUMER_KEY = f.read().strip()

        self.ldebug("Retrieving CONSUMER_SECRET...")
        with open(path.join(self.secrets_dir, "CONSUMER_SECRET")) as f:
            CONSUMER_SECRET = f.read().strip()

        self.ldebug("Retrieving ACCESS_TOKEN...")
        with open(path.join(self.secrets_dir, "ACCESS_TOKEN")) as f:
            ACCESS_TOKEN = f.read().strip()

        self.ldebug("Retrieving ACCESS_SECRET...")
        with open(path.join(self.secrets_dir, "ACCESS_SECRET")) as f:
            ACCESS_SECRET = f.read().strip()

        self.ldebug("Looking for OWNER_HANDLE...")
        owner_handle_path = path.join(self.secrets_dir, "OWNER_HANDLE")
        if path.isfile(owner_handle_path):
            with open(owner_handle_path) as f:
                self.owner_handle = f.read().strip()
        else:
            self.ldebug("Couldn't find OWNER_HANDLE, unable to DM...")
            self.owner_handle = ""

        self.auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        self.auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)

        self.api = tweepy.API(self.auth)

    def send(
            self,
            *,
            text: str,
    ) -> List[OutputRecord]:
        """
        Send birdsite message.

        :param text: text to send in post.
        :returns: list of output records,
            each corresponding to either a single post,
            or an error.
        """
        try:
            status = self.api.update_status(text)
            return [TweetRecord(record_data={"tweet_id": status._json["id"], "text": text})]

        except tweepy.TweepyException as e:
            return [self.handle_error(
                message=(f"Bot {self.bot_name} encountered an error when "
                 f"sending post {text} without media:\n{e}\n"),
                error=e)]

    def send_with_media(
            self,
            *,
            text: str,
            files: List[str],
            captions: List[str]=[]
    ) -> List[OutputRecord]:
        """
        Upload media to birdsite,
        and send status and media,
        and captions if present.

        :param text: tweet text.
        :param files: list of files to upload with post.
        :param captions: list of captions to include as alt-text with files.
        :returns: list of output records,
            each corresponding to either a single post,
            or an error.
        """

        # upload media
        media_ids = None
        try:
            self.ldebug(f"Uploading files {files}.")
            media_ids = [self.api.media_upload(file).media_id_string for file in files]
        except tweepy.TweepyException as e:
            return [self.handle_error(
                message=f"Bot {self.bot_name} encountered an error when uploading {files}:\n{e}\n",
                error=e)]

        # apply captions, if present
        self._handle_caption_upload(media_ids=media_ids, captions=captions)

        # send status
        try:
            status = self.api.update_status(status=text, media_ids=media_ids)
            return [TweetRecord(record_data={
                "tweet_id": status._json["id"],
                "text": text,
                "media_ids": media_ids,
                "captions": captions,
                "files": files
            })]

        except tweepy.TweepyException as e:
            return [self.handle_error(
                message=(f"Bot {self.bot_name} encountered an error when "
                 f"sending post {text} with media ids {media_ids}:\n{e}\n"),
                error=e)]

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
        self.log.info(f"Attempting to batch reply to birdsite user {target_handle}")

        if "@" in target_handle:
            base_target_handle = target_handle[1:]
        else:
            base_target_handle = target_handle

        records: List[OutputRecord] = []
        statuses = self.api.user_timeline(screen_name=base_target_handle, count=lookback_limit)
        self.log.debug(f"Retrieved {len(statuses)} statuses.")
        for i, status in enumerate(statuses):
            self.log.debug(f"Processing status {i} of {len(statuses)}")
            status_id = status.id

            # find possible replies we've made.
            # the 10 * lookback_limit is a guess,
            # might not be enough and I'm not sure we can guarantee it is.
            our_statuses = self.api.user_timeline(since_id=status_id,
                                                  count=lookback_limit * 10)
            in_reply_to_ids = list(map(lambda x: x.in_reply_to_status_id, our_statuses))

            if status_id not in in_reply_to_ids:
                # the twitter API and tweepy will attempt to give us the truncated text of the
                # message if we don't do this roundabout thing.
                encoded_status_text = self.api.get_status(status_id,
                                                  tweet_mode="extended")._json["full_text"]

                status_text = html.unescape(encoded_status_text)
                message = callback(message_id=status_id, message=status_text, extra_keys={})

                full_message = f"@{base_target_handle} {message}"
                self.log.info(f"Trying to reply with {message} to status {status_id} "
                              f"from {target_handle}.")
                try:
                    new_status = self.api.update_status(status=full_message,
                                                        in_reply_to_status_id=status_id)

                    records.append(TweetRecord(record_data={
                        "tweet_id": new_status.id,
                        "in_reply_to": f"@{base_target_handle}",
                        "in_reply_to_id": status_id,
                        "text": full_message,
                    }))

                except tweepy.TweepyException as e:
                    records.append(self.handle_error(
                        message=(f"Bot {self.bot_name} encountered an error when "
                         f"trying to reply to {status_id} with {message}:\n{e}\n"),
                        error=e))
            else:
                self.log.info(f"Not replying to status {status_id} from {target_handle} "
                              f"- we already replied.")

        return records

    ## Helpful methods for this output.
    def send_dm_sos(self, message: str) -> None:
        """
        Send DM to owner if something happens.

        :param message: message to send to owner.
        :returns: None.
        """
        if self.owner_handle:
            try:
                # twitter changed the DM API and tweepy (as of 2019-03-08)
                # has not adapted.
                # fixing with
                # https://github.com/tweepy/tweepy/issues/1081#issuecomment-423486837
                owner_id = self.api.get_user(screen_name=self.owner_handle).id
                event = {
                    "event": {
                        "type": "message_create",
                        "message_create": {
                            "target": {
                                "recipient_id": f"{owner_id}",
                            },
                            "message_data": {
                                "text": message
                            }
                        }
                    }
                }

                self._send_direct_message_new(event)

            except tweepy.TweepyException as de:
                self.lerror(f"Error trying to send DM about error!: {de}")

        else:
            self.lerror("Can't send DM SOS, no owner handle.")

    def handle_error(
            self,
            *,
            message: str,
            error: tweepy.TweepyException,
    ) -> OutputRecord:
        """
        Handle error while trying to do something.

        :param message: message to send in DM regarding error.
        :param e: tweepy error object.
        :returns: OutputRecord containing an error.
        """
        self.lerror(f"Got an error! {error}")

        # Handle errors if we know how.
        try:
            code = error[0]["code"]
            if code in self.handled_errors:
                self.handled_errors[code]
            else:
                self.send_dm_sos(message)

        except Exception:
            self.send_dm_sos(message)

        return TweetRecord(error=error)

    def default_duplicate_handler(self) -> None:
        """Default handler for duplicate status error."""
        self.linfo("Duplicate handler: who cares about duplicate statuses.")
        return

    def set_duplicate_handler(self, duplicate_handler: Callable[..., None]) -> None:
        self.handled_errors[187] = duplicate_handler

    def _handle_caption_upload(
            self,
            *,
            media_ids: List[str],
            captions: Optional[List[str]],
    ) -> None:
        """
        Handle uploading all captions.

        :param media_ids: media ids of uploads to attach captions to.
        :param captions: captions to be attached to those media ids.
        :returns: None.
        """
        if captions is None:
            captions = []

        if len(media_ids) > len(captions):
            captions.extend([self.default_caption_message] * (len(media_ids) - len(captions)))

        for i, media_id in enumerate(media_ids):
            caption = captions[i]
            self._upload_caption(media_id=media_id, caption=caption)

    # taken from https://github.com/tweepy/tweepy/issues/716#issuecomment-398844271
    def _upload_caption(self, *, media_id: str, caption: str) -> Any:
        post_data = {
            "media_id": media_id,
            "alt_text": {
                "text": caption,
            },
        }

        metadata_path = "/media/metadata/create.json"

        return tweepy.binder.bind_api(
            api=self.api,
            path=metadata_path,
            method="POST",
            allowed_param=[],
            require_auth=True,
            upload_api=True,
        )(post_data=json.dumps(post_data))

    # taken from
    # https://github.com/do-n-khanh/tweepy/commit/79772c976c64830149095f087c16c181912466ba#diff-ea5dd38a4efd9ff36c96e04ab0597cfb
    def _send_direct_message_new(self, messageobject: Dict[str, Dict]) -> Any:
        """
        :reference: https://developer.twitter.com/en/docs/direct-messages/sending-and-receiving/api-reference/new-event.html
        """
        headers, post_data = _buildmessageobject(messageobject)
        newdm_path = "/direct_messages/events/new.json"

        return tweepy.binder.bind_api(
            api=self.api,
            path=newdm_path,
            method="POST",
            require_auth=True,
        )(post_data=post_data, headers=headers)

# taken from
# https://github.com/do-n-khanh/tweepy/commit/79772c976c64830149095f087c16c181912466ba#diff-ea5dd38a4efd9ff36c96e04ab0597cfb
def _buildmessageobject(messageobject: Dict[str, Dict]) -> Tuple[Dict[str, str], str]:
    body = json.dumps(messageobject)
    # build headers
    headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(body))
    }

    return headers, body

class TweetRecord(OutputRecord):
    def __init__(
            self,
            *,
            record_data: Dict[str, Any]={},
            error: tweepy.TweepyException=None,
    ) -> None:
        """
        Create tweet record object.

        :param record_data: data to use to generate a TweetRecord.
        :param error: error encountered while posting,
            to generate a record with.
        """
        super().__init__()
        self._type = self.__class__.__name__
        self.tweet_id = record_data.get("tweet_id", None)
        self.id = self.tweet_id
        self.text = record_data.get("text", None)
        self.files = record_data.get("files", [])
        self.media_ids = record_data.get("media_ids", [])
        self.captions = record_data.get("captions", [])
        self.timestamp = record_data.get("timestamp", None)
        self.in_reply_to = record_data.get("in_reply_to", None)
        self.in_reply_to_id = record_data.get("in_reply_to_id", None)

        if error is not None:
            # So Python doesn't get upset when we try to json-dump the record later.
            try:
                self.error = json.dumps(error.__dict__)
            except TypeError:
                # fuck you
                self.error = str(error)

            try:
                if isinstance(error.message, str):
                    self.error_message = error.message
                elif isinstance(error.message, list):
                    self.error_code = error.message[0]["code"]
                    self.error_message = error.message[0]["message"]
            except AttributeError:
                # fine, I didn't want it anyways.
                pass
