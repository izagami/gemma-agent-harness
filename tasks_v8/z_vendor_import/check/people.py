import random
FAM = ["佐藤","鈴木","高橋","田中","伊藤","渡辺","山本","中村","小林","加藤","吉田","山田","佐々木","山口","松本","井上","木村","林","斎藤","清水"]
GIV = ["太郎","花子","健太","さくら","翔","美咲","大輔","陽菜","蓮","結衣","悠真","葵","拓海","凛","颯太","芽依"]
ROM = ["Emily Clark","John Smith","Liu Wei","Anna Muller","Carlos Ruiz","Priya Nair","Tom Becker","Sofia Rossi"]
def people(n, seed, prefix):
    r = random.Random(seed); out = []; used = set()
    while len(out) < n:
        if r.random() < 0.25:
            name = r.choice(ROM)+" "+chr(65+len(out)%26)+"."
        else:
            name = r.choice(FAM)+" "+r.choice(GIV)
        if name in used: continue
        used.add(name)
        i = len(out)
        email = f"{prefix}{i:03d}.{r.choice(['k','m','t','y'])}@example.{r.choice(['jp','com','net'])}"
        phone = f"0{r.choice([3,6,90,80,70])}-{r.randint(1000,9999)}-{r.randint(1000,9999)}"
        out.append((name, email, phone))
    return out
