"""jobs 模块常量：状态/轮次/结果的合法值（key 存库，标签给前端展示）。"""

# 投递状态
APPLICATION_STATUSES = (
    "applied",        # 投递中
    "viewed",         # 已查看
    "assessment",     # 测评（一般位于笔试之前）
    "written_test",   # 笔试
    "interviewing",   # 面试中
    "offer",          # Offer
    "rejected",       # 挂了（被拒）
    "declined",       # 已拒绝（主动放弃）
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

# 轮次结果
ROUND_RESULTS = (
    "pending",        # 待定
    "passed",         # 通过
    "failed",         # 未通过
)

# 自定义日程类型
EVENT_TYPES = (
    "talk",           # 宣讲会
    "other",          # 其他
)

# 状态中文标签（报错文案用）
STATUS_LABELS = {
    "applied": "投递中",
    "viewed": "已查看",
    "assessment": "测评",
    "written_test": "笔试",
    "interviewing": "面试中",
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