Attribute VB_Name = "Module1"
Option Explicit

' ============================================================
'  支払予定表マクロ
'  シート「請求」(1行目は見出し、B列は "yyyy/m/d" の文字列)
'     A:請求番号  B:請求日  C:取引先  D:支払条件  E:金額
'  請求ごとに締め日・支払予定日を計算し、pay_schedule.txt (タブ区切り) に出す。
'  支払予定日が土日のときは前の金曜日に前倒しする。
'  「週」は 基準日 (年度初め 2026/4/1) から何週目か (日曜始まり)。
'  2020/06 財務課 作成 / 2025/03 「ヶ月後」の条件を追加
' ============================================================

Private Const KIJUN As Date = #4/1/2026#

Public Sub 支払予定表()
    Dim ws As Worksheet
    Dim lastRow As Long, r As Long
    Dim s As String, p As Variant, cond As String
    Dim y As Long, m As Long, d As Long, n As Long, pd As Long
    Dim dt As Date, closing As Date, pay As Date
    Dim f As Integer, wd As Long

    Set ws = ThisWorkbook.Worksheets("請求")
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    f = FreeFile
    Open ThisWorkbook.Path & "\pay_schedule.txt" For Output As #f
    Print #f, "請求番号" & vbTab & "請求日" & vbTab & "締め日" & vbTab & "支払予定日" & vbTab & "週" & vbTab & "金額"

    For r = 2 To lastRow
        ' --- 請求日 (文字列) をチェックして日付にする
        s = Trim(ws.Cells(r, 2).Value)
        p = Split(s, "/")
        If UBound(p) <> 2 Then GoTo BadDate
        If Not (IsNumeric(p(0)) And IsNumeric(p(1)) And IsNumeric(p(2))) Then GoTo BadDate
        y = CLng(p(0)): m = CLng(p(1)): d = CLng(p(2))
        dt = DateSerial(y, m, d)
        If Year(dt) <> y Or Month(dt) <> m Or Day(dt) <> d Then GoTo BadDate

        ' --- 支払条件
        cond = Trim(ws.Cells(r, 4).Value)
        If cond = "末締め翌月末払い" Then
            closing = DateSerial(y, m + 1, 0)
            pay = DateSerial(Year(closing), Month(closing) + 2, 0)
        ElseIf cond Like "末締め翌々月*日払い" Then
            closing = DateSerial(y, m + 1, 0)
            pd = Val(Mid(cond, 7))
            pay = DateSerial(Year(closing), Month(closing) + 2, pd)
        ElseIf cond Like "*日締め翌月*日払い" Or cond Like "*日締め翌月末払い" Then
            n = Val(cond)
            If d <= n Then
                closing = DateSerial(y, m, n)
            Else
                closing = DateSerial(y, m + 1, n)
            End If
            If InStr(cond, "翌月末") > 0 Then
                pay = DateSerial(Year(closing), Month(closing) + 2, 0)
            Else
                pd = Val(Mid(cond, InStr(cond, "翌月") + 2))
                pay = DateSerial(Year(closing), Month(closing) + 1, pd)
            End If
        ElseIf cond Like "納品後*日" Then
            closing = dt
            pay = DateAdd("d", Val(Mid(cond, 4)), dt)
        ElseIf cond Like "*ヶ月後" Then
            closing = dt
            pay = DateAdd("m", Val(cond), dt)
        Else
            Print #f, ws.Cells(r, 1).Value & vbTab & "ERROR 支払条件不明"
            GoTo NextRow
        End If

        ' --- 土日は前倒し (月曜=1 ... 日曜=7)
        wd = Weekday(pay, vbMonday)
        If wd = 6 Then
            pay = pay - 1
        ElseIf wd = 7 Then
            pay = pay - 2
        End If

        Print #f, ws.Cells(r, 1).Value & vbTab & Format(dt, "yyyy/mm/dd") & vbTab & Format(closing, "yyyy/mm/dd") _
            & vbTab & Format(pay, "yyyy/mm/dd (aaa)") & vbTab & DateDiff("ww", KIJUN, pay) _
            & vbTab & Format(ws.Cells(r, 5).Value, "#,##0")
        GoTo NextRow
BadDate:
        Print #f, ws.Cells(r, 1).Value & vbTab & "ERROR 請求日不正"
NextRow:
    Next r
    Close #f
    MsgBox "pay_schedule.txt を出力しました"
End Sub
