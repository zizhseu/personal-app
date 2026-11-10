"""将明确的招聘事件原子应用到指定岗位，保留来源与变更记录。"""
from datetime import datetime
import hashlib
import json
import re

from fastapi import HTTPException
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session

from app.modules.jobs import service as jobs
from app.modules.jobs.constants import ROUND_TYPE_STATUS, STATUS_FLOW
from app.modules.jobs.models import Application
from app.modules.jobs.positions import position_groups, position_summaries
from app.modules.jobs.schemas import PositionStatusPatch, RoundCreate, RoundUpdate

from .analysis import time_is_grounded
from .imap_client import normalized
from .models import MailAccount, MailMessage, change_summary
from .schemas import MailProposal


class ReviewRequired(Exception):
    """候选事件需要人工核对，不执行部分更新。"""


COMPANY_SEARCH_LIMIT = 20


def search_companies(db: Session, keyword: str) -> dict:
    """按单个关键词查询有界候选，通配符按普通文字处理。"""
    keyword = keyword.strip()
    if not keyword or len(keyword) > 40:
        raise HTTPException(400, "公司检索关键词需为 1 至 40 个字符")
    statement = (select(Application.company).distinct()
        .where(func.lower(Application.company).contains(keyword.lower(), autoescape=True))
        .order_by(case((func.lower(Application.company) == keyword.lower(), 0), else_=1),
                  func.length(Application.company), Application.company)
        .limit(COMPANY_SEARCH_LIMIT + 1))
    companies = list(db.scalars(statement))
    return {"keyword": keyword, "companies": companies[:COMPANY_SEARCH_LIMIT],
            "hasMore": len(companies) > COMPANY_SEARCH_LIMIT}


