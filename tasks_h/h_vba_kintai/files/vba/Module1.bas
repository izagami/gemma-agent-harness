Attribute VB_Name = "Module1"
Option Explicit

' ============================================================
'  アルバイト勤怠集計マクロ
'  シート「勤怠」(1行目は見出し、タイムカードの転記)
'     A:日付  B:社員番号  C:氏名  D:出勤  E:退勤  F:休憩(分)  G:時給
'  締めは毎月15日。支給月 yyyymm を入れると 前月16日～当月15日 を集計し
'  kyuyo_yyyymm.txt (タブ区切り) を給与ソフト取込用に書き出す。
'  2017/05 総務課 作成 / 2021/10 深夜割増を追加 / 2023/04 土日手当を追加
' ============================================================

Private Const STD_WAGE As Long = 1100     ' 時給が空欄のときの標準時給
Private Const WEEKEND_ADD As Long = 100   ' 土日手当 (時給に加算)

Public Sub 勤怠集計()
    Dim ws As Worksheet
    Dim target As String, y As Integer, m As Integer
    Dim dFrom As Date, dTo As Date, d As Date
    Dim lastRow As Long, r As Long, i As Long, j As Long, e As Long
    Dim key As String
    Dim st As Long, en As Long, brk As Long, wk As Long, ot As Long, nt As Long, w As Long
    Dim pay As Double
    Dim dict As Object

    target = InputBox("支給月を yyyymm で入力 (前月16日～当月15日を集計)", "勤怠集計", Format(Date, "yyyymm"))
    If Len(target) <> 6 Or Not IsNumeric(target) Then Exit Sub
    y = CInt(Left(target, 4))
    m = CInt(Right(target, 2))
    dFrom = DateSerial(y, m - 1, 16)
    dTo = DateSerial(y, m, 15)

    Set ws = ThisWorkbook.Worksheets("勤怠")
    Set dict = CreateObject("Scripting.Dictionary")
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row

    ' 1 日ごとの計算結果 (行の順) と 社員 (最初に出てきた順)
    Dim n As Long, cnt As Long
    Dim eKey() As String, eName() As String
    Dim rEmp() As Long, rDate() As Date, rSt() As Double, rEn() As Double, rBrk() As Long
    Dim rWk() As Long, rOt() As Long, rNt() As Long, rPay() As Double
    n = 0: cnt = 0
    For r = 2 To lastRow
        If Not IsDate(ws.Cells(r, 1).Value) Then GoTo NextRow
        d = ws.Cells(r, 1).Value
        If d < dFrom Or d > dTo Then GoTo NextRow
        If Trim(ws.Cells(r, 2).Value) = "" Then GoTo NextRow
        ' 打刻漏れの日は集計しない (総務で手修正してから再実行)
        If ws.Cells(r, 4).Value = "" Or ws.Cells(r, 5).Value = "" Then GoTo NextRow

        st = Hour(ws.Cells(r, 4).Value) * 60 + Minute(ws.Cells(r, 4).Value)
        en = Hour(ws.Cells(r, 5).Value) * 60 + Minute(ws.Cells(r, 5).Value)
        If en <= st Then en = en + 1440               ' 日付をまたぐ勤務
        brk = Val(ws.Cells(r, 6).Value)
        wk = ((en - st - brk) \ 15) * 15             ' 15 分未満は切り捨て
        If wk <= 0 Then GoTo NextRow
        ot = 0
        If wk > 480 Then ot = wk - 480                ' 1 日 8 時間を超えた分は残業
        ' 深夜 (22:00～翌5:00)。休憩は深夜帯には取らない決まりなので引かない
        nt = Overlap(st, en, 0, 300) + Overlap(st, en, 1320, 1740)

        If ws.Cells(r, 7).Value = "" Then
            w = STD_WAGE
        Else
            w = ws.Cells(r, 7).Value
        End If
        If Weekday(d) = vbSaturday Or Weekday(d) = vbSunday Then w = w + WEEKEND_ADD
        ' 日額は円未満を持ったまま積み上げ、月の合計で切り捨てる
        pay = wk * w / 60 + ot * w * 0.25 / 60 + nt * w * 0.25 / 60

        key = Format(ws.Cells(r, 2).Value, "00000")
        If Not dict.Exists(key) Then
            n = n + 1
            ReDim Preserve eKey(1 To n): ReDim Preserve eName(1 To n)
            eKey(n) = key
            eName(n) = Trim(ws.Cells(r, 3).Value)
            dict.Add key, n
        End If
        cnt = cnt + 1
        ReDim Preserve rEmp(1 To cnt): ReDim Preserve rDate(1 To cnt)
        ReDim Preserve rSt(1 To cnt): ReDim Preserve rEn(1 To cnt): ReDim Preserve rBrk(1 To cnt)
        ReDim Preserve rWk(1 To cnt): ReDim Preserve rOt(1 To cnt): ReDim Preserve rNt(1 To cnt)
        ReDim Preserve rPay(1 To cnt)
        rEmp(cnt) = dict(key): rDate(cnt) = d
        rSt(cnt) = ws.Cells(r, 4).Value: rEn(cnt) = ws.Cells(r, 5).Value: rBrk(cnt) = brk
        rWk(cnt) = wk: rOt(cnt) = ot: rNt(cnt) = nt: rPay(cnt) = pay
