"""jobs 模块常量：状态/轮次/结果的合法值（key 存库，标签给前端展示）。"""

# 投递状态
APPLICATION_STATUSES = (
    "screening",      # 初筛（原投递中+已查看合并）
    "assessment",     # 测评
    "written_test",   # 笔试
    "interviewing",   # 面试
    "offer",          # Offer
)

# 流程轮次类型
ROUND_TYPES = (
    "assessment",     # 测评
    "written_test",   # 笔试
    "first",          # 一面
    "second",         # 二面
    "third",          # 三面
    "hr",             # HR面
    "final",          # 终面
    "other",          # 其他
)

# 轮次结果（待定细分为：未开始 / 已完成但结果未出）
ROUND_RESULTS = (
    "not_started",    # 未开始
    "completed",      # 已完成（还不知道结果）
    "not_attended",   # 未参加（已完成的对立面：跳过 / 放弃该轮）
    "passed",         # 通过
    "failed",         # 未通过
    "accepted",       # 接受 Offer（仅状态为 Offer 时使用）
    "rejected_offer", # 拒绝 Offer（仅状态为 Offer 时使用）
)

# 自定义日程类型
EVENT_TYPES = (
    "talk",           # 宣讲会
    "other",          # 其他
)

# 状态流转顺序（正向推进联动轮次结果用）
STATUS_FLOW = ("screening", "assessment", "written_test", "interviewing", "offer")

# 状态中文标签（报错文案用；rejected/declined 为废弃状态，仅老数据展示兼容）
STATUS_LABELS = {
    "screening": "初筛",
    "assessment": "测评",
    "written_test": "笔试",
    "interviewing": "面试",
    "offer": "Offer",
    "rejected": "挂了",
    "declined": "已拒绝",
}

# 轮次类型中文标签（报错文案用）
ROUND_TYPE_LABELS = {
    "assessment": "测评",
    "written_test": "笔试",
    "first": "一面",
    "second": "二面",
    "third": "三面",
    "hr": "HR面",
    "final": "终面",
    "other": "其他",
}

# 轮次类型 → 要求的投递状态（None = 不限）；硬约束：状态没到位不能加对应轮次
ROUND_TYPE_STATUS = {
    "assessment": "assessment",
    "written_test": "written_test",
    "first": "interviewing",
    "second": "interviewing",
    "third": "interviewing",
    "hr": "interviewing",
    "final": "interviewing",
    "other": None,
}