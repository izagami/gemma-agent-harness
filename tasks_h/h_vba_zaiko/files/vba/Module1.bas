Attribute VB_Name = "Module1"
Option Explicit

' ============================================================
'  在庫評価表マクロ (移動平均法 + ABC 分析)
'  シート「入出庫」(1行目は見出し)
'     A:日付  B:品番  C:区分(入庫/出庫/調整)  D:数量  E:単価(入庫のみ)
'  シート「品目」(1行目は見出し)
'     A:品番  B:品名  C:入数(1ケースの個数)
'  基準日までの入出庫から品番ごとの在庫数と評価額を出し、
'  評価額の大きい順に zaiko_yyyymmdd.txt (タブ区切り) に書き出す。
'  2020/09 物流課 作成 / 2022/03 ABC ランクを追加 / 2024/07 調整区分を追加
' ============================================================

Public Sub 在庫評価表()
    Dim wsT As Worksheet, wsM As Worksheet
    Dim lastRow As Long, r As Long, i As Long, j As Long, k As Long, t As Long
    Dim s As String, kijun As Date
    Dim code As String, kbn As String
    Dim qty As Long, cost As Long, irisu As Long
    Dim dict As Object, mst As Object

    s = InputBox("基準日を yyyy/mm/dd で入力", "在庫評価表", Format(Date, "yyyy/mm/dd"))
    If Not IsDate(s) Then Exit Sub
    kijun = CDate(s)

    Set wsT = ThisWorkbook.Worksheets("入出庫")
    Set wsM = ThisWorkbook.Worksheets("品目")
    lastRow = wsT.Cells(wsT.Rows.Count, 1).End(xlUp).Row

    ' 区分の入力ミスがあれば何も出力しない (基幹への取込事故防止)
    For r = 2 To lastRow
        If wsT.Cells(r, 1).Value <> "" Then
            kbn = Trim(wsT.Cells(r, 3).Value)
            If kbn <> "入庫" And kbn <> "出庫" And kbn <> "調整" Then
                MsgBox r & " 行目の区分が不正です: " & kbn
                Exit Sub
            End If
        End If
    Next r

    ' 品目マスタ (品番 -> 行番号)
    Set mst = CreateObject("Scripting.Dictionary")
    For r = 2 To wsM.Cells(wsM.Rows.Count, 1).End(xlUp).Row
        code = UCase(Trim(wsM.Cells(r, 1).Value))
        If code <> "" And Not mst.Exists(code) Then mst.Add code, r
    Next r

    ' 品番ごとの在庫数・在庫金額 (シートの行の順に積み上げる)
    Set dict = CreateObject("Scripting.Dictionary")
    Dim n As Long
    Dim codes() As String, zq() As Long, za() As Long
    n = 0
    For r = 2 To lastRow
        If wsT.Cells(r, 1).Value = "" Then GoTo NextRow
        If wsT.Cells(r, 1).Value > kijun Then GoTo NextRow
        code = UCase(Trim(wsT.Cells(r, 2).Value))
        If code = "" Then GoTo NextRow
        kbn = Trim(wsT.Cells(r, 3).Value)
        qty = wsT.Cells(r, 4).Value

        If Not dict.Exists(code) Then
            n = n + 1
            ReDim Preserve codes(1 To n): ReDim Preserve zq(1 To n): ReDim Preserve za(1 To n)
            codes(n) = code
            dict.Add code, n
        End If
        i = dict(code)

        Select Case kbn
        Case "入庫"
            za(i) = za(i) + CLng(qty * wsT.Cells(r, 5).Value)
            zq(i) = zq(i) + qty
        Case "出庫"
            ' 移動平均単価で払い出す。在庫以上の出庫は金額を全部落とす
            If zq(i) <= 0 Or qty >= zq(i) Then
                cost = za(i)
            Else
                cost = CLng(za(i) * qty / zq(i))
            End If
            za(i) = za(i) - cost
            zq(i) = zq(i) - qty
        Case "調整"
            ' 棚卸差異 (数量だけ直す。マイナスもある)
            zq(i) = zq(i) + qty
        End Select
NextRow:
    Next r

    Dim grand As Double, cum As Double
    grand = 0
    For i = 1 To n
        grand = grand + za(i)
    Next i
    If grand <= 0 Then
        MsgBox "基準日までの在庫がありません"
        Exit Sub
    End If

    ' 評価額の大きい順 (選択ソート)
    Dim idx() As Long
    ReDim idx(1 To n)
    For i = 1 To n
        idx(i) = i
    Next i
    For i = 1 To n - 1
        k = i
        For j = i + 1 To n
            If za(idx(j)) > za(idx(k)) Then k = j
        Next j
        If k <> i Then
            t = idx(i): idx(i) = idx(k): idx(k) = t
        End If
    Next i

    Dim f As Integer, nm As String, tanka As String, rank As String
    f = FreeFile
    Open ThisWorkbook.Path & "\zaiko_" & Format(kijun, "yyyymmdd") & ".txt" For Output As #f
    Print #f, "基準日" & vbTab & Format(kijun, "yyyy/mm/dd")
    Print #f, "品番" & vbTab & "品名" & vbTab & "入数" & vbTab & "在庫数" & vbTab & "ケース" & vbTab & "バラ" _
        & vbTab & "単価" & vbTab & "評価額" & vbTab & "構成比" & vbTab & "累計" & vbTab & "ランク"
    cum = 0
    For i = 1 To n
        k = idx(i)
        If mst.Exists(codes(k)) Then
            nm = wsM.Cells(mst(codes(k)), 2).Value
            irisu = wsM.Cells(mst(codes(k)), 3).Value
        Else
            nm = "(未登録)"
            irisu = 0
        End If
        If irisu <= 0 Then irisu = 1
        If zq(k) > 0 Then
            tanka = Format(za(k) / zq(k), "#,##0.00")
        Else
            tanka = "-"
        End If
        cum = cum + za(k)
        If cum / grand <= 0.7 Then
            rank = "A"
        ElseIf cum / grand <= 0.9 Then
            rank = "B"
        Else
            rank = "C"
        End If
        Print #f, codes(k) & vbTab & nm & vbTab & irisu & vbTab & zq(k) & vbTab & (zq(k) \ irisu) _
            & vbTab & (zq(k) Mod irisu) & vbTab & tanka & vbTab & Format(za(k), "#,##0") _
            & vbTab & Format(za(k) / grand, "0.0%") & vbTab & Format(cum / grand, "0.0%") & vbTab & rank
    Next i
    Print #f, "合計" & vbTab & n & "品目" & vbTab & vbTab & vbTab & vbTab & vbTab & vbTab _
        & Format(grand, "#,##0") & vbTab & "100.0%"
    Close #f

    MsgBox "zaiko_" & Format(kijun, "yyyymmdd") & ".txt を出力しました"
End Sub
