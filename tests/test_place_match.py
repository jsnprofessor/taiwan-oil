import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from place_match import (  # noqa: E402
    FAR, MATCH, NO, REVIEW, address_query, best, cpc_address, match_station,
    name_match, name_query, norm, street,
)


def offset(lat, lng, north_m):
    """A point north_m metres north of (lat, lng)."""
    return lat + north_m / 111_320, lng


def station(sid, name, city, district, addr, lat, lng):
    return {"id": sid, "name": name, "city": city, "district": district,
            "addr": addr, "lat": lat, "lng": lng}


def place(pid, name, lat, lng, addr, status="OPERATIONAL"):
    return {"id": pid, "displayName": {"text": name},
            "location": {"latitude": lat, "longitude": lng},
            "formattedAddress": addr, "businessStatus": status, "types": ["gas_station"]}


class Normalising(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(norm("臺北市康寧路三段30號"), "台北市康寧路3段30號")
        self.assertEqual(norm("576巷86之1號"), "576巷86-1號")
        self.assertEqual(norm("１２３ 號"), "123號")

    def test_street(self):
        self.assertEqual(street("豐谷里15鄰中華路二段515號"), "中華路2段515號")
        self.assertEqual(street("114臺北市內湖區葫洲里康寧路三段30號"), "康寧路3段30號")
        self.assertEqual(street("樟樹村8鄰竹圍35-1號"), "")

    def test_name_match(self):
        self.assertTrue(name_match("康寧", "台灣中油康寧站(加盟&自助)"))
        self.assertTrue(name_match("山隆銅鑼", "山隆加油站 銅鑼站(中油/人工/自助)"))
        self.assertTrue(name_match("好市多中壢", "好市多Costco中壢加油站"))
        self.assertFalse(name_match("康寧", "台灣中油(直營)-東湖站"))

    def test_cpc_address(self):
        penghu = station("D5534", "鎖港漁船站", "澎湖縣", "", "馬公市鎖港里293號(備註:星期六日暫停營業)", 0, 0)
        self.assertEqual(cpc_address(penghu), "澎湖縣馬公市鎖港里293號")
        chiayi = station("II6212C65", "忠孝路", "嘉義市", "東區", "嘉義市東區忠孝路808號", 0, 0)
        self.assertEqual(cpc_address(chiayi), "嘉義市東區忠孝路808號")

    def test_queries(self):
        s = station("D5139", "南寮漁船站", "高雄市", "", "彌陀區南寮里漁港路73號", 24.84566, 120.92791)
        q = name_query(s)
        self.assertEqual(q["textQuery"], "台灣中油 南寮漁船站")
        self.assertEqual(q["locationBias"]["circle"]["radius"], 150)
        self.assertEqual(q["includedType"], "gas_station")
        self.assertTrue(q["strictTypeFiltering"])
        a = address_query(s)
        self.assertEqual(a["textQuery"], "台灣中油 高雄市彌陀區南寮里漁港路73號")
        self.assertNotIn("locationBias", a)


class RealCases(unittest.TestCase):
    """Cases met while matching all stations on 2026-10-15."""

    def test_makung_far_but_name_and_address_agree(self):
        s = station("D5531", "馬公漁船站", "澎湖縣", "", "馬公市海安街16號(備註:週六暫停營業)", 23.56821, 119.57076)
        boat = place("boat", "台灣中油馬公漁船加油站", *offset(23.56821, 119.57076, 457), "880澎湖縣馬公市啟明里海安街16號880")
        town = place("town", "台灣中油 馬公加油站", *offset(23.56821, 119.57076, -406), "880澎湖縣馬公市啟明里民福路18號")
        c = best(s, [town, boat], "name")
        self.assertEqual((c["pid"], c["verdict"]), ("boat", MATCH))

    def test_shiliu_cpc_brand_beats_franchise_office(self):
        s = station("II6212B98", "佳得美石榴站", "雲林縣", "斗六市", "榴中里石榴路230號", 23.72719, 120.5891)
        office = place("office", "佳得美股份有限公司石榴分公司", *offset(23.72719, 120.5891, 227), "640雲林縣斗六市榴中里石榴路230號")
        cpc = place("cpc", "台灣中油石榴站（ 加盟）", *offset(23.72719, 120.5891, 226), "640雲林縣斗六市榴中里石榴路230號")
        self.assertEqual(best(s, [office, cpc], "name")["pid"], "cpc")

    def test_zhongsen_cpc_listing_beats_inspection_shop(self):
        s = station("LL6212A45", "中森站", "宜蘭縣", "宜蘭市", "中山路5段501號", 24.77969, 121.75923)
        shop = place("shop", "中森加油站 ｜ 中森汽車檢驗廠", 24.77969, 121.75923, "260宜蘭縣宜蘭市茭白里中山路五段501號")
        cpc = place("cpc", "台灣中油 中森站(加盟)", *offset(24.77969, 121.75923, 11), "260宜蘭縣宜蘭市茭白里中山路五段501號")
        self.assertEqual(best(s, [shop, cpc], "name")["pid"], "cpc")

    def test_donghu_in_xizhi_is_only_review(self):
        s = station("D215W", "東湖站", "台北市", "內湖區", "康寧路三段225號", 25.0675, 121.61194)
        xizhi = place("xizhi", "台灣中油 東湖站(汐止康寧街）", *offset(25.0675, 121.61194, 595), "221新北市汐止區北山里康寧街6號")
        c = match_station(s, lambda body: [xizhi] if "locationBias" in body else [])
        self.assertEqual(c["verdict"], REVIEW)

    def test_jiangjun_neighbouring_cpc_listing_rejected(self):
        s = station("D503T", "將軍漁船站(僅星期一營業)", "台南市", "將軍區", "長沙里126-6號", 23.19, 120.11)
        other = place("other", "台灣中油 將軍站(直營&自助)", *offset(23.19, 120.11, 22), "725臺南市將軍區忠嘉里忠興162之1號")
        self.assertEqual(best(s, [other], "name")["verdict"], NO)

    def test_costco_dash_and_zhi_are_the_same(self):
        s = station("YY6212D25", "好市多中壢站", "桃園市", "中壢區", "民族路六段576巷86-1號", 24.9653, 121.1558)
        p = place("costco", "好市多Costco中壢加油站", *offset(24.9653, 121.1558, 26), "320桃園市中壢區過嶺里民族路六段576巷86之1號")
        c = best(s, [p], "name")
        self.assertEqual(c["verdict"], MATCH)
        self.assertIn("addr", c["signals"])

    def test_shanlong_tongluo_character_pairs(self):
        s = station("GG6212A73", "山隆銅鑼站", "苗栗縣", "銅鑼鄉", "樟樹村8鄰竹圍35-1號", 24.4487, 120.7794)
        p = place("shanlong", "山隆加油站 銅鑼站(中油/人工/自助)", *offset(24.4487, 120.7794, 9), "366苗栗縣銅鑼鄉樟樹村35-1號")
        self.assertEqual(best(s, [p], "name")["verdict"], MATCH)

    def test_suogang_garbled_google_address_is_review(self):
        s = station("D5534", "鎖港漁船站", "澎湖縣", "", "馬公市鎖港里293號(備註:星期六日暫停營業)", 23.53306, 119.60538)
        p = place("suogang", "台灣中油鎖港漁船加油站", *offset(23.53306, 119.60538, 564), "880澎湖縣馬公市鎖港里鎖管里293號")
        self.assertEqual(best(s, [p], "name")["verdict"], REVIEW)

    def test_nanliao_found_by_address_far_from_cpc_pin(self):
        s = station("D5139", "南寮漁船站", "高雄市", "", "彌陀區南寮里漁港路73號", 24.84566, 120.92791)
        hsinchu = place("hsinchu", "台灣中油南寮站（直營）", *offset(24.84566, 120.92791, 20), "300新竹市北區南寮里東大路四段292號")
        kaohsiung = place("kaohsiung", "台灣中油 南寮站(直營站附漁船加油)", 22.764367, 120.237296, "827高雄市彌陀區南寮里漁港路73號")
        c = match_station(s, lambda body: [hsinchu] if "locationBias" in body else [kaohsiung])
        self.assertEqual((c["pid"], c["verdict"]), ("kaohsiung", FAR))
        self.assertGreater(c["dist"], 200_000)

    def test_permanently_closed_listing_not_matched(self):
        s = station("X1", "測試站", "台北市", "中正區", "中正路1號", 25.04, 121.51)
        p = place("closed", "台灣中油 測試站", 25.04, 121.51, "100臺北市中正區中正路1號", status="CLOSED_PERMANENTLY")
        self.assertEqual(best(s, [p], "name")["verdict"], NO)

    def test_no_results(self):
        s = station("X1", "測試站", "台北市", "中正區", "中正路1號", 25.04, 121.51)
        self.assertIsNone(match_station(s, lambda body: []))


if __name__ == "__main__":
    unittest.main()
