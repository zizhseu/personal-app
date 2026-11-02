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


class PositionResolver:
    """缺失快照不是第二个岗位；同流程只有一个已知名称时，展示到该流程下。"""

    def __init__(self, row: Application):
        self.names: dict[int, set[str]] = {}
        self.stages = {item.id: item for item in row.status_history}
        self.rounds = {item.id: item for item in row.rounds}
        sources = [*row.status_history, *row.rounds, *row.round_result_history]
        for item in sources:
            name = recorded_position(item.position)
            if name:
                self.names.setdefault(item.position_version, set()).add(name)
        current = recorded_position(row.position)
        if row.has_current_position and current:
            self.names.setdefault(row.position_version, set()).add(current)

    def resolve(self, version, position, linked=None):
        name = recorded_position(position)
        if name is not None:
            return name
        if linked is not None:
            return linked
        names = self.names.get(version, set())
        return next(iter(names)) if len(names) == 1 else None

    @staticmethod
    def compatible(left, right):
        return left.position_version == right.position_version and (
            not recorded_position(left.position) or not recorded_position(right.position)
            or recorded_position(left.position) == recorded_position(right.position))

    def stage_position(self, stage):
        return self.resolve(stage.position_version, stage.position)

    def round_position(self, item):
        stage = self.stages.get(item.status_history_id)
        linked = self.stage_position(stage) if stage and self.compatible(item, stage) else None
        return self.resolve(item.position_version, item.position, linked)

    def result_position(self, result):
        item, stage = self.rounds.get(result.round_id), self.stages.get(result.status_history_id)
        linked = self.round_position(item) if item and self.compatible(result, item) else None
        if linked is None and stage and self.compatible(result, stage):
            linked = self.stage_position(stage)
        return self.resolve(result.position_version, result.position, linked)


def position_groups(row: Application) -> dict[tuple[int, str | None], PositionRecords]:
    groups: dict[tuple[int, str | None], PositionRecords] = {}

    def ensure(version, position):
        return groups.setdefault((version, recorded_position(position)), PositionRecords())

    resolver = PositionResolver(row)
    if row.has_current_position:
        ensure(row.position_version, row.position)
    for stage in row.status_history:
        ensure(stage.position_version, resolver.stage_position(stage)).stages.append(stage)
    for item in row.rounds:
        ensure(item.position_version, resolver.round_position(item)).rounds.append(item)
    for result in row.round_result_history:
        ensure(result.position_version, resolver.result_position(result)).results.append(result)
    return groups
