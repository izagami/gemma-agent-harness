#!/usr/bin/env python3
"""Hidden check for q_vba_text: run /work/customer_clean.py on the given and on hidden sheets, compare byte for byte
with an independent emulation of the macro (emu_text.py)."""
import csv, io, os, random, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emu_text as E

PROG = "/work/customer_clean.py"
HDR = ["顧客コード", "氏名", "フリガナ", "住所", "電話", "ポイント"]

CRAFTED = [
    ["C1001", "　山本　　健太　", "　やまもと　けんた", "千葉県千葉市中央区市場町1－1", "043(223)2110", " 1 2 3 "],
    ["C1002　", "小林 優子", "コバヤシ ユウコ", "埼玉県さいたま市浦和区高砂3－15－1", "048-824-2111", "5"],
    ["C1003", "ｶﾄｳ ｼｮｳｼﾞ株式会社 東日本営業本部", "かとうしょうじ", "宮城県仙台市青葉区本町3－8－1", "022-211-2111", "&H1F"],
    ["C1004", "吉田（株）", "ヨシダ", "静岡県静岡市葵区追手町9－6", "054 221 2455", "1.5e1"],
    ["C1005", "株式会社ミライ・ネクスト・ホールディングス", "ミライ・ネクスト", "東京都千代田区丸の内1－9－1 グラントウキョウノースタワー 30F", "03(1234)5678", "1d2"],
    ["c1006", "山口 智子", "ヤマグチ トモコ", "山口県山口市滝町1－1", "083-922-3111", "7"],
    ["C10071", "松本 翔", "マツモト ショウ", "長野県長野市大字南長野字幅下692－2", "026-232-0111", "8"],
    ["C1008", "井上 大輔", "イノウエ ダイスケ", "兵庫県神戸市中央区加納町6－5－1", "078 331 8181", "12,345"],
    ["C1009", "木村 さくら", "きむら さくら", "和歌山県和歌山市一番丁1", "073-432-4111", ".75"],
    ["C1010", "林 和也", "ハヤシ カズヤ", "鹿児島県鹿児島市鴨池新町10－1 行政庁舎 18階", "0992862111", "-12"],
    ["C1011", "清水 ゆかり", "シミズ ユカリ", "神奈川県川崎市川崎区宮本町1", "044-200-2111 (代)", "3.14159"],
    ["C1012", "山崎 健", "ヤマザキ ケン", "大阪府大阪市中央区大手前2－1－22", "06-6941-0351", "100ポイント"],
    ["C1013", "森 結衣", "モリ ユイ", "東京都港区芝公園4－2－8", "０３－３４３３－５１１１", "  "],
    ["C1014", "池田 浩二", "イケダ コウジ", "北海道旭川市6条通9丁目46", "0166-26-1111", "+7"],
    ["C1015", "橋本 ﾏﾘｱ", "ハシモト マリア", "沖縄県那覇市泉崎1－2－2", "098-866-2333", "1e"],
    ["C1016", "阿部 拓海", "アベ タクミ", "青森県青森市長島1－1－1", "017-722-1111", "&O17"],
    ["C1017", "石川 まどか", "イシカワ　マドカ", "石川県金沢市鞍月1－1", "076-225-1111", "0012"],
    ["C1018", "前田 光", "マエダ ヒカル", "岡山県岡山市北区内山下2－4－6", "086 224 2111 ext.5", "9.50"],
    ["C1019", "藤田 直樹", "フジタ ナオキ", "福島県福島市杉妻町2－16", "024-521-1111", "1.2.3"],
    ["C1020", "後藤 美穂", "ごとう みほ", "大分県大分市大手町3－1－1  大分県庁 本館", "097-536-1111", "abc"],
    ["C1021", "岡田 誠一郎（株式会社岡田建設 代表取締役）", "オカダ セイイチロウ", "広島県広島市中区基町10－52", "082-228-2111", "250"],
    ["C1022", "長谷川 ゆう", "ハセガワ ユウ", "愛媛県松山市一番町4－4－2", "", "3"],
    ["", "", "", "", "", ""],
    ["C1023", "近藤 ひなた", "コンドウ ヒナタ", "京都府京都市中京区寺町通御池上る上本能寺前町488", "075-222-3111", "1 000"],
    ["C1024", "石井 ダイキ", "イシイ ダイキ", "三重県津市広明町13", "059-224-3070", "2e3"],
    ["C1025", "村上 優", "ムラカミ ユウ", "新潟県新潟市中央区新光町4－1", "025-285-5511", "-0.25"],
    ["C1026", "遠藤 ＪＵＮ", "エンドウ ジュン", "岐阜県岐阜市薮田南2－1－1", "058-272-1111", "42 件"],
    ["C1027", "青木 碧", "アオキ ミドリ", "栃木県宇都宮市塙田1－1－20", "028-623-2323", "77pt（3月分）"],
]


