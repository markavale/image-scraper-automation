from pydantic import BaseModel
from typing import Optional, Union

class EventDTO(BaseModel):
    term: Optional[str] = None
    event_id: Optional[Union[str, int]] = None
    score: Optional[Union[float, int]] = None
    link: Optional[str] = None
    date: Optional[str] = None

    @classmethod
    def from_event(cls, event: dict) -> "EventDTO":
        data = event.get('data', {})
        return cls(
            term=event.get('term'),
            event_id=event.get('id'),
            score=event.get('score'),
            link=data.get('link'),
            date=data.get('date'))