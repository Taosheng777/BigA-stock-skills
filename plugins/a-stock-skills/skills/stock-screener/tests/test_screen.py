# SENTINEL_TEST_C1
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import screen


class TestParseValue(unittest.TestCase):
    def test_float_passthrough(self):
        self.assertEqual(screen.parse_value(31.5), 31.5)

    def test_int_to_float(self):
        self.assertEqual(screen.parse_value(5), 5.0)

    def test_yi_unit(self):
        self.assertAlmostEqual(screen.parse_value("2.13亿"), 213000000.0)

    def test_wan_unit(self):
        self.assertAlmostEqual(screen.parse_value("1234万"), 12340000.0)

    def test_liutong_yi(self):
        self.assertAlmostEqual(screen.parse_value("2843.71亿"), 284371000000.0)

    def test_percent_keeps_magnitude(self):
        self.assertAlmostEqual(screen.parse_value("1.84%"), 1.84)

    def test_thousands_comma(self):
        self.assertAlmostEqual(screen.parse_value("1,234.5"), 1234.5)

    def test_none(self):
        self.assertIsNone(screen.parse_value(None))

    def test_empty_string(self):
        self.assertIsNone(screen.parse_value(""))

    def test_garbage(self):
        self.assertIsNone(screen.parse_value("--"))

    def test_scientific_notation_string(self):
        self.assertAlmostEqual(screen.parse_value("2.5356130847E8"), 253561308.47, places=2)

    def test_raw_decimal_string(self):
        self.assertAlmostEqual(screen.parse_value("12003367200.000"), 12003367200.0)

    def test_negative_number_string(self):
        self.assertAlmostEqual(screen.parse_value("-12126646"), -12126646.0)

    def test_bool_is_not_numeric(self):
        self.assertIsNone(screen.parse_value(True))


class TestNormalizeFieldName(unittest.TestCase):
    def test_strip_at_prefix(self):
        self.assertEqual(screen.normalize_field_name("@涨跌幅"), "涨跌幅")

    def test_strip_date_suffix(self):
        self.assertEqual(screen.normalize_field_name("最新价[20260623]"), "最新价")

    def test_strip_sub_marker(self):
        self.assertEqual(screen.normalize_field_name("涨跌幅:前复权"), "涨跌幅")

    def test_strip_all_layers(self):
        self.assertEqual(
            screen.normalize_field_name("近5日区间涨跌幅:前复权[20260619-20260623]"),
            "近5日区间涨跌幅",
        )

    def test_plain_unchanged(self):
        self.assertEqual(screen.normalize_field_name("股票代码"), "股票代码")

    def test_at_quality_field(self):
        self.assertEqual(screen.normalize_field_name("@净资产收益率"), "净资产收益率")


class TestPickValue(unittest.TestCase):
    def test_prefer_non_null_variant(self):
        rec = {"@净资产收益率": None, "净资产收益率": 19.87}
        self.assertAlmostEqual(screen.pick_value(rec, "净资产收益率"), 19.87)

    def test_unit_string_parsed(self):
        rec = {"@主力净流入": "2.13亿", "主力净流入": "2.13亿"}
        self.assertAlmostEqual(screen.pick_value(rec, "主力净流入"), 213000000.0)

    def test_single_at_variant(self):
        rec = {"@市盈率": 22.23}
        self.assertAlmostEqual(screen.pick_value(rec, "市盈率"), 22.23)

    def test_no_match_returns_none(self):
        rec = {"@涨跌幅": 1.84}
        self.assertIsNone(screen.pick_value(rec, "换手率"))

    def test_all_none_returns_none(self):
        rec = {"@净利润同比增长率": None, "净利润同比增长率": None}
        self.assertIsNone(screen.pick_value(rec, "净利润同比增长率"))


