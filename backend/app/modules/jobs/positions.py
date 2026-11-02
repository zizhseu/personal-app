"""按与详情页相同的岗位快照及明确关联，定位一个岗位分组的记录。"""
from dataclasses import dataclass, field
from datetime import datetime

from .models import Application, InterviewRound, RoundResultHistory, StatusHistory
from .constants import ROUND_TYPE_STATUS


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


def position_summaries(row: Application) -> list[dict]:
    """岗位记录展示序号独立于内部代次，主要岗位只是汇总选择。"""
    groups = position_groups(row)
    current_key = (row.position_version, recorded_position(row.position)) if row.has_current_position else None
    preferred = (row.primary_position_version, recorded_position(row.primary_position))

    def order(entry):
        (version, position), group = entry
        times = [item.changed_at for item in group.stages] + [item.created_at for item in group.rounds] + [item.changed_at for item in group.results]
        return version, min((value for value in times if value is not None), default=datetime.max), position or ''

    ordered_groups = sorted(groups.items(), key=order)
    first_key = ordered_groups[0][0] if ordered_groups else None
    # 未选择时用最早的岗位；用户选择始终优先，不随当前岗位变化。
    primary_key = preferred if row.primary_position_version is not None and preferred in groups else first_key
    summaries = []
    for index, (key, group) in enumerate(ordered_groups, 1):
        is_current = key == current_key
        latest_round = max(group.rounds, key=lambda item: item.id, default=None)
        latest_stage = max(group.stages, key=lambda item: (item.changed_at, item.id), default=None)
        latest_result = max(group.results, key=lambda item: (item.changed_at, item.id), default=None)
        status = row.status if is_current else latest_stage.status if latest_stage else latest_result.status if latest_result else ROUND_TYPE_STATUS.get(latest_round.round_type) if latest_round else None
        decision = row.offer_decision if is_current else None
        if not is_current and status == 'offer':
            recorded = [item for item in group.results if item.to_result in ('accepted', 'rejected_offer')]
            if recorded:
                decision = max(recorded, key=lambda item: (item.changed_at, item.id)).to_result
        result = decision if status == 'offer' else latest_round.result if latest_round else None
        summaries.append({
            'position': key[1], 'positionVersion': key[0], 'displayOrder': index,
            'isCurrent': is_current, 'isPrimary': key == primary_key,
            'status': status, 'result': result, 'offerDecision': decision, 'latestRoundId': latest_round.id if latest_round else None,
            'roundIds': [item.id for item in group.rounds], 'statusHistoryIds': [item.id for item in group.stages],
            'resultHistoryIds': [item.id for item in group.results],
        })
    return summaries
