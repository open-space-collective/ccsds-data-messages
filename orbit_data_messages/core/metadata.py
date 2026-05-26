class Metadata:

    def __init__(
        self,
        keyword: str,
        units: str | None = None,
    ):
        self.keyword = keyword
        self.units = units

    def __str__(self) -> str:
        return f"{self.keyword}{f' [{self.units}]' if self.units else ''}"
