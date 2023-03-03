"""Stuff used by output classes."""
from datetime import datetime
from logging import Logger
from typing import Any, Callable, Dict, List

class OutputSkeleton:
    """Common stuff for output skeletons."""
    def __init__(
            self,
            *,
            secrets_dir: str,
            log: Logger,
            bot_name: str,
    ) -> None:
        self.log = log
        self.secrets_dir = secrets_dir

        self.bot_name = bot_name
        self.handled_errors: Dict[int, Any] = {}

        self.default_caption_message = "No caption provided for image."

        # Output skeletons must implement these.
        # mypy doesn't let us express a function taking only keyword arguments,
        # as best I can tell.
        self.cred_init: Callable[..., None]
        self.send: Callable[..., List[OutputRecord]]
        self.send_with_media: Callable[..., List[OutputRecord]]
        self.perform_batch_reply: Callable[..., List[OutputRecord]]

    def linfo(self, message: str) -> None:
        """Wrapped debug log with prefix key."""
        self.log.info(f"{self.bot_name}: {message}")

    def ldebug(self, message: str) -> None:
        """Wrapped debug log with prefix key."""
        self.log.debug(f"{self.bot_name}: {message}")

    def lerror(self, message: str) -> None:
        """Wrapped error log with prefix key."""
        self.log.error(f"{self.bot_name}: {message}")

class OutputRecord:
    """Record for an output occurrence."""
    def __init__(self) -> None:
        """Create tweet record object."""
        self._type = self.__class__.__name__
        self.timestamp = datetime.now().isoformat()

    def __str__(self) -> str:
        """Print object."""
        return str(self.__dict__)

    def __repr__(self) -> str:
        """repr object"""
        return str(self)

    def __eq__(self, other:Any) -> bool:
        """Overrides the default implementation"""
        if isinstance(other, OutputRecord):
            for key, value in self.__dict__.items():
                if value != other.__dict__[key]:
                    return False

                return True
        return False

    @classmethod
    def from_dict(cls, obj_dict: Dict[str, Any]) -> "OutputRecord":
        """Get object back from dict."""
        obj = cls()
        for key, item in obj_dict.items():
            obj.__dict__[key] = item

        return obj
