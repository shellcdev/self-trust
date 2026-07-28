# -*- coding: utf-8 -*-
"""多币种支持测试（Level A: contract.currency + Level B: judge --currency/--rate）。

测试覆盖：
- CNY 原生透传（向后兼容，无额外字段）
- 外币换算判定（amount_cny = amount * rate，判定基于换算后金额）
- 缺失汇率 / 无效汇率报错
- contract.currency 字段存储与读取
- submit 落盘：pending_spends / pending_requests / audit_log 记录原始币种信息
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from core.contract import read_contract, write_contract
from core.models import CURRENCY_SYMBOLS, currency_symbol, Contract
from modules.initialize import lazy_init
from modules.judge import judge, submit

TODAY = date(2026, 7, 27)


# ================================================================ Level A
class TestCurrencyField:
    """contract.currency 字段存储 + 符号映射。"""

    def test_default_currency_is_cny(self, tmp_data_dir: Path):
        """默认初始化 → currency=CNY。"""
        result = lazy_init(
            tmp_data_dir, corpus=200000, monthly_contribution=8000,
            objectives=[{"name": "FIRE", "target_amount": 3000000,
                         "deadline": "2036-01-01"}],
            today=TODAY)
        assert result["ok"]
        c = read_contract(tmp_data_dir)
        assert c["currency"] == "CNY"

    def test_init_with_usd(self, tmp_data_dir: Path):
        """init --currency USD → contract.currency=USD。"""
        result = lazy_init(
            tmp_data_dir, corpus=50000, monthly_contribution=5000,
            objectives=[{"name": "FIRE", "target_amount": 1000000,
                         "deadline": "2036-01-01"}],
            today=TODAY, currency="USD")
        assert result["ok"]
        c = read_contract(tmp_data_dir)
        assert c["currency"] == "USD"

    def test_currency_uppercase(self, tmp_data_dir: Path):
        """小写 usd → 自动转大写 USD。"""
        result = lazy_init(
            tmp_data_dir, corpus=50000, monthly_contribution=5000,
            objectives=[{"name": "FIRE", "target_amount": 1000000,
                         "deadline": "2036-01-01"}],
            today=TODAY, currency="usd")
        assert result["ok"]
        c = read_contract(tmp_data_dir)
        assert c["currency"] == "USD"

    def test_currency_symbol_mapping(self):
        """CURRENCY_SYMBOLS 映射完整。"""
        assert currency_symbol("CNY") == "¥"
        assert currency_symbol("USD") == "$"
        assert currency_symbol("EUR") == "€"
        assert currency_symbol("HKD") == "HK$"
        # 未知币种回退到 code 本身
        assert currency_symbol("XYZ") == "XYZ"
        # 空值默认 CNY
        assert currency_symbol("") == "¥"

    def test_contract_dataclass_has_currency(self):
        """Contract dataclass 含 currency 字段，默认 CNY。"""
        c = Contract()
        assert c.currency == "CNY"
        d = c.to_dict()
        assert "currency" in d and d["currency"] == "CNY"

    def test_old_contract_without_currency_backward_compat(self, tmp_data_dir: Path):
        """旧契约（无 currency 字段）→ from_dict 回退默认 CNY。"""
        result = lazy_init(
            tmp_data_dir, corpus=200000, monthly_contribution=8000,
            objectives=[{"name": "FIRE", "target_amount": 3000000,
                         "deadline": "2036-01-01"}],
            today=TODAY)
        assert result["ok"]
        c = read_contract(tmp_data_dir)
        # 删掉 currency 模拟旧契约
        del c["currency"]
        # from_dict 应能读取（忽略未知/缺失字段）
        c2 = Contract.from_dict(c)
        assert c2.currency == "CNY"  # dataclass 默认值


# ================================================================ Level B
class TestJudgeMultiCurrency:
    """judge() 多币种换算判定。"""

    def test_cny_passthrough_no_extra_fields(self, base_contract: dict):
        """CNY 原生 → 不触发换算，original_amount=None（向后兼容）。"""
        r = judge(base_contract, amount=6000, category="合理享受",
                  planned=False, today=TODAY)
        assert r["ok"]
        assert r["inputs"]["original_amount"] is None
        assert r["inputs"]["original_currency"] is None
        assert r["inputs"]["exchange_rate"] is None
        assert r["inputs"]["base_currency"] == "CNY"
        assert r["inputs"]["amount"] == 6000.0

    def test_usd_conversion(self, base_contract: dict):
        """USD 200 @7.25 → CNY 1450 判定。"""
        r = judge(base_contract, amount=200, category="合理享受",
                  planned=False, today=TODAY, currency="USD", exchange_rate=7.25)
        assert r["ok"]
        assert r["inputs"]["original_amount"] == 200.0
        assert r["inputs"]["original_currency"] == "USD"
        assert r["inputs"]["exchange_rate"] == 7.25
        assert r["inputs"]["amount"] == 1450.0    # 换算后金额
        # 判定基于换算后金额
        assert r["inputs"]["remaining_after"] == r["inputs"]["net_assets"] - 1450.0

    def test_usd_conversion_same_scene_as_cny(self, base_contract: dict):
        """$200@7.25=¥1450 与直接 ¥1450 判定结果一致。"""
        r_usd = judge(base_contract, amount=200, category="合理享受",
                      planned=False, today=TODAY, currency="USD", exchange_rate=7.25)
        r_cny = judge(base_contract, amount=1450, category="合理享受",
                      planned=False, today=TODAY)
        assert r_usd["ok"] and r_cny["ok"]
        assert r_usd["decision"]["scene"] == r_cny["decision"]["scene"]
        assert r_usd["decision"]["result"] == r_cny["decision"]["result"]
        # 中间变量一致（换算后金额相同）
        assert r_usd["inputs"]["remaining_after"] == r_cny["inputs"]["remaining_after"]
        assert r_usd["inputs"]["effective_cushion"] == r_cny["inputs"]["effective_cushion"]

    def test_missing_rate_error(self, base_contract: dict):
        """非 CNY 但无 rate → 报错。"""
        r = judge(base_contract, amount=200, category="合理享受",
                  planned=False, today=TODAY, currency="USD")
        assert r["ok"] is False
        assert r["error"] == "missing_rate"

    def test_zero_rate_error(self, base_contract: dict):
        """rate=0 → 报错。"""
        r = judge(base_contract, amount=200, category="合理享受",
                  planned=False, today=TODAY, currency="USD", exchange_rate=0)
        assert r["ok"] is False
        assert r["error"] == "missing_rate"

    def test_negative_rate_error(self, base_contract: dict):
        """rate<0 → 报错。"""
        r = judge(base_contract, amount=200, category="合理享受",
                  planned=False, today=TODAY, currency="USD", exchange_rate=-1)
        assert r["ok"] is False
        assert r["error"] == "missing_rate"

    def test_same_currency_no_conversion(self, base_contract: dict):
        """currency=CNY + rate=999 → 不触发换算（币种相同直接跳过）。"""
        r = judge(base_contract, amount=6000, category="合理享受",
                  planned=False, today=TODAY, currency="CNY", exchange_rate=999)
        assert r["ok"]
        assert r["inputs"]["amount"] == 6000.0
        assert r["inputs"]["original_amount"] is None  # 未触发换算

    def test_contract_currency_as_base(self, tmp_data_dir: Path):
        """contract.currency=USD 时，CNY 消费需换算到 USD。"""
        result = lazy_init(
            tmp_data_dir, corpus=50000, monthly_contribution=5000,
            objectives=[{"name": "FIRE", "target_amount": 1000000,
                         "deadline": "2036-01-01"}],
            today=TODAY, currency="USD")
        assert result["ok"]
        c = read_contract(tmp_data_dir)
        # contract base=USD, 消费 CNY 1450 @0.138 → USD 200.1
        r = judge(c, amount=1450, category="合理享受", planned=False,
                  today=TODAY, currency="CNY", exchange_rate=0.138)
        assert r["ok"]
        assert r["inputs"]["base_currency"] == "USD"
        assert r["inputs"]["original_currency"] == "CNY"
        assert abs(r["inputs"]["amount"] - 200.1) < 0.01


# ================================================================ submit 落盘
class TestSubmitMultiCurrency:
    """submit() 落盘：pending_spends / pending_requests / audit_log 记录币种信息。"""

    def test_submit_usd_records_currency(self, tmp_data_dir: Path):
        """submit USD → pending_spends 记录原始币种。"""
        result = lazy_init(
            tmp_data_dir, corpus=200000, monthly_contribution=8000,
            objectives=[{"name": "FIRE", "target_amount": 3000000,
                         "deadline": "2036-01-01"}],
            today=TODAY)
        assert result["ok"]

        r = submit(tmp_data_dir, amount=200, category="合理享受",
                   planned=False, today=TODAY, currency="USD", exchange_rate=7.25)
        assert r["ok"]

        c = read_contract(tmp_data_dir)
        spends = c.get("pending_spends", [])
        assert len(spends) == 1
        s = spends[0]
        assert s["amount"] == 200.0           # 原始金额
        assert s["amount_base"] == 1450.0     # 换算后金额
        assert s["currency"] == "USD"
        assert s["exchange_rate"] == 7.25
        assert s["base_currency"] == "CNY"

    def test_submit_cny_no_currency_fields(self, tmp_data_dir: Path):
        """submit CNY → currency/exchange_rate 为 None（向后兼容）。"""
        result = lazy_init(
            tmp_data_dir, corpus=200000, monthly_contribution=8000,
            objectives=[{"name": "FIRE", "target_amount": 3000000,
                         "deadline": "2036-01-01"}],
            today=TODAY)
        assert result["ok"]

        r = submit(tmp_data_dir, amount=6000, category="合理享受",
                   planned=False, today=TODAY)
        assert r["ok"]

        c = read_contract(tmp_data_dir)
        spends = c.get("pending_spends", [])
        assert len(spends) == 1
        s = spends[0]
        assert s["currency"] is None
        assert s["exchange_rate"] is None

    def test_submit_usd_cooldown_records_currency(self, tmp_data_dir: Path):
        """触发冷静期的 USD 消费 → pending_requests 记录币种信息。"""
        result = lazy_init(
            tmp_data_dir, corpus=200000, monthly_contribution=8000,
            objectives=[{"name": "FIRE", "target_amount": 3000000,
                         "deadline": "2036-01-01"}],
            today=TODAY)
        assert result["ok"]

        # $1000 @7.25 = ¥7250 → 超过冷静期阈值（¥3000）→ 触发冷静期
        r = submit(tmp_data_dir, amount=1000, category="数码",
                   planned=False, today=TODAY, currency="USD", exchange_rate=7.25)
        assert r["ok"]
        assert r["cooldown"]["triggered"] is True
        assert r.get("request_id") is not None

        c = read_contract(tmp_data_dir)
        reqs = c.get("pending_requests", [])
        assert len(reqs) == 1
        req = reqs[0]
        assert req["amount"] == 1000.0          # 原始金额
        assert req["amount_base"] == 7250.0     # 换算后金额
        assert req["original_currency"] == "USD"
        assert req["exchange_rate"] == 7.25
        assert req["base_currency"] == "CNY"

    def test_audit_log_records_currency(self, tmp_data_dir: Path):
        """F8 审计快照记录原始币种信息。"""
        from core import audit as audit_io

        result = lazy_init(
            tmp_data_dir, corpus=200000, monthly_contribution=8000,
            objectives=[{"name": "FIRE", "target_amount": 3000000,
                         "deadline": "2036-01-01"}],
            today=TODAY)
        assert result["ok"]

        r = submit(tmp_data_dir, amount=200, category="合理享受",
                   planned=False, today=TODAY, currency="USD", exchange_rate=7.25)
        assert r["ok"]

        records = audit_io.read_all(tmp_data_dir, "approval_log")
        assert len(records) >= 1
        # 最后一条是本次审批快照
        snap = records[-1]
        assert snap["original_amount"] == 200.0
        assert snap["original_currency"] == "USD"
        assert snap["exchange_rate"] == 7.25
        assert snap["base_currency"] == "CNY"
