from pathlib import Path

from pydantic import TypeAdapter

from backend.app.schemas import Character


class CharacterDictionary:
    def __init__(self, characters: list[Character]) -> None:
        all_ids = [character.character_id for character in characters]
        if len(set(all_ids)) != len(all_ids):
            raise ValueError("Dictionary contains duplicate character IDs")
        self._published = {
            character.character_id: character
            for character in characters
            if character.status == "published"
        }

    @classmethod
    def from_path(cls, path: Path) -> "CharacterDictionary":
        characters = TypeAdapter(list[Character]).validate_json(path.read_text(encoding="utf-8"))
        return cls(characters)

    def get(self, character_id: str) -> Character | None:
        return self._published.get(character_id)

    def published(self) -> tuple[Character, ...]:
        return tuple(self._published.values())
