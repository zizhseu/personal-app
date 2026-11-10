"""邮箱基线、重复邀请、岗位隔离与原子更新回归。"""
import asyncio
from datetime import datetime, timedelta
from email.message import EmailMessage
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI, HTTPException
import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app  # 注册全部模型。
from app.core.database import get_db
from app.modules.jobs import service as jobs
from app.modules.jobs.models import Application, InterviewRound
from app.modules.jobs.schemas import ApplicationCreate, ApplicationUpdate, ApplicationStatusPatch, PositionDeleteInput, RoundCreate, RoundUpdate
from app.modules.jobs.positions import position_summaries
from app.modules.mailbox import analysis, execution, imap_client, service, router
from app.modules.mailbox.models import MailAccount, MailMessage, change_summary
from app.modules.mailbox.schemas import MailProposal, MailSettings
from app.shared.base import Base


class MailboxTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.db = self.factory()
        self.future = (datetime.now() + timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0)
        self.time_quote = self.future.strftime("%Y年%m月%d日 %H:%M")
        self.body = f"测试银行邀请您参加研发工程师一面，开始时间为{self.time_quote}。"
        self.application = jobs.create_application(self.db, ApplicationCreate(company="测试银行", position="研发工程师"))
        self.account = MailAccount(address="mailbox-test@163.com", uid_validity="7", last_uid=10,
                                   next_scan_at=datetime.now() + timedelta(hours=1))
        self.db.add(self.account)
        self.db.commit()
        self.token = service.claim_scan(self.db, self.account.id)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def proposal(self, **updates):
        result = {
            "category": "event", "eventType": "invitation", "company": "测试银行", "position": "研发工程师",
            "companySearchKeywords": ["测试银行"],
            "roundType": "first", "result": None, "startAt": self.future.isoformat(), "deadlineAt": None,
            "startEvidence": self.time_quote, "deadlineEvidence": None, "evidence": self.body, "reason": "具体的一面邀请",
        }
        return {**result, **updates}

    def message(self, *, body=None, subject="测试银行一面邀请", uid=11):
        raw = EmailMessage()
        raw["From"] = "hr@example.invalid"
        raw["Subject"] = subject
        raw.set_content(body or self.body)
        payload = imap_client.parse_mail(raw.as_bytes(), uid, datetime.now())
        row = MailMessage(account_id=self.account.id, uid_validity="7", **payload)
        self.db.add(row)
        self.db.commit()
        return row

    def replies(self, proposal=None):
        data = proposal or self.proposal()
        company = data.get("matchedCompany", data.get("company"))
        reason = data.get("companyMatchReason", "与候选中的原名相同")
        match = {"matchedCompany": company,
                 "companyMatchType": data.get("companyMatchType", "exact" if company else "uncertain"),
                 "companyMatchReason": "无法确定对应公司" if reason is None else reason}
        match.update({key: data[key] for key in ("targetPosition", "positionAction", "positionMatchReason") if key in data})
        return [json.dumps(data, ensure_ascii=False), json.dumps(match, ensure_ascii=False)]

    def process(self, row, proposal=None):
        with patch.object(analysis.model_service, "llm_chat", new=AsyncMock(side_effect=self.replies(proposal))):
            asyncio.run(service.analyze_message(self.db, row.id, self.token))
        self.db.expire_all()
        return self.db.get(MailMessage, row.id)

    def test_invitation_updates_position_and_does_not_infer_prior_result(self):
        row = self.process(self.message())
        self.assertEqual(row.status, "applied")
        application = jobs.get_application(self.db, self.application.id)
        self.assertEqual(application.status, "interviewing")
        self.assertEqual(next(r for r in application.rounds if r.round_type == "screening").result, "not_started")
        self.assertEqual(next(r for r in application.rounds if r.round_type == "first").start_at, self.future)
        self.assertIn("before", row.changes)

    def test_reworded_same_arrangement_does_not_add_second_round(self):
        self.process(self.message())
        body = self.body + "请及时确认。"
        row = self.process(self.message(body=body, uid=12), self.proposal(evidence=body))
        self.assertEqual(row.status, "duplicate")
        self.assertEqual(len(list(self.db.scalars(select(InterviewRound).where(InterviewRound.round_type == "first")))), 1)

    def test_repeated_reminder_is_ignored(self):
        row = self.process(self.message(), self.proposal(category="reminder", reason="同一测评的催办"))
        self.assertEqual(row.status, "ignored")
        self.assertEqual(jobs.get_application(self.db, self.application.id).status, "screening")

    def test_general_apply_invitation_skips_model(self):
        row = self.message(subject="测试银行岗位投递邀请")
        with patch.object(analysis.model_service, "llm_chat", new=AsyncMock()) as model:
            asyncio.run(service.analyze_message(self.db, row.id, self.token))
        model.assert_not_awaited()
        self.assertEqual(row.status, "ignored")

    def test_same_company_multiple_position_periods_require_review(self):
        jobs.update_application(self.db, self.application.id, ApplicationUpdate(position="研发工程师", restart_process=True))
        row = self.process(self.message())
        self.assertEqual(row.status, "review")
        self.assertEqual(jobs.get_application(self.db, self.application.id).status, "screening")

    def test_invitation_without_time_requires_review(self):
        row = self.process(self.message(), self.proposal(startAt=None, startEvidence=None))
        self.assertEqual(row.status, "review")

    def test_hallucinated_time_requires_review(self):
        row = self.process(self.message(), self.proposal(startAt=(self.future + timedelta(hours=1)).isoformat()))
        self.assertEqual(row.status, "review")

    def test_fabricated_source_is_rejected(self):
        row = self.process(self.message(), self.proposal(company="另一家银行"))
        self.assertEqual(row.status, "failed")

    def postal_message(self, source_company="中国邮政储蓄银行"):
        self.application.company = "中国邮储银行"
        self.db.commit()
        body = f"{source_company}邀请您参加研发工程师一面，开始时间为{self.time_quote}。"
        row = self.message(body=body, subject=f"{source_company}一面邀请")
        proposal = self.proposal(company=source_company, matchedCompany="中国邮储银行", companyMatchType="alias",
                                 companySearchKeywords=["邮储", "银行", "邮政"],
                                 companyMatchReason="邮政储蓄银行全称与候选名单中的简称对应", evidence=body)
        return row, proposal

    def test_fixed_two_requests_have_independent_contexts(self):
        row = self.message()
        with patch.object(analysis.model_service, "llm_chat", new=AsyncMock(side_effect=self.replies())) as model:
            asyncio.run(service.analyze_message(self.db, row.id, self.token))
        self.assertEqual(model.await_count, 2)
        first, second = [call.args[0] for call in model.call_args_list]
        self.assertEqual([message["role"] for message in first], ["system", "user"])
        self.assertEqual([message["role"] for message in second], ["system", "user"])
        self.assertNotIn("existingCompanies", json.loads(first[1]["content"]))
        self.assertNotIn("candidateCompanies", json.loads(first[1]["content"]))
        payload = json.loads(second[1]["content"])
        self.assertEqual(payload["candidateCompanies"], ["测试银行"])
        self.assertNotIn("body", payload)

    def test_postal_bank_alias_matches_existing_company_and_keeps_original(self):
        row, proposal = self.postal_message()
        row = self.process(row, proposal)
        self.assertEqual(row.status, "applied")
        self.assertEqual(row.application_id, self.application.id)
        self.assertEqual(row.proposal["company"], "中国邮政储蓄银行")
        self.assertEqual(row.proposal["matchedCompany"], "中国邮储银行")
        self.assertEqual(jobs.get_application(self.db, self.application.id).company, "中国邮储银行")

    def test_model_cannot_select_company_outside_candidate_list(self):
        row, proposal = self.postal_message()
        row = self.process(row, {**proposal, "matchedCompany": "名单中不存在的公司"})
        self.assertEqual(row.status, "failed")
        self.assertEqual(jobs.get_application(self.db, self.application.id).status, "screening")

    def test_alias_without_reason_is_rejected(self):
        row, proposal = self.postal_message()
        row = self.process(row, {**proposal, "companyMatchReason": ""})
        self.assertEqual(row.status, "failed")

    def test_alias_cannot_be_claimed_as_exact_string_match(self):
        row, proposal = self.postal_message()
        row = self.process(row, {**proposal, "companyMatchType": "exact"})
        self.assertEqual(row.status, "failed")

    def test_company_alias_does_not_bypass_multiple_position_periods(self):
        row, proposal = self.postal_message()
        jobs.update_application(self.db, self.application.id, ApplicationUpdate(position="研发工程师", restart_process=True))
        row = self.process(row, proposal)
        self.assertEqual(row.status, "review")
        self.assertEqual(jobs.get_application(self.db, self.application.id).status, "screening")

    def test_branch_name_is_not_automatically_merged_with_parent_bank(self):
        row, proposal = self.postal_message("中国邮政储蓄银行上海分行")
        row = self.process(row, proposal)
        self.assertEqual(row.status, "review")

    def test_model_alias_cannot_override_existing_exact_company(self):
        jobs.create_application(self.db, ApplicationCreate(company="另一家银行", position="研发工程师"))
        row = self.process(self.message(), self.proposal(matchedCompany="另一家银行", companyMatchType="alias",
                                                        companyMatchReason="模拟错误的别名判断"))
        self.assertEqual(row.status, "failed")
        self.assertEqual(jobs.get_application(self.db, self.application.id).status, "screening")

    def test_unknown_alias_without_model_match_requires_review(self):
        row, proposal = self.postal_message()
        row = self.process(row, {**proposal, "matchedCompany": None, "companyMatchType": "uncertain", "companyMatchReason": None})
        self.assertEqual(row.status, "review")

    def test_company_renamed_during_model_wait_does_not_match_old_candidate(self):
        row, proposal = self.postal_message()

        replies = self.replies(proposal)

        async def response(messages):
            if "candidateCompanies" in json.loads(messages[1]["content"]):
                jobs.update_application(self.db, self.application.id, ApplicationUpdate(company="已更名的银行"))
                return replies[1]
            return replies[0]

        with patch.object(analysis.model_service, "llm_chat", new=AsyncMock(side_effect=response)):
            asyncio.run(service.analyze_message(self.db, row.id, self.token))
        self.db.refresh(row)
        self.assertEqual(row.status, "review")
        self.assertEqual(jobs.get_application(self.db, self.application.id).status, "screening")

    def test_keywords_are_queried_individually_and_union_is_deduplicated(self):
        row, proposal = self.postal_message()
        proposal["companySearchKeywords"] = ["邮储", "银行", "邮储", "邮政"]
        with patch.object(execution, "search_companies", wraps=execution.search_companies) as search, \
                patch.object(analysis.model_service, "llm_chat", new=AsyncMock(side_effect=self.replies(proposal))) as model:
            asyncio.run(service.analyze_message(self.db, row.id, self.token))
        self.assertEqual([call.args[1] for call in search.call_args_list], ["邮储", "银行", "邮政"])
        payload = json.loads(model.call_args_list[1].args[0][1]["content"])
        self.assertEqual(payload["candidateCompanies"], ["中国邮储银行"])
        self.db.refresh(row)
        self.assertEqual(len(row.proposal["companySearchResults"]), 3)

    def test_large_company_catalog_is_bounded_per_keyword(self):
        row, proposal = self.postal_message()
        self.db.add_all([Application(company=f"银行候选{i:04d}", position="研发工程师", status="screening") for i in range(600)])
        self.db.commit()
        with patch.object(analysis.model_service, "llm_chat", new=AsyncMock(side_effect=self.replies(proposal))) as model:
            asyncio.run(service.analyze_message(self.db, row.id, self.token))
        self.assertEqual(model.await_count, 2)
        first = json.loads(model.call_args_list[0].args[0][1]["content"])
        second = json.loads(model.call_args_list[1].args[0][1]["content"])
        self.assertNotIn("candidateCompanies", first)
        self.assertLessEqual(len(second["candidateCompanies"]), 5 * execution.COMPANY_SEARCH_LIMIT)
        self.assertIn("中国邮储银行", second["candidateCompanies"])
        broad = next(result for result in second["searches"] if result["keyword"] == "银行")
        self.assertEqual(len(broad["companies"]), execution.COMPANY_SEARCH_LIMIT)
        self.assertTrue(broad["hasMore"])

    def test_no_search_results_stops_before_second_model_request(self):
        row = self.message()
        proposal = self.proposal(companySearchKeywords=["毫无关联的检索词"])
        with patch.object(analysis.model_service, "llm_chat", new=AsyncMock(side_effect=self.replies(proposal))) as model:
            asyncio.run(service.analyze_message(self.db, row.id, self.token))
        self.assertEqual(model.await_count, 1)
        self.db.refresh(row)
        self.assertEqual(row.status, "review")
        self.assertEqual(row.proposal["companySearchResults"][0]["companies"], [])

    def test_reminder_ends_after_first_model_request(self):
        row = self.message()
        proposal = self.proposal(category="reminder")
        with patch.object(execution, "search_companies") as search, \
                patch.object(analysis.model_service, "llm_chat", new=AsyncMock(side_effect=self.replies(proposal))) as model:
            asyncio.run(service.analyze_message(self.db, row.id, self.token))
        self.assertEqual(model.await_count, 1)
        search.assert_not_called()

    def test_keyword_count_is_limited(self):
        row = self.process(self.message(), self.proposal(companySearchKeywords=[str(index) for index in range(6)]))
        self.assertEqual(row.status, "failed")

    def test_missing_keywords_requires_review(self):
        row = self.process(self.message(), self.proposal(companySearchKeywords=[]))
        self.assertEqual(row.status, "review")

    def test_search_wildcards_are_literal_characters(self):
        jobs.create_application(self.db, ApplicationCreate(company="100%科技", position="研发"))
        jobs.create_application(self.db, ApplicationCreate(company="100X科技", position="研发"))
        result = execution.search_companies(self.db, "%")
        self.assertEqual(result["companies"], ["100%科技"])
        self.assertEqual(execution.search_companies(self.db, "' OR 1=1 --")["companies"], [])

    def test_company_search_api_returns_distinct_bounded_results(self):
        jobs.create_application(self.db, ApplicationCreate(company="测试银行", position="另一岗位"))
        response = self.request("GET", "/api/mailbox/companies/search", params={"keyword": "测试"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["companies"], ["测试银行"])
        self.assertFalse(response.json()["hasMore"])
        self.assertEqual(self.request("GET", "/api/mailbox/companies/search", params={"keyword": " "}).status_code, 400)

    def test_invalid_second_result_does_not_add_more_model_requests(self):
        row, proposal = self.postal_message()
        proposal["matchedCompany"] = "不存在的候选公司"
        with patch.object(analysis.model_service, "llm_chat", new=AsyncMock(side_effect=self.replies(proposal))) as model:
            asyncio.run(service.analyze_message(self.db, row.id, self.token))
        self.assertEqual(model.await_count, 2)
        self.db.refresh(row)
        self.assertEqual(row.status, "failed")

    def test_second_request_failure_preserves_first_result_and_search_trace(self):
        row = self.message()
        with patch.object(analysis.model_service, "llm_chat", new=AsyncMock(
                side_effect=[self.replies()[0], HTTPException(504, "模拟第二轮超时")])):
            asyncio.run(service.analyze_message(self.db, row.id, self.token))
        self.db.refresh(row)
        self.assertEqual(row.status, "failed")
        self.assertEqual(row.proposal["company"], "测试银行")
        self.assertTrue(row.proposal["companySearchResults"])
        self.assertEqual(jobs.get_application(self.db, self.application.id).status, "screening")

    def test_legacy_proposal_without_search_fields_can_be_confirmed(self):
        row = self.message()
        proposal = self.proposal()
        proposal.pop("companySearchKeywords")
        row.proposal, row.status = proposal, "review"
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        result = execution.apply_event(self.db, row.id, execution.targets(self.db)[0], manual=True)
        self.assertEqual(result.status, "applied")

    def bank_unit_message(self):
        self.application.company = "中国银行"
        self.db.commit()
        jobs.update_application(self.db, self.application.id, ApplicationUpdate(position="上海省分", restart_process=True))
        body = f"中国银行软件中心邀请您参加一面，开始时间为{self.time_quote}。"
        row = self.message(body=body, subject="中国银行软件中心一面邀请")
        proposal = self.proposal(company="中国银行软件中心", position=None, companySearchKeywords=["中国银行", "软件中心"],
            matchedCompany="中国银行", companyMatchType="unit", companyMatchReason="已有岗位按招聘单位分组",
            targetPosition="中国银行软件中心", positionAction="create", positionMatchReason="沿用上海省分这类机构标签", evidence=body)
        return row, proposal

    def test_unit_context_creates_independent_position_without_switching_current(self):
        row, proposal = self.bank_unit_message()
        before = jobs.get_application(self.db, self.application.id)
        current = (before.position, before.position_version, before.status, before.primary_position_version)
        row = self.process(row, proposal)
        self.assertEqual(row.status, "applied")
        application = jobs.get_application(self.db, self.application.id)
        self.assertEqual((application.position, application.position_version, application.status, application.primary_position_version), current)
        created = next(item for item in position_summaries(application) if item["position"] == "中国银行软件中心")
        self.assertEqual(created["status"], "interviewing")
        self.assertGreater(created["positionVersion"], application.position_version)
        self.assertIn("新增岗位", row.to_dict()["changeSummary"])

    def test_second_request_receives_existing_position_labels(self):
        row, proposal = self.bank_unit_message()
        with patch.object(analysis.model_service, "llm_chat", new=AsyncMock(side_effect=self.replies(proposal))) as model:
            asyncio.run(service.analyze_message(self.db, row.id, self.token))
        payload = json.loads(model.call_args_list[1].args[0][1]["content"])
        profile = next(item for item in payload["companyPositionContext"] if item["company"] == "中国银行")
        self.assertIn("上海省分", profile["positions"])
        self.assertEqual(model.await_count, 2)

    def test_repeated_unit_invitation_reuses_created_position(self):
        row, proposal = self.bank_unit_message()
        first = self.process(row, proposal)
        application = jobs.get_application(self.db, self.application.id)
        counter = application.position_version_counter
        body = proposal["evidence"] + "请及时确认。"
        repeated = self.process(self.message(body=body, uid=12), {**proposal, "evidence": body})
        self.assertEqual(repeated.status, "duplicate")
        self.assertEqual(repeated.round_id, first.round_id)
        application = jobs.get_application(self.db, self.application.id)
        self.assertEqual(application.position_version_counter, counter)
        self.assertEqual(len([item for item in position_summaries(application)
                              if item["position"] == "中国银行软件中心"]), 1)

    def test_changed_company_snapshot_rejects_new_position_confirmation(self):
        row = self.process(self.message(), self.proposal(startAt=None, startEvidence=None))
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        parent = execution.company_targets(self.db)[0]
        target = {**parent, "createPosition": True, "newPosition": "待新增岗位"}
        round_id = jobs.get_application(self.db, self.application.id).rounds[0].id
        jobs.update_round(self.db, round_id, RoundUpdate(review_note="确认前新增的人工记录"))
        with self.assertRaises(execution.ReviewRequired):
            execution.apply_event(self.db, row.id, target, manual=True)
        self.db.rollback()
        application = jobs.get_application(self.db, self.application.id)
        self.assertFalse(any(item["position"] == "待新增岗位" for item in position_summaries(application)))
        self.assertEqual(application.position_version_counter, 1)
        self.assertEqual(self.db.get(MailMessage, row.id).status, "review")

    def test_unit_mapping_without_institutional_position_pattern_requires_review(self):
        self.application.company = "中国银行"
        self.db.commit()
        body = f"中国银行软件中心邀请您参加一面，开始时间为{self.time_quote}。"
        proposal = self.proposal(company="中国银行软件中心", position=None, companySearchKeywords=["中国银行"],
            matchedCompany="中国银行", companyMatchType="unit", companyMatchReason="归属候选",
            targetPosition="中国银行软件中心", positionAction="create", positionMatchReason="新增", evidence=body)
        row = self.process(self.message(body=body), proposal)
        self.assertEqual(row.status, "review")

    def test_new_position_and_status_roll_back_when_round_creation_fails(self):
        row, proposal = self.bank_unit_message()
        counter = self.db.get(Application, self.application.id).position_version_counter
        with patch.object(jobs, "create_round", side_effect=RuntimeError("模拟写入失败")):
            row = self.process(row, proposal)
        self.assertEqual(row.status, "failed")
        application = jobs.get_application(self.db, self.application.id)
        self.assertFalse(any(item["position"] == "中国银行软件中心" for item in position_summaries(application)))
        self.assertEqual(application.position_version_counter, counter)

    def test_new_position_version_is_not_reused_after_delete_or_reapply(self):
        row, proposal = self.bank_unit_message()
        self.process(row, proposal)
        application = jobs.get_application(self.db, self.application.id)
        summary = next(item for item in position_summaries(application) if item["position"] == "中国银行软件中心")
        deleted_version = summary["positionVersion"]
        jobs.delete_position(self.db, application.id, PositionDeleteInput(position=summary["position"],
            position_version=deleted_version, expected_position_version=application.position_version,
            expected_round_ids=summary["roundIds"], expected_status_history_ids=summary["statusHistoryIds"],
            expected_result_history_ids=summary["resultHistoryIds"]))
        application = jobs.update_application(self.db, application.id, ApplicationUpdate(position="另一岗位", restart_process=True))
        self.assertGreater(application.position_version, deleted_version)

    def test_manual_creation_accepts_user_position_label_and_is_idempotent(self):
        row = self.process(self.message(), self.proposal(startAt=None, startEvidence=None))
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        parent = execution.company_targets(self.db)[0]
        payload = {"applicationId": parent["applicationId"], "positionVersion": parent["expectedPositionVersion"],
            "position": None, "newPosition": "用户指定招聘单位", "expectedUpdatedAt": parent["expectedUpdatedAt"],
            "expectedCompanySnapshot": parent["expectedCompanySnapshot"]}
        first = self.request("POST", f"/api/mailbox/messages/{row.id}/apply", json=payload)
        second = self.request("POST", f"/api/mailbox/messages/{row.id}/apply", json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(len([item for item in position_summaries(jobs.get_application(self.db, self.application.id))
                              if item["position"] == "用户指定招聘单位"]), 1)

    def test_dated_job_title_maps_to_existing_position_instead_of_creating_duplicate(self):
        body = f"测试银行邀请研发工程师-2027届-广州参加一面，开始时间为{self.time_quote}。"
        proposal = self.proposal(position="研发工程师-2027届-广州", evidence=body, targetPosition="研发工程师",
            positionAction="existing", positionMatchReason="届次和地点是岗位描述后缀")
        row = self.process(self.message(body=body), proposal)
        self.assertEqual(row.status, "applied")
        self.assertEqual(len(position_summaries(jobs.get_application(self.db, self.application.id))), 1)

    def test_identical_existing_round_is_reported_as_unchanged(self):
        jobs.patch_status(self.db, self.application.id, ApplicationStatusPatch(status="interviewing"))
        existing = jobs.create_round(self.db, self.application.id, RoundCreate(round_type="first"))
        row = self.process(self.message(), self.proposal(startAt=None, startEvidence=None))
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        result = execution.apply_event(self.db, row.id, execution.targets(self.db)[0], manual=True, selected_round_id=existing.id)
        self.assertEqual(result.status, "unchanged")
        self.assertIn("现有记录一致", result.to_dict()["changeSummary"])

    def test_legacy_applied_record_explains_created_round_and_time(self):
        summary = change_summary({"before": {"status": "rescreen", "round": None},
            "after": {"status": "rescreen", "round": {"roundType": "written_test",
                "startAt": "2026-11-12T19:00:00", "scheduledAt": "2026-11-12T21:00:00"}}})
        self.assertIn("新增笔试", summary)
        self.assertIn("开始 2026-11-12 19:00", summary)
        self.assertIn("截止 2026-11-12 21:00", summary)

    def test_old_invitation_cannot_move_offer_position_backwards(self):
        jobs.patch_status(self.db, self.application.id, ApplicationStatusPatch(status="offer"))
        row = self.process(self.message())
        self.assertEqual(row.status, "review")
        self.assertEqual(jobs.get_application(self.db, self.application.id).status, "offer")

    def test_new_invitation_does_not_reopen_a_failed_position_automatically(self):
        jobs.patch_status(self.db, self.application.id, ApplicationStatusPatch(status="interviewing"))
        jobs.create_round(self.db, self.application.id, RoundCreate(round_type="first", result="failed"))
        body = f"测试银行邀请研发工程师参加二面，时间为{self.time_quote}。"
        row = self.process(self.message(body=body, subject="测试银行二面邀请"), self.proposal(roundType="second", evidence=body))
        self.assertEqual(row.status, "review")
        self.assertEqual(len(list(self.db.scalars(select(InterviewRound).where(InterviewRound.round_type == "second")))), 0)

    def test_failed_round_creation_rolls_back_status_and_keeps_mail(self):
        with patch.object(jobs, "create_round", side_effect=RuntimeError("模拟执行中断")):
            row = self.process(self.message())
        self.assertEqual(row.status, "failed")
        application = jobs.get_application(self.db, self.application.id)
        self.assertEqual(application.status, "screening")
        self.assertEqual(len(application.rounds), 1)
        self.assertIsNotNone(row.proposal)

    def test_deadline_is_not_recorded_as_start_time(self):
        body = f"测试银行研发工程师测评邀请，截止时间为{self.time_quote}。"
        proposal = self.proposal(roundType="assessment", startAt=None, startEvidence=None,
                                 deadlineAt=self.future.isoformat(), deadlineEvidence=self.time_quote, evidence=body)
        row = self.process(self.message(body=body, subject="测评邀请"), proposal)
        self.assertEqual(row.status, "applied")
        round_row = self.db.get(InterviewRound, row.round_id)
        self.assertIsNone(round_row.start_at)
        self.assertEqual(round_row.scheduled_at, self.future)

    def test_exact_duplicate_is_saved_without_reanalysis(self):
        original = self.message()
        raw = EmailMessage()
        raw["From"], raw["Subject"] = original.sender, original.subject
        raw.set_content(self.body)
        payload = imap_client.parse_mail(raw.as_bytes(), 12, datetime.now())
        service.store_batch(self.db, self.account.id, self.token,
                            {"validity": "7", "last_uid": 12, "messages": [payload], "reset": False})
        duplicate = self.db.scalar(select(MailMessage).where(MailMessage.uid == 12))
        self.assertEqual(duplicate.status, "duplicate")
        self.assertEqual(duplicate.duplicate_of, original.id)
        self.assertEqual(self.account.last_uid, 12)

    def test_only_one_scanner_can_claim_account(self):
        with self.assertRaises(HTTPException) as error:
            service.claim_scan(self.db, self.account.id)
        self.assertEqual(error.exception.status_code, 409)

    def test_stale_task_cannot_change_message_after_new_lease(self):
        row = self.message()
        row.status, row.processing_token = "analyzing", self.token
        self.account.scan_token = "new-task"
        self.db.commit()
        service.finish_message(self.db, row.id, self.token, "failed", "旧任务")
        self.db.refresh(row)
        self.assertEqual(row.status, "analyzing")

    def test_user_confirms_a_specific_historical_position(self):
        jobs.update_application(self.db, self.application.id, ApplicationUpdate(position="数据工程师", restart_process=True))
        row = self.process(self.message(), self.proposal(startAt=None, startEvidence=None))
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        target = next(item for item in execution.targets(self.db) if item["position"] == "研发工程师")
        execution.apply_event(self.db, row.id, target, manual=True)
        application = jobs.get_application(self.db, self.application.id)
        self.assertEqual(application.status, "screening")
        self.assertEqual(application.position, "数据工程师")
        self.assertEqual(next(r for r in application.rounds if r.round_type == "first").position_version, 1)

    def test_scan_failure_keeps_cursor_and_releases_lease(self):
        with patch.object(service, "authorization_code", return_value="test-only"), \
                patch.object(imap_client, "read_mailbox", side_effect=HTTPException(502, "连接失败")):
            asyncio.run(service.run_scan(self.account.id, self.token, session_factory=self.factory))
        self.db.refresh(self.account)
        self.assertEqual(self.account.last_uid, 10)
        self.assertIsNone(self.account.scan_token)
        self.assertEqual(self.account.last_error, "连接失败")

    def test_save_settings_establishes_baseline_without_backfill(self):
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        baseline = {"validity": "9", "last_uid": 200, "messages": [], "reset": False}
        with patch.object(service, "test_connection", new=AsyncMock(return_value=baseline)), \
                patch.object(service.private_store, "read_document", return_value={}), \
                patch.object(service.private_store, "write_document"):
            result = asyncio.run(service.save_settings(self.db, MailSettings(address="new-test@163.com", authorization_code="test-only")))
        account = service.current_account(self.db)
        self.assertEqual(account.last_uid, 200)
        self.assertAlmostEqual((account.next_scan_at - account.baseline_at).total_seconds(), 3600, delta=2)
        self.assertNotIn("test-only", json.dumps(result))

    def test_setting_same_account_preserves_existing_cursor(self):
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        with patch.object(service, "test_connection", new=AsyncMock(return_value={"validity": "7", "last_uid": 200})), \
                patch.object(service, "authorization_code", return_value="test-only"):
            asyncio.run(service.save_settings(self.db, MailSettings(address=self.account.address)))
        self.assertEqual(service.current_account(self.db).last_uid, 10)

    def test_changed_round_snapshot_rejects_stale_confirmation(self):
        row = self.process(self.message(), self.proposal(startAt=None, startEvidence=None))
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        target = execution.targets(self.db)[0]
        round_id = target["rounds"][0]["id"]
        jobs.update_round(self.db, round_id, RoundUpdate(review_note="用户刚补充的记录"))
        with self.assertRaises(execution.ReviewRequired):
            execution.apply_event(self.db, row.id, target, manual=True)
        self.db.rollback()
        self.assertEqual(jobs.get_application(self.db, self.application.id).status, "screening")

    def test_invitation_cannot_invent_a_passed_result(self):
        row = self.process(self.message(), self.proposal(result="passed"))
        self.assertEqual(row.status, "failed")

    def test_negative_result_cannot_be_inverted_by_model(self):
        jobs.patch_status(self.db, self.application.id, ApplicationStatusPatch(status="interviewing"))
        jobs.create_round(self.db, self.application.id, RoundCreate(round_type="first"))
        body = "测试银行研发工程师一面未通过，感谢您的参与。"
        row = self.process(self.message(body=body), self.proposal(eventType="result", result="passed",
            startAt=None, startEvidence=None, evidence=body))
        self.assertEqual(row.status, "review")

    def test_result_notification_preserves_existing_schedule(self):
        jobs.patch_status(self.db, self.application.id, ApplicationStatusPatch(status="interviewing"))
        existing = jobs.create_round(self.db, self.application.id, RoundCreate(
            round_type="first", start_at=self.future, duration_minutes=60, result="completed"))
        original_deadline = existing.scheduled_at
        other_deadline = self.future + timedelta(hours=3)
        quote = other_deadline.strftime("%Y年%m月%d日 %H:%M")
        body = f"测试银行研发工程师一面未通过，原通知截止时间为{quote}。"
        row = self.process(self.message(body=body), self.proposal(eventType="result", result="failed",
            startAt=None, startEvidence=None, deadlineAt=other_deadline.isoformat(), deadlineEvidence=quote, evidence=body))
        self.assertEqual(row.status, "applied")
        self.db.refresh(existing)
        self.assertEqual(existing.result, "failed")
        self.assertEqual(existing.scheduled_at, original_deadline)

    def test_manual_scan_does_not_change_hourly_due_time(self):
        expected = self.account.next_scan_at
        self.db.refresh(self.account)
        self.assertEqual(self.account.next_scan_at, expected)
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        service.claim_scan(self.db, self.account.id)
        self.db.refresh(self.account)
        self.assertEqual(self.account.next_scan_at, expected)

    def test_scheduled_scan_claims_only_when_due(self):
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        with self.assertRaises(HTTPException):
            service.claim_scan(self.db, self.account.id, scheduled=True)
        self.account.next_scan_at = datetime.now() - timedelta(seconds=1)
        self.db.commit()
        service.claim_scan(self.db, self.account.id, scheduled=True)
        self.db.refresh(self.account)
        self.assertAlmostEqual((self.account.next_scan_at - datetime.now()).total_seconds(), 3600, delta=2)

    def test_scheduler_runs_due_scan_without_waiting_an_hour_in_test(self):
        self.account.scan_token, self.account.lease_until = None, None
        self.account.next_scan_at = datetime.now() - timedelta(seconds=1)
        self.db.commit()
        with patch.object(router, "SessionLocal", self.factory), \
                patch.object(service, "run_scan", new=AsyncMock()) as run, \
                patch.object(router.asyncio, "sleep", new=AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(router.scheduler())
        run.assert_awaited_once()

    def request(self, method, path, **kwargs):
        test_app = FastAPI()
        test_app.include_router(router.router)
        test_app.dependency_overrides[get_db] = lambda: self.db

        async def send():
            transport = httpx.ASGITransport(app=test_app, client=("127.0.0.1", 12345))
            async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
                return await client.request(method, path, **kwargs)
        return asyncio.run(send())

    def test_api_manual_scan_is_queued_and_returns_immediately(self):
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        with patch.object(service, "run_scan", new=AsyncMock()) as run:
            response = self.request("POST", "/api/mailbox/scan")
        self.assertEqual(response.status_code, 202)
        run.assert_awaited_once()

    def test_api_scan_runs_full_fetch_analysis_and_atomic_update(self):
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        raw = EmailMessage()
        raw["From"], raw["Subject"] = "hr@example.invalid", "测试银行一面邀请"
        raw.set_content(self.body)
        payload = imap_client.parse_mail(raw.as_bytes(), 11, datetime.now())
        batch = {"validity": "7", "last_uid": 11, "messages": [payload], "reset": False, "has_more": False}
        with patch.object(service, "SessionLocal", self.factory), \
                patch.object(service, "authorization_code", return_value="test-only"), \
                patch.object(imap_client, "read_mailbox", return_value=batch), \
                patch.object(analysis.model_service, "llm_chat", new=AsyncMock(side_effect=self.replies())):
            response = self.request("POST", "/api/mailbox/scan")
        self.assertEqual(response.status_code, 202)
        self.db.expire_all()
        row = self.db.scalar(select(MailMessage).where(MailMessage.uid == 11))
        self.assertEqual(row.status, "applied")
        self.assertEqual(jobs.get_application(self.db, self.application.id).status, "interviewing")
        self.db.refresh(self.account)
        self.assertEqual(self.account.last_uid, 11)
        self.assertIsNone(self.account.scan_token)

    def test_scan_drains_pages_through_the_initial_uid_upper_bound(self):
        original = self.message()
        raw = EmailMessage()
        raw["From"], raw["Subject"] = original.sender, original.subject
        raw.set_content(self.body)
        payload = imap_client.parse_mail(raw.as_bytes(), 12, datetime.now())
        batches = [{"validity": "7", "last_uid": 11, "messages": [], "reset": False, "has_more": True, "upper_uid": 12},
                   {"validity": "7", "last_uid": 12, "messages": [payload], "reset": False, "has_more": False}]
        with patch.object(service, "authorization_code", return_value="test-only"), \
                patch.object(imap_client, "read_mailbox", side_effect=batches) as read, \
                patch.object(analysis.model_service, "llm_chat", new=AsyncMock(side_effect=self.replies())):
            asyncio.run(service.run_scan(self.account.id, self.token, session_factory=self.factory))
        self.assertEqual(read.call_count, 2)
        self.assertEqual(read.call_args.kwargs["through_uid"], 12)
        self.db.refresh(self.account)
        self.assertEqual(self.account.last_uid, 12)

    def test_api_paginates_messages_and_only_detail_returns_body(self):
        row = self.message()
        response = self.request("GET", "/api/mailbox/messages")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertNotIn("body", response.json()["items"][0])
        detail = self.request("GET", f"/api/mailbox/messages/{row.id}")
        self.assertIn(self.body, detail.json()["body"])

    def test_invalid_config_response_never_echoes_authorization_code(self):
        secret = "synthetic-test-value-" * 30
        response = self.request("PUT", "/api/mailbox/settings", json={"address": "bad", "authorizationCode": secret})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(secret, response.text)

    def test_api_confirmation_is_idempotent(self):
        row = self.process(self.message(), self.proposal(startAt=None, startEvidence=None))
        self.account.scan_token, self.account.lease_until = None, None
        self.db.commit()
        target = execution.targets(self.db)[0]
        payload = {key: target[key] for key in ("applicationId", "position", "positionVersion", "expectedUpdatedAt", "expectedSnapshot")}
        first = self.request("POST", f"/api/mailbox/messages/{row.id}/apply", json=payload)
        second = self.request("POST", f"/api/mailbox/messages/{row.id}/apply", json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        rounds = list(self.db.scalars(select(InterviewRound).where(InterviewRound.round_type == "first")))
        self.assertEqual(len(rounds), 1)

    def test_api_ignore_cannot_replace_an_applied_audit_record(self):
        row = self.process(self.message())
        response = self.request("POST", f"/api/mailbox/messages/{row.id}/ignore")
        self.assertEqual(response.status_code, 409)
        self.db.refresh(row)
        self.assertEqual(row.status, "applied")


class ImapTests(unittest.TestCase):
    def client(self, validity=b"7", next_uid=b"14"):
        client = Mock()
        client.capabilities = (b"IMAP4rev1",)
        client.select.return_value = ("OK", [b"3"])
        client.response.side_effect = lambda key: (key, [validity if key == "UIDVALIDITY" else next_uid])
        return client

    def test_first_connection_only_takes_uid_baseline(self):
        client = self.client()
        with patch.object(imap_client.imaplib, "IMAP4_SSL", return_value=client):
            result = imap_client.read_mailbox("test@163.com", "test-only")
        self.assertEqual(result["last_uid"], 13)
        client.uid.assert_not_called()
        client.select.assert_called_once_with("INBOX", readonly=True)

    def test_missing_select_uidnext_uses_status_response(self):
        client = self.client(next_uid=None)
        client.status.return_value = ("OK", [b'"INBOX" (UIDVALIDITY 7 UIDNEXT 140)'])
        with patch.object(imap_client.imaplib, "IMAP4_SSL", return_value=client):
            result = imap_client.read_mailbox("test@163.com", "test-only")
        self.assertEqual(result["last_uid"], 139)
        client.uid.assert_not_called()

    def test_missing_uidnext_uses_uid_only_baseline(self):
        client = self.client(next_uid=None)
        client.status.return_value = ("OK", [b'"INBOX" (UIDVALIDITY 7)'])
        client.uid.return_value = ("OK", [b"1 9 130"])
        with patch.object(imap_client.imaplib, "IMAP4_SSL", return_value=client):
            result = imap_client.read_mailbox("test@163.com", "test-only")
        self.assertEqual(result["last_uid"], 130)
        client.uid.assert_called_once_with("search", None, "ALL")

    def test_uidvalidity_reset_does_not_read_historical_messages(self):
        client = self.client(validity=b"8")
        with patch.object(imap_client.imaplib, "IMAP4_SSL", return_value=client):
            result = imap_client.read_mailbox("test@163.com", "test-only", validity="7", last_uid=10)
        self.assertTrue(result["reset"])
        client.uid.assert_not_called()

    def test_incremental_scan_uses_peek_and_filters_old_uids(self):
        client = self.client()
        client.uid.side_effect = [("OK", [b"9 11 13"]), ("OK", [(b"", b"Subject: test\r\n\r\nhello")]),
                                  ("OK", [(b"", b"Subject: test2\r\n\r\nhello")])]
        with patch.object(imap_client.imaplib, "IMAP4_SSL", return_value=client):
            result = imap_client.read_mailbox("test@163.com", "test-only", validity="7", last_uid=10)
        self.assertEqual([item["uid"] for item in result["messages"]], [11, 13])
        self.assertIn("BODY.PEEK", client.uid.call_args_list[1].args[2])

    def test_html_and_attachment_names_are_extracted(self):
        raw = EmailMessage()
        raw["Subject"] = "笔试邀请"
        raw.set_content("<html><style>hidden</style><p>测试银行笔试</p></html>", subtype="html", charset="gb18030")
        raw.add_attachment(b"test", maintype="application", subtype="pdf", filename="测评说明.pdf")
        result = imap_client.parse_mail(raw.as_bytes(), 1, datetime.now())
        self.assertIn("测试银行笔试", result["body"])
        self.assertNotIn("hidden", result["body"])
        self.assertEqual(result["attachments"], ["测评说明.pdf"])


if __name__ == "__main__":
    unittest.main()
