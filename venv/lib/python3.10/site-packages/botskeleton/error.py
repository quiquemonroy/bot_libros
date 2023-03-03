class BotSkeletonException(Exception):
    """
    Generic Exception for errors in this project

    Attributes:
        desc  -- short message describing error
    """
    def __init__(self, desc:str) -> None:
        super(BotSkeletonException, self).__init__()
        self.desc = desc