class TestRankPercentile(unittest.TestCase):
    def test_ascending(self):
        self.assertEqual(
            screen.rank_percentile([10, 20, 30, 40, 50]), [0.0, 0.25, 0.5, 0.75, 1.0]
        )

    def test_descending_input(self):
        self.assertEqual(
            screen.rank_percentile([50, 40, 30, 20, 10]), [1.0, 0.75, 0.5, 0.25, 0.0]
        )

    def test_none_skipped(self):
        self.assertEqual(screen.rank_percentile([10, None, 30]), [0.0, None, 1.0])

    def test_ties_average(self):
        self.assertEqual(screen.rank_percentile([10, 10, 20]), [0.25, 0.25, 1.0])

    def test_single_is_neutral(self):
        self.assertEqual(screen.rank_percentile([42]), [0.5])

    def test_all_none(self):
        self.assertEqual(screen.rank_percentile([None, None]), [None, None])

    def test_empty(self):
        self.assertEqual(screen.rank_percentile([]), [])


class TestScore(unittest.TestCase):
    def _pool(self):
        return [
            {"code": "A", "x": 10, "y": 100},
            {"code": "B", "x": 20, "y": 50},
            {"code": "C", "x": 30, "y": None},
        ]

    def test_weighted_score_and_gap_renorm(self):
        fields = [("x", 0.5, "higher"), ("y", 0.5, "lower")]
        res = screen.score(self._pool(), fields)
        by = {r["record"]["code"]: r["score"] for r in res}
        self.assertAlmostEqual(by["A"], 0.0)
        self.assertAlmostEqual(by["B"], 75.0)
        self.assertAlmostEqual(by["C"], 100.0)

    def test_parts_exposed(self):
        res = screen.score(self._pool(), [("x", 1.0, "higher")])
        self.assertIn("x", res[0]["parts"])

    def test_all_fields_none_score_none(self):
        res = screen.score([{"code": "A", "x": None}], [("x", 1.0, "higher")])
        self.assertIsNone(res[0]["score"])


class TestDedup(unittest.TestCase):
    def test_removes_duplicate_keeps_first(self):
        pool = [
            {"股票代码": "002415.SZ", "股票简称": "海康威视"},
            {"股票代码": "000021.SZ", "股票简称": "深科技"},
            {"股票代码": "002415.SZ", "股票简称": "海康威视-dup"},
        ]
        out = screen.dedup(pool)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["股票简称"], "海康威视")

    def test_empty(self):
        self.assertEqual(screen.dedup([]), [])


class TestExcludeHoldings(unittest.TestCase):
    def _pool(self):
        return [
            {"股票代码": "002415.SZ", "股票简称": "海康威视"},
            {"股票代码": "000021.SZ", "股票简称": "深科技"},
        ]

    def test_exclude_by_6digit(self):
        out = screen.exclude_holdings(self._pool(), ["002415"])
        self.assertEqual([r["股票代码"] for r in out], ["000021.SZ"])

    def test_exclude_by_suffixed_code(self):
        out = screen.exclude_holdings(self._pool(), ["000021.SZ"])
        self.assertEqual([r["股票代码"] for r in out], ["002415.SZ"])

    def test_empty_holdings_keeps_all(self):
        self.assertEqual(len(screen.exclude_holdings(self._pool(), [])), 2)

    def test_none_holdings_keeps_all(self):
        self.assertEqual(len(screen.exclude_holdings(self._pool(), None)), 2)


class TestRenderHtml(unittest.TestCase):
    def _results(self):
        return [
            {"record": {"股票代码": "002415.SZ", "股票简称": "海康威视"}, "score": 88.5, "parts": {"涨跌幅": 0.9}},
            {"record": {"股票代码": "000021.SZ", "股票简称": "深科技"}, "score": 72.0, "parts": {"涨跌幅": 0.5}},
        ]

    def _meta(self):
        return {"title": "放量突破", "date": "2026-06-24"}

    def test_contains_codes_and_names(self):
        out = screen.render_html(self._results(), self._meta())
        self.assertIn("002415", out)
        self.assertIn("海康威视", out)
        self.assertIn("深科技", out)

    def test_contains_score(self):
        out = screen.render_html(self._results(), self._meta())
        self.assertIn("88.5", out)

    def test_contains_disclaimer_and_date(self):
        out = screen.render_html(self._results(), self._meta())
        self.assertIn("非持牌投顾", out)
        self.assertIn("2026-06-24", out)

    def test_is_html_document(self):
        out = screen.render_html(self._results(), self._meta())
        self.assertTrue(out.lstrip().lower().startswith("<!doctype html"))

    def test_escapes_dynamic_values(self):
        out = screen.render_html(self._results(), {"title": "<script>x", "date": "2026-06-24"})
        self.assertNotIn("<script>x", out)


