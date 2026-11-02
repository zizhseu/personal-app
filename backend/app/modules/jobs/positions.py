"""按与详情页相同的岗位快照及明确关联，定位一个岗位分组的记录。"""
from dataclasses import dataclass, field

from .models import Application, InterviewRound, RoundResultHistory, StatusHistory


def recorded_position(value: str | None) -> str | None:
    return value.strip() or None if value else None


@dataclass
class PositionRecords:
    rounds: list[InterviewRound] = field(default_factory=list)
    stages: list[StatusHistory] = field(default_factory=list)
    results: list[RoundResultHistory] = field(default_factory=list)


def position_groups(row: Application) -> dict[tuple[int, str | None], PositionRecords]:
    groups: dict[tuple[int, str | None], PositionRecords] = {}

    def ensure(version, position):
        return groups.setdefault((version, recorded_position(position)), PositionRecords())

    def compatible(left, right):
        return left.position_version == right.position_version and (
            not recorded_position(left.position) or not recorded_position(right.position)
            or recorded_position(left.position) == recorded_position(right.position))

    if row.has_current_position:
        ensure(row.position_version, row.position)
    stages = {stage.id: stage for stage in row.status_history}
    rounds = {item.id: item for item in row.rounds}
    round_positions = {}
    for stage in row.status_history:
        ensure(stage.position_version, stage.position).stages.append(stage)
    for item in row.rounds:
        stage = stages.get(item.status_history_id)
        position = recorded_position(item.position)
        if position is None and stage and compatible(item, stage):
            position = recorded_position(stage.position)
        ensure(item.position_version, position).rounds.append(item)
        round_positions[item.id] = position
    for result in row.round_result_history:
        position = recorded_position(result.position)
        item, stage = rounds.get(result.round_id), stages.get(result.status_history_id)
        if position is None and item and compatible(result, item):
            position = round_positions.get(item.id)
        if position is None and stage and compatible(result, stage):
            position = recorded_position(stage.position)
        ensure(result.position_version, position).results.append(result)
    return groups
