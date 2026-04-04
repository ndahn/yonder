from yonder.hash import calc_hash, lookup_name


class ObjectId:
    def __init__(self, initial_value: int | str):
        self._hash = 0
        self._name = None
        self.set(initial_value)

    def to_dict(self) -> dict:
        if self._name:
            return {"String": self._name}
        return {"Hash": self._hash}

    @classmethod
    def from_dict(cls, data: dict) -> "ObjectId":
        if "String" in data:
            return cls(data["String"])
        return cls(data["Hash"])

    def validate(self) -> None:
        if self._name and calc_hash(self._name) != self._hash:
            raise ValueError(
                f"Object hash and name out of sync ({self._hash} vs. ({self._name}))"
            )

    def set(self, value: int | str) -> None:
        if isinstance(value, int):
            self._hash = value
            self._name = lookup_name(value, None)
        else:
            self._hash = calc_hash(value)
            self._name = value

    def value(self) -> int | str:
        return self._name if self._name else self._hash

    @property
    def hash(self) -> int:
        return self._hash

    @hash.setter
    def hash(self, value: int) -> None:
        self.set(value)

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self.set(value)

    def __hash__(self) -> int:
        return self._hash

    def __str__(self) -> str:
        return self._name if self._name else f"#{self._hash}"

    def __repr__(self) -> str:
        name = self._name or "<?>"
        return f"{name} (#{self._hash})"