class TestIntegrationRealFixture(unittest.TestCase):
    """在真实问财返回上跑整条链路；真数据的字段名/结构以此为准（datas 在顶层）。"""

    def setUp(self):
        import json

        p = os.path.join(os.path.dirname(__file__), "fixtures", "probe-2-quality.json")
        try:
            with open(p, encoding="utf-8") as f:
                doc = json.load(f)
            self.pool = doc["datas"]
            if not self.pool:
                raise ValueError("empty datas")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
            self.skipTest("real fixture unavailable: %s" % e)

    def _fields(self):
        # 真实归一后字段名（[日期] 后缀由 normalize 剥除）
        return [
            ("最新涨跌幅", 0.20, "higher"),
            ("换手率", 0.15, "higher"),
            ("主力资金流向", 0.25, "higher"),
            ("归母净利润同比增长率", 0.15, "higher"),
            ("净资产收益率", 0.15, "higher"),
            ("最新市盈率ttm", 0.05, "lower"),
            ("最新市净率", 0.05, "lower"),
        ]

    def test_scores_real_pool_in_range(self):
        res = screen.score(self.pool, self._fields())
        self.assertEqual(len(res), len(self.pool))
        scored = [r for r in res if r["score"] is not None]
        self.assertGreater(len(scored), 0)
        for r in scored:
            self.assertGreaterEqual(r["score"], 0.0)
            self.assertLessEqual(r["score"], 100.0)

    def test_date_suffix_and_string_number_parsing(self):
        rec = self.pool[0]
        self.assertIsNotNone(screen.pick_value(rec, "换手率"))  # [日期] 后缀字段命中
        self.assertIsNotNone(screen.pick_value(rec, "净资产收益率"))
        self.assertIsNotNone(screen.pick_value(rec, "流通市值"))  # 裸数字字符串
        cje = screen.pick_value(rec, "成交额")  # 科学计数法字符串
        self.assertIsNotNone(cje)
        self.assertGreater(cje, 1e6)

    def test_render_real_pool(self):
        res = screen.score(self.pool, self._fields())
        out = screen.render_html(res, {"title": "放量突破", "date": "2026-06-24"})
        first6 = self.pool[0]["股票代码"].split(".")[0]
        self.assertIn(first6, out)
        self.assertIn("非持牌投顾", out)


# ---- C2: 数据访问 + 编排（holdings / fetch 翻页 / pipeline / presets / cli 投影）----


class TestLoadHoldings(unittest.TestCase):
    def _write(self, text):
        import tempfile

        fd, p = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        self.addCleanup(os.remove, p)
        return p

    def test_extracts_suffixed_codes_from_table(self):
        p = self._write(
            "| 标的 | 代码 | 持仓 |\n"
            "| 黄金ETF | 159934.SZ | 1700 |\n"
            "| 东阳光 | 600673.SH | 300 |\n"
        )
        self.assertEqual(set(screen.load_holdings(p)), {"159934", "600673"})

    def test_dedupes_repeated_code(self):
        p = self._write("600673.SH 建仓\n变更记录里 600673.SH 再次出现\n")
        self.assertEqual(screen.load_holdings(p), ["600673"])

    def test_ignores_funds_without_codes_and_money(self):
        # 基金账户无代码、带千分位逗号的金额、日期都不应被误当成代码
        p = self._write(
            "| 前海开源国企精选混合C | 112,243.00 | -0.34% |\n"
            "现价 9.347 成交额 10,105.00 数据日 2026-06-24\n"
            "| 招商银行 | 600036.SH | 200 |\n"
        )
        self.assertEqual(screen.load_holdings(p), ["600036"])

    def test_missing_file_returns_empty(self):
        self.assertEqual(screen.load_holdings("/no/such/holdings-xyz.md"), [])