def to_csv(rows):
    b = io.StringIO(); w = csv.writer(b, lineterminator="\r\n")
    w.writerow(HDR); [w.writerow(r) for r in rows]
    return b.getvalue().encode("cp932")


def randoms(n):
    rnd = random.Random(1022)
    sur = ["佐藤", "鈴木", "高橋", "田中", "渡辺", "ｻﾄｳ", "株式会社東西", "（株）北斗", "南北(株)", "合同会社ミナミ"]
    giv = ["太郎", "花子", "ﾊﾅｺ", "エンジニアリングサービス", "テクノロジーズ", "あおい", "一"]
    kana = ["さとう たろう", "サトウ　ハナコ", "　ﾀﾅｶ", "ガーデン・パーク", "ぱぴぷぺぽ", "ヴェール", "ＡＢＣ"]
    addr = ["東京都中央区銀座1－1－1 銀座ビル 3F", "神奈川県相模原市中央区中央2－11－15", "鹿児島県霧島市国分中央3－45－1",
            "北海道函館市東雲町4－13", "大阪府堺市堺区南瓦町3－1　堺市役所", "和歌山県田辺市新屋敷町1", "京都府宇治市宇治琵琶33"]
    tel = ["03-1111-2222", "0312345678", "06 1234 5678", "045-111-2222", "090-1111-2222", "０９０１１１１２２２２", "12345", "(099)111-2222"]
    pts = ["10", " 2 0 ", "3.5", "1e2", "&HFF", "1,000", "x", "", "0.125", "-4"]
    rows = []
    for i in range(n):
        code = rnd.choice([f"C{2000 + i}", f"C{2000 + i}", f"C{2000 + i}", f"C{20000 + i}", f" C{2000 + i} ", f"Ｃ{2000 + i}"])
        nm = rnd.choice(sur) + rnd.choice([" ", "　", "  ", ""]) + rnd.choice(giv) * rnd.choice([1, 1, 2])
        rows.append([code, nm, rnd.choice(kana), rnd.choice(addr), rnd.choice(tel), rnd.choice(pts)])
    return rows


def main():
    fails, cases = [], 0
    sc = [0, 0]
    tmp = tempfile.mkdtemp()
    sheets = [("given", None), ("hidden-1", CRAFTED), ("hidden-2", randoms(40))]
    for name, rows in sheets:
        src = "/work/data/kokyaku.csv" if rows is None else os.path.join(tmp, name + ".csv")
        if rows is not None:
            open(src, "wb").write(to_csv(rows))
        want = open("/check/orig_expected_customers_load.txt", "rb").read() if rows is None else E.convert(rows)
        dst = os.path.join(tmp, name + ".txt")
        r = subprocess.run([sys.executable, PROG, src, dst], capture_output=True, text=True, timeout=30)
        got = open(dst, "rb").read() if os.path.exists(dst) else b""
        wl, gl = want.split(b"\r\n"), got.split(b"\r\n")
        cases += len(wl) - 2
        bad = [j for j in range(len(wl)) if j >= len(gl) or wl[j] != gl[j]]
        # graded: lines in their place; a sheet whose bytes differ with no differing line (line ends, encoding,
        # trailing extra lines) counts as all wrong
        sc[0] += (len(wl) - len(bad)) if (got == want or bad) else 0
        sc[1] += len(wl)
        if got != want:
            fails.append(name)
            for j in bad[:3]:
                print(f"MISMATCH {name} line {j}: expected {wl[j].decode('cp932')!r} got "
                      f"{gl[j].decode('cp932', 'replace') if j < len(gl) else None!r}")
            if not bad:
                print(f"MISMATCH {name}: line endings or encoding differ: expected {want[:40]!r} got {got[:40]!r}")
            if r.stderr:
                print("stderr:", r.stderr[-300:])
            print(f"  {name}: {len(bad)} of {len(wl) - 1} lines differ")
    print(f"{cases} rows compared, {len(fails)} sheet(s) differ")
    print(f"SCORE {sc[0]}/{sc[1]}")
    sys.exit(1 if fails else 0)


main()
