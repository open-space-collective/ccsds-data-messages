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
        delineation: Delineation | None = None,
    ):
        self.keyword = keyword
        self.units = units
        self.delineation = delineation

    @property
    def delineation_str(self) -> str:
        return f"{self.delineation.start} / {self.delineation.stop}" if self.delineation else ""

    def __str__(self) -> str:
        return f"{self.keyword}{f' [{self.units}]' if self.units else ''}{f' ({self.delineation_str})' if self.delineation else ''}"