class TestFetchPool(unittest.TestCase):
    def _runner(self, pages):
        def run(query, page, limit):
            return pages[page - 1]

        return run

    def test_accumulates_across_pages_until_no_more(self):
        pages = [
            {"datas": [{"股票代码": "1"}, {"股票代码": "2"}], "has_more": True},
            {"datas": [{"股票代码": "3"}], "has_more": False},
        ]
        out = screen.fetch_pool("q", max_records=100, page_limit=2, runner=self._runner(pages))
        self.assertEqual([r["股票代码"] for r in out], ["1", "2", "3"])

    def test_respects_max_records_cap(self):
        pages = [
            {"datas": [{"股票代码": "1"}, {"股票代码": "2"}], "has_more": True},
            {"datas": [{"股票代码": "3"}, {"股票代码": "4"}], "has_more": True},
        ]
        out = screen.fetch_pool("q", max_records=3, page_limit=2, runner=self._runner(pages))
        self.assertEqual(len(out), 3)

    def test_stops_on_empty_datas(self):
        pages = [{"datas": [], "has_more": True}]
        out = screen.fetch_pool("q", max_records=50, page_limit=10, runner=self._runner(pages))
        self.assertEqual(out, [])

    def test_missing_datas_raises(self):
        def run(query, page, limit):
            return {"error": "额度不足", "status_code": 403}

        with self.assertRaises(screen.ScreenError):
            screen.fetch_pool("q", runner=run)


class TestScreenPool(unittest.TestCase):
    def _pool(self):
        return [
            {"股票代码": "000001.SZ", "股票简称": "A", "x": 10},
            {"股票代码": "000002.SZ", "股票简称": "B", "x": 30},
            {"股票代码": "000002.SZ", "股票简称": "B-dup", "x": 30},
            {"股票代码": "000003.SZ", "股票简称": "C", "x": 20},
        ]

    def test_dedup_exclude_sort_top(self):
        fields = [("x", 1.0, "higher")]
        out = screen.screen_pool(self._pool(), fields, holding_codes=["000003"], top=10)
        codes = [r["record"]["股票代码"].split(".")[0] for r in out]
        self.assertEqual(codes, ["000002", "000001"])

    def test_top_limit(self):
        fields = [("x", 1.0, "higher")]
        out = screen.screen_pool(self._pool(), fields, holding_codes=None, top=1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["record"]["股票代码"], "000002.SZ")


class TestPresets(unittest.TestCase):
    def test_known_preset_has_query_and_fields(self):
        p = screen.get_preset("放量突破")
        self.assertTrue(p["query"])
        self.assertTrue(p["fields"])

    def test_unknown_preset_raises(self):
        with self.assertRaises(KeyError):
            screen.get_preset("不存在的模板")

    def test_all_presets_weights_normalized_and_valid_direction(self):
        self.assertGreaterEqual(len(screen.PRESETS), 4)
        for name, p in screen.PRESETS.items():
            wsum = sum(w for _, w, _ in p["fields"])
            self.assertAlmostEqual(wsum, 1.0, places=6, msg=name)
            for _, _, d in p["fields"]:
                self.assertIn(d, ("higher", "lower"), msg=name)

    def test_default_fields_valid(self):
        wsum = sum(w for _, w, _ in screen.DEFAULT_FIELDS)
        self.assertAlmostEqual(wsum, 1.0, places=6)


class TestBuildListing(unittest.TestCase):
    def test_summary_and_html(self):
        pool = [
            {"股票代码": "000001.SZ", "股票简称": "A", "x": 10},
            {"股票代码": "000002.SZ", "股票简称": "B", "x": 30},
        ]
        fields = [("x", 1.0, "higher")]
        out = screen.build_listing(
            pool, fields, holding_codes=None, top=15,
            meta={"title": "测试", "date": "2026-06-24"},
        )
        self.assertEqual(out["meta"]["title"], "测试")
        self.assertEqual(len(out["results"]), 2)
        self.assertIn("code", out["results"][0])
        self.assertIn("name", out["results"][0])
        self.assertIn("score", out["results"][0])
        self.assertIn("非持牌投顾", out["html"])
        self.assertEqual(out["results"][0]["code"], "000002.SZ")


