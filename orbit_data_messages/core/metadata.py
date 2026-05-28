class Delineation:

    def __init__(
        self,
        start: str,
        stop: str,
    ):
        self.start = start
        self.stop = stop

    def __str__(self) -> str:
        return f"{self.start} / {self.stop}"


class FieldMetadata:

    def __init__(
        self,
        keyword: str,
        units: str | None = None,
    ):
        self.keyword = keyword
        self.units = units

    def __str__(self) -> str:
        return f"{self.keyword}{f' [{self.units}]' if self.units else ''}"