def target_snapshot(application, summary):
    group = position_groups(application)[(summary["positionVersion"], summary["position"])]
    payload = {"version": application.position_version, "status": summary["status"],
               "rounds": [item.to_dict() for item in sorted(group.rounds, key=lambda item: item.id)],
               "stages": [item.to_dict() for item in sorted(group.stages, key=lambda item: item.id)],
               "results": [item.to_dict() for item in sorted(group.results, key=lambda item: item.id)]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def company_snapshot(application):
    payload = {"application": application.to_dict(), "sequence": application.position_version_counter}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def company_targets(db: Session) -> list[dict]:
    return [{"applicationId": row.id, "company": row.company, "currentPosition": row.position,
             "expectedUpdatedAt": row.updated_at.isoformat(), "expectedPositionVersion": row.position_version,
             "expectedCompanySnapshot": company_snapshot(row)} for row in jobs.list_applications(db)]


def company_position_context(db: Session, companies: list[str]) -> list[dict]:
    ids = list(db.scalars(select(Application.id).where(Application.company.in_(companies))))
    positions = {company: [] for company in companies}
    for app_id in ids:
        row = jobs.get_application(db, app_id)
        positions[row.company].extend(item["position"] for item in position_summaries(row) if item["position"])
    return [{"company": company, "positions": list(dict.fromkeys(names))[:10],
             "hasMore": len(set(names)) > 10} for company, names in positions.items()]


def targets(db: Session) -> list[dict]:
    result = []
    for application in jobs.list_applications(db):
        for item in position_summaries(application):
            result.append({
                "applicationId": application.id, "company": application.company,
                "position": item["position"], "positionVersion": item["positionVersion"],
                "displayOrder": item["displayOrder"],
                "status": item["status"], "expectedUpdatedAt": application.updated_at.isoformat(),
                "expectedSnapshot": target_snapshot(application, item),
                "rounds": [r.to_dict() for r in application.rounds if r.id in item["roundIds"]],
            })
    return result


def matching_targets(db: Session, proposal: MailProposal) -> list[dict]:
    if not proposal.company:
        return []
    choices = targets(db)
    company = proposal.company
    exact = any(normalized(item["company"]) == normalized(company) for item in choices)
    if exact and proposal.matched_company and normalized(proposal.matched_company) != normalized(company):
        return []
    if not exact:
        if (not proposal.matched_company or proposal.company_match_type not in ("alias", "unit")
                or not (proposal.company_match_reason or "").strip()):
            return []
        if proposal.company_match_type == "unit":
            # 只有现有岗位已使用机构标签、邮件单位也明确隶属该公司时采用这种归属。
            same_company = [item for item in choices if normalized(item["company"]) == normalized(proposal.matched_company)]
            if (not normalized(proposal.company).startswith(normalized(proposal.matched_company))
                    or not re.search(r"分行|省分|支行|中心|分公司", proposal.company)
                    or not any(re.search(r"分行|省分|支行|中心|分公司", item["position"] or "") for item in same_company)
                    or re.search(r"子公司|控股|集团", proposal.company)):
                return []
        elif re.search(r"分行|支行|分公司|子公司|总行|控股|集团|研究院",
                       proposal.company + proposal.matched_company + proposal.evidence):
            return []
        company = proposal.matched_company
    position = proposal.target_position or proposal.position
    matched = [item for item in choices if normalized(item["company"]) == normalized(company)
               and (not position or normalized(item["position"] or "") == normalized(position))]
    if matched or proposal.position_action != "create" or not proposal.target_position:
        return matched
    if proposal.event_type not in ("invitation", "offer"):
        return []
    if any(normalized(item["company"]) == normalized(company) and item["position"]
           and len(normalized(item["position"])) >= 4
           and (normalized(item["position"]) in normalized(proposal.target_position)
                or normalized(proposal.target_position) in normalized(item["position"])) for item in choices):
        return []
    return [{**item, "createPosition": True, "newPosition": proposal.target_position}
            for item in company_targets(db) if normalized(item["company"]) == normalized(company)]


def auto_review_reason(message: MailMessage, proposal: MailProposal) -> str | None:
    if proposal.category != "event":
        return "这封邮件没有可自动执行的招聘事件"
    reference = message.sent_at or message.received_at
    if not time_is_grounded(proposal.start_at, proposal.start_evidence, reference):
        return "开始时间需要核对原文"
    if not time_is_grounded(proposal.deadline_at, proposal.deadline_evidence, reference):
        return "截止时间需要核对原文"
    markers = {
        "assessment": r"测评|性格测试|能力测试|assessment", "written_test": r"笔试|机考|编程.{0,6}(测评|考试)|written.test",
        "ai": r"AI\s*面试|智能面试", "first": r"一面|初面|第一.{0,3}(轮|面试)",
        "second": r"二面|第二.{0,3}(轮|面试)", "third": r"三面|第三.{0,3}(轮|面试)",
        "hr": r"HR\s*面|人力.{0,3}面试", "final": r"终面|最终.{0,3}面试",
        "verbal_offer": r"口头.{0,8}(offer|录用)", "formal_offer": r"正式.{0,8}offer|录用通知|录用函|offer\s*letter",
        "tripartite": r"三方|就业协议", "screening": r"初筛|简历筛选",
    }
    marker = markers.get(proposal.round_type)
    if not marker or not re.search(marker, message.subject + "\n" + proposal.evidence, re.IGNORECASE):
        return "轮次类型缺少明确原文依据，请核对后选择岗位"
    if proposal.event_type in ("invitation", "reschedule"):
        times = [value for value in (proposal.start_at, proposal.deadline_at) if value]
        if not times:
            return "邀请中缺少可确认的具体时间，请核对是否为重复邀请"
        if max(times) < datetime.now():
            return "安排时间已经过去，可能是迟到或重复邮件"
    if proposal.event_type == "reschedule" and not re.search(r"改期|调整|变更|更改|重新安排", proposal.evidence):
        return "改期事件缺少明确的变更依据"
    if proposal.event_type == "result":
        negative = re.search(r"未通过|不通过|未能|遗憾|暂不|未获|不予录用|不符合", proposal.evidence)
        positive = re.search(r"通过|恭喜|入围|进入下一", proposal.evidence)
        if proposal.result == "passed" and (negative or not positive):
            return "通过结果与原文依据不够明确，请核对"
        if proposal.result == "failed" and not negative:
            return "未通过结果缺少明确原文依据，请核对"
        if proposal.result == "completed" and not re.search(r"已完成|完成了|已提交", proposal.evidence):
            return "完成结果缺少明确原文依据，请核对"
    return None


def _same_arrangement(round_row, proposal):
    checks = []
    if proposal.start_at:
        checks.append(round_row.start_at == proposal.start_at)
    if proposal.deadline_at:
        checks.append(round_row.scheduled_at == proposal.deadline_at)
    return bool(checks) and all(checks)


def apply_event(db: Session, message_id: int, target: dict, *, token: str | None = None,
                manual: bool = False, selected_round_id: int | None = None) -> MailMessage:
    message = db.get(MailMessage, message_id)
    if message is None:
        raise HTTPException(404, "邮件记录不存在")
    if message.status in ("applied", "unchanged"):
        return message
    expected_state = "review" if manual else "analyzing"
    if message.status != expected_state or (not manual and message.processing_token != token):
        raise HTTPException(409, "邮件处理状态已变化，请刷新后重试")
    now = datetime.now()
    account_filter = MailAccount.scan_token == token if token else or_(MailAccount.scan_token.is_(None), MailAccount.lease_until <= now)
    locked = db.execute(update(MailAccount).where(MailAccount.id == message.account_id, account_filter)
                        .values(updated_at=MailAccount.updated_at))
    if locked.rowcount != 1:
        raise HTTPException(409, "邮箱正在由其他任务处理，请稍后重试")
    proposal = MailProposal.model_validate(message.proposal)
    if proposal.category != "event" or proposal.event_type == "application_received":
        raise ReviewRequired("该邮件没有可提交的流程变化")
    if not manual:
        reason = auto_review_reason(message, proposal)
        if reason:
            raise ReviewRequired(reason)
    expected_updated_at = datetime.fromisoformat(target["expectedUpdatedAt"])
    locked = db.execute(update(Application).where(Application.id == target["applicationId"],
        Application.updated_at == expected_updated_at).values(updated_at=Application.updated_at))
    if locked.rowcount != 1:
        raise ReviewRequired("投递记录已被修改，请刷新岗位信息后核对")
    db.expire_all()
    application = jobs.get_application(db, target["applicationId"])
    created_position = None
    creating = bool(target.get("createPosition"))
    if creating:
        if company_snapshot(application) != target.get("expectedCompanySnapshot"):
            raise ReviewRequired("公司下的岗位记录已变化，请刷新后重新核对")
        if proposal.event_type not in ("invitation", "offer"):
            raise ReviewRequired("请先为结果或改期邮件选择已有岗位及轮次")
        stage = jobs.create_position(db, application.id, target["newPosition"],
                                     ROUND_TYPE_STATUS[proposal.round_type], commit=False)
        key = (stage.position_version, stage.position)
        created_position = {"positionVersion": key[0], "position": key[1]}
        db.expire_all()
        application = jobs.get_application(db, target["applicationId"])
    else:
        key = (target["positionVersion"], target["position"])
    group = position_groups(application).get(key)
    if group is None:
        raise ReviewRequired("该岗位已变更或删除")
    summary = next(item for item in position_summaries(application)
                   if (item["positionVersion"], item["position"]) == key)
    if not creating and target_snapshot(application, summary) != target.get("expectedSnapshot"):
        raise ReviewRequired("岗位状态或轮次已修改，请刷新岗位信息后核对")
    candidates = [item for item in group.rounds if item.round_type == proposal.round_type]
    if selected_round_id is not None:
        candidates = [item for item in candidates if item.id == selected_round_id]
        if not candidates:
            raise ReviewRequired("选择的轮次不属于该岗位或类型不符")
    matching = [item for item in candidates if _same_arrangement(item, proposal)]
    identified_round_id = None
    if proposal.event_type in ("result", "reschedule"):
        eligible = matching or candidates
        if len(eligible) != 1:
            raise ReviewRequired("无法唯一确定对应轮次，请选择已有轮次")
        identified_round_id = eligible[0].id
    event_key = hashlib.sha256(json.dumps([
        application.id, *key, identified_round_id, proposal.event_type, proposal.round_type, proposal.result,
        proposal.start_at.isoformat() if proposal.start_at else None,
        proposal.deadline_at.isoformat() if proposal.deadline_at else None,
    ], ensure_ascii=False).encode()).hexdigest()
    existing = db.scalar(select(MailMessage).where(MailMessage.account_id == message.account_id,
        MailMessage.event_key == event_key, MailMessage.status.in_(("applied", "unchanged")), MailMessage.id != message.id))
    if existing or (proposal.event_type == "invitation" and matching):
        message.status, message.reason = "duplicate", "已有相同招聘事件或相同时间的轮次，本次保留来源"
        message.duplicate_of = existing.id if existing else None
        message.application_id = application.id
        message.round_id = existing.round_id if existing else matching[0].id
        message.processing_token = None
        db.commit()
        return message
    if not manual and proposal.event_type in ("invitation", "offer") and candidates and not matching:
        raise ReviewRequired("该岗位已有同类轮次，请确认是重复邀请、改期还是新增轮次")
    round_row = None
    if proposal.event_type in ("result", "reschedule") or selected_round_id:
        eligible = matching or candidates
        if len(eligible) != 1:
            raise ReviewRequired("无法唯一确定对应轮次，请选择已有轮次")
        round_row = eligible[0]
        if not manual and message.sent_at and round_row.updated_at > message.sent_at:
            raise ReviewRequired("该轮次在邮件发送后已有修改，请核对后处理")
        if proposal.event_type == "reschedule" and round_row.result != "not_started":
            raise ReviewRequired("该轮次已有结果，请核对改期邮件")
        if (not manual and proposal.event_type == "result"
                and round_row.result in ("passed", "failed", "accepted", "rejected_offer")
                and round_row.result != proposal.result):
            raise ReviewRequired("该轮次已有明确结果，请核对冲突邮件")
    desired_status = ROUND_TYPE_STATUS[proposal.round_type]
    changing_stage = proposal.event_type in ("invitation", "offer")
    if not manual and changing_stage and summary["result"] in ("failed", "rejected_offer"):
        raise ReviewRequired("该岗位已有未通过或拒绝结果，请确认新邀请是否属于重新招聘")
    if changing_stage and desired_status != summary["status"]:
        if not manual and (summary["status"] not in STATUS_FLOW or
                STATUS_FLOW.index(desired_status) < STATUS_FLOW.index(summary["status"])):
            raise ReviewRequired("岗位已进入后续阶段，旧邀请需要人工核对")
    before = {"status": summary["status"], "round": round_row.to_dict() if round_row else None}
    if changing_stage and desired_status != summary["status"]:
        latest_stage = max(group.stages, key=lambda item: (item.changed_at, item.id), default=None)
        jobs.patch_position_status(db, application.id, PositionStatusPatch(
            position=key[1], position_version=key[0], expected_position_version=application.position_version,
            status=desired_status, expected_status=summary["status"],
            expected_status_history_id=latest_stage.id if latest_stage else None,
        ), commit=False, sync_round_results=False)
    duration = None
    effective_start = proposal.start_at or (round_row.start_at if round_row else None)
    if proposal.event_type != "result" and effective_start and proposal.deadline_at:
        if proposal.deadline_at < effective_start:
            raise ReviewRequired("新的截止时间早于已记录的开始时间，请核对原安排")
        duration = int((proposal.deadline_at - effective_start).total_seconds() / 60)
    if round_row:
        updates = {}
        if proposal.event_type == "result":
            updates["result"] = proposal.result
        elif proposal.event_type == "reschedule" or selected_round_id:
            if proposal.start_at:
                updates["start_at"] = proposal.start_at
            if duration is not None:
                updates["duration_minutes"] = duration
        round_row = jobs.update_round(db, round_row.id, RoundUpdate(**updates), commit=False)
    else:
        round_row = jobs.create_round(db, application.id, RoundCreate(
            position=key[1], position_version=key[0], expected_position_version=application.position_version,
            round_type=proposal.round_type, start_at=proposal.start_at, duration_minutes=duration,
            result=proposal.result or "not_started",
        ), commit=False)
    if proposal.deadline_at and proposal.event_type != "result":
        round_row.scheduled_at = proposal.deadline_at
    db.flush()
    after = {"status": desired_status if changing_stage else summary["status"], "round": round_row.to_dict()}
    fields = ("roundType", "startAt", "scheduledAt", "durationMinutes", "result", "reviewNote")
    changed = (bool(created_position) or before["round"] is None or before["status"] != after["status"]
               or any(before["round"].get(field) != after["round"].get(field) for field in fields))
    if changed:
        application.updated_at = datetime.now()
    message = db.get(MailMessage, message_id)
    message.status, message.event_key = "applied" if changed else "unchanged", event_key
    message.application_id, message.round_id = application.id, round_row.id
    message.processing_token = None
    message.changes = {"before": before, "after": after, "createdPosition": created_position}
    message.reason = change_summary(message.changes)
    db.commit()
    db.expire_all()
    return message