NextRow:
    Next r
    If n = 0 Then
        MsgBox Format(dFrom, "yyyy/mm/dd") & "～" & Format(dTo, "yyyy/mm/dd") & " の勤怠がありません"
        Exit Sub
    End If

    Dim f As Integer, days As Long, sWk As Long, sOt As Long, sNt As Long, tot As Double, grand As Long
    f = FreeFile
    Open ThisWorkbook.Path & "\kyuyo_" & target & ".txt" For Output As #f
    Print #f, "集計期間" & vbTab & Format(dFrom, "yyyy/mm/dd") & vbTab & Format(dTo, "yyyy/mm/dd")
    Print #f, "社員番号" & vbTab & "氏名" & vbTab & "日付" & vbTab & "出勤" & vbTab & "退勤" & vbTab & "休憩" _
        & vbTab & "実働" & vbTab & "残業" & vbTab & "深夜" & vbTab & "日額"
    grand = 0
    For e = 1 To n
        days = 0: sWk = 0: sOt = 0: sNt = 0: tot = 0
        For i = 1 To cnt
            If rEmp(i) = e Then
                Print #f, eKey(e) & vbTab & eName(e) & vbTab & Format(rDate(i), "m/d(aaa)") _
                    & vbTab & Format(rSt(i), "h:mm") & vbTab & Format(rEn(i), "h:mm") & vbTab & rBrk(i) _
                    & vbTab & HM(rWk(i)) & vbTab & HM(rOt(i)) & vbTab & HM(rNt(i)) _
                    & vbTab & Format(rPay(i), "#,##0")
                days = days + 1
                sWk = sWk + rWk(i): sOt = sOt + rOt(i): sNt = sNt + rNt(i)
                tot = tot + rPay(i)
            End If
        Next i
        Print #f, eKey(e) & vbTab & eName(e) & vbTab & "計" & vbTab & days & "日" & vbTab & vbTab _
            & vbTab & HM(sWk) & vbTab & HM(sOt) & vbTab & HM(sNt) & vbTab & Format(Int(tot), "#,##0")
        grand = grand + Int(tot)
    Next e
    Print #f, "合計" & vbTab & n & "名" & vbTab & vbTab & vbTab & vbTab & vbTab & vbTab & vbTab & vbTab _
        & Format(grand, "#,##0")
    Close #f

    MsgBox "kyuyo_" & target & ".txt を出力しました"
End Sub

' 区間 [a1, a2) と [b1, b2) の重なり (分)
Private Function Overlap(ByVal a1 As Long, ByVal a2 As Long, ByVal b1 As Long, ByVal b2 As Long) As Long
    Dim s As Long, t As Long
    s = a1: If b1 > s Then s = b1
    t = a2: If b2 < t Then t = b2
    If t > s Then Overlap = t - s Else Overlap = 0
End Function

' 分 -> h:mm
Private Function HM(ByVal mins As Long) As String
    HM = (mins \ 60) & ":" & Format(mins Mod 60, "00")
End Function