class TestTencentPrefix(unittest.TestCase):
    """行情 enrichment 的市场前缀:优先用问财返回的交易所后缀,规避 5 开头误判。"""

    def test_suffix_sz(self):
        self.assertEqual(screen.tencent_prefix("002415.SZ"), "sz002415")

    def test_suffix_sh(self):
        self.assertEqual(screen.tencent_prefix("600036.SH"), "sh600036")

    def test_suffix_bj(self):
        self.assertEqual(screen.tencent_prefix("832000.BJ"), "bj832000")

    def test_suffix_sh_etf(self):
        self.assertEqual(screen.tencent_prefix("510300.SH"), "sh510300")

    def test_bare_6(self):
        self.assertEqual(screen.tencent_prefix("600519"), "sh600519")

    def test_bare_5_is_sh(self):
        # a-stock-data 原版 bug:5 开头判 sz;本实现必须判 sh
        self.assertEqual(screen.tencent_prefix("510300"), "sh510300")

    def test_bare_0_is_sz(self):
        self.assertEqual(screen.tencent_prefix("002415"), "sz002415")

    def test_bare_8_is_bj(self):
        self.assertEqual(screen.tencent_prefix("832000"), "bj832000")

    def test_invalid_none(self):
        self.assertIsNone(screen.tencent_prefix("abc"))


class TestParseTencentPayload(unittest.TestCase):
    # 字段索引与真实腾讯载荷对齐:2=代码 31=涨跌额 32=涨跌幅 38=换手率 39=PEttm 46=PB
    _F = "~".join(str(i) for i in range(6, 31))  # 索引 6..30 的占位
    SAMPLE = (
        'v_sz002415="51~海康威视~002415~30.00~29.50~29.60~' + _F +
        "~0.50~1.69~30.5~29.4~35~36~187040~4.55~18.2~40~41~42~7.22~2800.5~2700.4"
        '~2.85~32.4~27.6~1.2~50~51~314.7~53";\n'
        'v_sh600036="1~招商银行~600036~37.18~37.25~37.10~' + _F +
        "~-0.07~-0.19~37.24~36.82~35~36~296~0.33~6.8~40~41~42~1.13~9376~9376"
        '~1.05~40.9~33.5~0.9~50~51~6.9~53";'
    )

    def test_parse_两只(self):
        got = screen.parse_tencent_payload(self.SAMPLE)
        self.assertIn("002415", got)
        self.assertIn("600036", got)

    def test_std_fields(self):
        got = screen.parse_tencent_payload(self.SAMPLE)["002415"]
        self.assertAlmostEqual(got["最新涨跌幅"], 1.69)
        self.assertAlmostEqual(got["换手率"], 4.55)
        self.assertAlmostEqual(got["最新市盈率ttm"], 18.2)
        self.assertAlmostEqual(got["最新市净率"], 2.85)

    def test_negative_change(self):
        got = screen.parse_tencent_payload(self.SAMPLE)["600036"]
        self.assertAlmostEqual(got["最新涨跌幅"], -0.19)

    def test_short_line_skipped(self):
        self.assertEqual(screen.parse_tencent_payload('v_sh600000="1~x~600000";'), {})

    def test_pe_pb_zero_is_sentinel_none(self):
        # 腾讯对亏损股/ETF 的 PE/PB 给 0.00(哨兵值,非真值):必须转 None,
        # 否则 'lower' 方向打分会把亏损股排成"估值最优"
        sample = self.SAMPLE.replace("~4.55~18.2~", "~4.55~0.00~").replace(
            "~2.85~32.4~", "~0.00~32.4~")
        got = screen.parse_tencent_payload(sample)["002415"]
        self.assertIsNone(got["最新市盈率ttm"])
        self.assertIsNone(got["最新市净率"])
        self.assertAlmostEqual(got["换手率"], 4.55)  # 换手率 0 合法,不受影响


