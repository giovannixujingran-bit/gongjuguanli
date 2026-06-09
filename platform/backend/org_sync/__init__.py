"""钉钉组织同步（Phase A，决策 #38）。

把钉钉的部门树 + 人员同步进平台库（department / user_account / user_department）。
- client.py：钉钉接口的抽象 DingtalkClient + httpx 实现（调经典通讯录 topapi）。
- sync.py：纯编排逻辑（遍历部门树、收集人员、按写入接口落库），可用假对象单测。

设计稿见 platform/docs/dingtalk-钉钉组织与部门治理/。
"""
