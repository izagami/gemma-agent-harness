"""Hidden behavioral check for tsel.py (run from a different cwd)."""
import os, subprocess, sys, tempfile

TSEL = "/work/tsel.py"
D = tempfile.mkdtemp()
os.chdir(D)
fails = []


def w(name, data):
    with open(name, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def run(*args, stdin=b""):
    r = subprocess.run([sys.executable, TSEL, *args], input=stdin, capture_output=True, timeout=10)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def case(name, got, code, out, err=""):
    exp = (code, out, err)
    if got != exp:
        fails.append(f"{name}: args gave {got!r}, expected {exp!r}")


w("p.tsv", "id\tname\tcity\tnote\n1\t佐藤\t東京\ta=b\n2\t鈴木\t大阪\t\n3\t高橋\t東京\turgent\n4\tLee\t名古屋\tx\n")
w("q.tsv", "id\tname\tcity\tnote\n5\t伊藤\t東京\t\n")
w("bad.tsv", "id\tname\tcity\n9\tZ\tZ\n")
w("empty.tsv", b"")
w("-n.tsv", "id\tname\tcity\tnote\n7\tDash\t札幌\t\n")
w("bom.tsv", b"\xef\xbb\xbfid\tv\r\n1\t\xe3\x81\x82\r\n2\tb\r\n")
w("c.csv", 'k,text,n\n1,"hello, world",3\n2,"say ""hi""",4\n3,plain,5\n')
w("semi.txt", "a;b;c\n1;2;3\n4;5;6\n")
w("short.tsv", "a\tb\tc\n1\t2\n3\t4\t5\n")
w("nh.tsv", "x\t1\tfoo\ny\t2\tbar\nz\t3\tfoo\n")

P = "id\tname\tcity\tnote\n"
case("all", run("p.tsv"), 0, open("p.tsv", encoding="utf-8").read())
case("names-order-dupes", run("-f", "city,id,id", "p.tsv"), 0,
     "city\tid\tid\n東京\t1\t1\n大阪\t2\t2\n東京\t3\t3\n名古屋\t4\t4\n")
case("index-range", run("-f", "4,1-2", "p.tsv"), 0, "note\tid\tname\na=b\t1\t佐藤\n\t2\t鈴木\nurgent\t3\t高橋\nx\t4\tLee\n")
case("range-single", run("-f2-2", "p.tsv"), 0, "name\n佐藤\n鈴木\n高橋\nLee\n")
case("where-and", run("-w", "city=東京", "-w", "id!=1", "-f", "name", "p.tsv"), 0, "name\n高橋\n")
case("where-empty-val", run("-w", "note=", "-f", "id", "p.tsv"), 0, "id\n2\n")
case("where-first-op", run("-w", "note=a=b", "-f", "id", "p.tsv"), 0, "id\n1\n")
case("where-neq-first", run("-w", "note!=a=b", "-n", "p.tsv"), 0, "3\n")
case("where-regex-eq", run("-w", "note~a=b", "-n", "p.tsv"), 0, "1\n")
case("where-regex", run("--where=name~^[A-Z]", "--fields=id", "p.tsv"), 0, "id\n4\n")
case("where-index", run("-w", "3=大阪", "-f", "1", "p.tsv"), 0, "id\n2\n")
case("no-match", run("-w", "city=福岡", "p.tsv"), 1, P)
case("count-zero", run("-n", "-w", "city=福岡", "p.tsv"), 1, "0\n")
case("count", run("--count", "p.tsv"), 0, "4\n")
case("combined-nH", run("-nH", "nh.tsv"), 0, "3\n")
case("attached-arg", run("-fname,city", "-wid=4", "p.tsv"), 0, "name\tcity\nLee\t名古屋\n")
case("long-sep-arg", run("--fields", "id", "--where", "city~阪", "p.tsv"), 0, "id\n2\n")
case("opts-after-file", run("p.tsv", "-f", "id", "-n"), 0, "4\n")
case("double-dash", run("-f", "name", "--", "-n.tsv"), 0, "name\nDash\n")
case("multi-files", run("-f", "id", "p.tsv", "q.tsv"), 0, "id\n1\n2\n3\n4\n5\n")
case("stdin-default", run("-f", "name", stdin=open("q.tsv", "rb").read()), 0, "name\n伊藤\n")
case("stdin-dash-mixed", run("-f", "id", "q.tsv", "-", stdin=open("p.tsv", "rb").read()), 0, "id\n5\n1\n2\n3\n4\n")
case("empty-file-ignored", run("-f", "id", "empty.tsv", "q.tsv"), 0, "id\n5\n")
case("empty-input", run("empty.tsv"), 1, "")
case("bom-crlf", run("-f", "v", "bom.tsv"), 0, "v\nあ\nb\n")
case("csv-quote", run("-d", ",", "-f", "text,k", "c.csv"), 0, 'text,k\n"hello, world",1\n"say ""hi""",2\nplain,3\n')
case("csv-where", run("-d,", "-w", "text=hello, world", "-f", "n", "c.csv"), 0, "n\n3\n")
case("csv-stdin", run("--delimiter=,", "-n", "-w", 'text~"', stdin=open("c.csv", "rb").read()), 0, "1\n")
case("other-delim", run("-d", ";", "-f", "c,a", "semi.txt"), 0, "c;a\n3;1\n6;4\n")
case("short-row", run("-f", "c,a", "short.tsv"), 0, "c\ta\n\t1\n5\t3\n")
case("noheader", run("-H", "-f", "3,1", "-w", "3=foo", "nh.tsv"), 0, "foo\tx\nfoo\tz\n")
case("noheader-stdin", run("--no-header", "-f", "2", stdin=b"a\tb\r\nc\td\r\n"), 0, "b\nd\n")
r = run("--help")
if r[0] != 0 or not r[1].strip():
    fails.append(f"--help: {r!r}")

E = "tsel: error: "
case("err-unknown-short", run("-x", "p.tsv"), 2, "", E + "unknown option: -x\n")
case("err-unknown-long", run("--bogus", "p.tsv"), 2, "", E + "unknown option: --bogus\n")
case("err-missing-arg", run("p.tsv", "-d"), 2, "", E + "option requires an argument: -d\n")
case("err-missing-arg-long", run("p.tsv", "--fields"), 2, "", E + "option requires an argument: --fields\n")
case("err-delim", run("-d", "ab", "p.tsv"), 2, "", E + "delimiter must be a single character\n")
case("err-unknown-field", run("-f", "id,zip", "p.tsv"), 2, "", E + "unknown field: zip\n")
case("err-unknown-where-field", run("-w", "zip=1", "p.tsv"), 2, "", E + "unknown field: zip\n")
case("err-index-0", run("-f", "0", "p.tsv"), 2, "", E + "field index out of range: 0\n")
case("err-index-big", run("-f", "1,5", "p.tsv"), 2, "", E + "field index out of range: 5\n")
case("err-index-noheader", run("-H", "-f", "4", "nh.tsv"), 2, "", E + "field index out of range: 4\n")
case("err-range", run("-f", "3-1", "p.tsv"), 2, "", E + "invalid range: 3-1\n")
case("err-name-noheader", run("-H", "-f", "name", "nh.tsv"), 2, "", E + "field names require a header: name\n")
case("err-expr", run("-w", "city", "p.tsv"), 2, "", E + "invalid expression: city\n")
case("err-expr-empty-col", run("-w", "=x", "p.tsv"), 2, "", E + "invalid expression: =x\n")
case("err-regex", run("-w", "name~(ab", "p.tsv"), 2, "", E + "invalid regex: (ab\n")
case("err-open", run("p.tsv", "missing.tsv"), 2, "", E + "cannot open: missing.tsv\n")
case("err-mismatch-no-partial", run("p.tsv", "bad.tsv"), 2, "", E + "header mismatch: bad.tsv\n")
case("err-mismatch-stdin", run("p.tsv", "-", stdin=b"id\tname\n1\tx\n"), 2, "", E + "header mismatch: -\n")

if fails:
    print(f"{len(fails)} behavior checks failed:")
    print("\n".join(fails[:15]))
    sys.exit(1)
print("tsel behavior OK")