class TestEnrichRecords(unittest.TestCase):
    POOL = [
        {"股票代码": "002415.SZ", "股票简称": "海康威视",
         "换手率[20260714]": "9.99%", "主力资金流向": "1.2亿"},
        {"股票代码": "600036.SH", "股票简称": "招商银行"},
    ]

    @staticmethod
    def fake_fetcher(codes):
        assert "sz002415" in codes and "sh600036" in codes
        return {"002415": {"最新涨跌幅": 1.69, "换手率": 4.55,
                           "最新市盈率ttm": 18.2, "最新市净率": 2.85},
                "600036": {"最新涨跌幅": -0.19, "换手率": 0.33,
                           "最新市盈率ttm": 6.8, "最新市净率": 1.05}}

    def test_override_wencai_variant(self):
        pool = [dict(r) for r in self.POOL]
        _, info = screen.enrich_records(pool, fetcher=self.fake_fetcher)
        # 腾讯值覆盖问财变体列,pick_value 取到的是腾讯值
        self.assertAlmostEqual(screen.pick_value(pool[0], "换手率"), 4.55)
        self.assertTrue(info["enriched"])
        self.assertEqual(info["hit"], 2)

    def test_fill_missing(self):
        pool = [dict(r) for r in self.POOL]
        screen.enrich_records(pool, fetcher=self.fake_fetcher)
        self.assertAlmostEqual(screen.pick_value(pool[1], "最新市净率"), 1.05)

    def test_keep_t2_only_fields(self):
        pool = [dict(r) for r in self.POOL]
        screen.enrich_records(pool, fetcher=self.fake_fetcher)
        self.assertAlmostEqual(screen.pick_value(pool[0], "主力资金流向"), 1.2e8)

    def test_fetcher_partial_missing_keeps_wencai(self):
        pool = [dict(r) for r in self.POOL]
        screen.enrich_records(
            pool, fetcher=lambda codes: {"600036": {"换手率": 0.33}})
        # 002415 腾讯缺失 → 保留问财原值
        self.assertAlmostEqual(screen.pick_value(pool[0], "换手率"), 9.99)

    def test_fetcher_failure_graceful(self):
        def boom(codes):
            raise OSError("network down")
        pool = [dict(r) for r in self.POOL]
        _, info = screen.enrich_records(pool, fetcher=boom)
        self.assertFalse(info["enriched"])
        self.assertIn("network down", info["note"])
        self.assertAlmostEqual(screen.pick_value(pool[0], "换手率"), 9.99)


class TestPresetQueriesSlim(unittest.TestCase):
    """打分列改源后:行情类展示词缀移出问句;筛选条件与 T2 专属词缀保留;字段表不变。"""

    MARKET_DISPLAY_WORDS = ["换手率", "市净率"]

    def test_fangliang_query(self):
        q = screen.PRESETS["放量突破"]["query"]
        for w in self.MARKET_DISPLAY_WORDS + ["市盈率"]:
            self.assertNotIn(w, q)
        self.assertIn("主力资金流向", q)
        self.assertIn("非ST", q)

    def test_diwei_query(self):
        q = screen.PRESETS["低位反转"]["query"]
        for w in self.MARKET_DISPLAY_WORDS:
            self.assertNotIn(w, q)
        self.assertIn("股价站上5日均线", q)

    def test_yeji_keeps_filter_pe(self):
        q = screen.PRESETS["业绩成长"]["query"]
        self.assertIn("市盈率小于40", q)  # 条件保留
        self.assertNotIn("市净率", q)      # 纯展示词移除

    def test_zhuli_query(self):
        q = screen.PRESETS["主力异动"]["query"]
        self.assertNotIn("换手率", q)
        self.assertIn("资金流入", q)

    def test_fields_unchanged(self):
        # 打分字段契约不变:换手率等仍参与打分(由 enrichment 供数)
        for name in ("放量突破", "低位反转", "主力异动"):
            self.assertIn(
                "换手率",
                [f[0] for f in screen.PRESETS[name]["fields"]],
            )


if __name__ == "__main__":
    unittest.main()
