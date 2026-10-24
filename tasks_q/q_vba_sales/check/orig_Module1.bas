Attribute VB_Name = "Module1"
Option Explicit

' ============================================================
'  月次売上集計マクロ
'  シート「売上明細」(1行目は見出し)
'     A:日付  B:担当者  C:商品  D:数量  E:単価  F:値引率
'  指定月の担当者別集計を、ブックと同じフォルダの
'  report_yyyymm.txt (タブ区切り) に書き出す。
'  2019/04 経理課 作成 / 2023/10 構成比の列を追加
' ============================================================

Public Sub 月次売上集計()
    Dim ws As Worksheet
    Dim lastRow As Long, r As Long, i As Long, j As Long, k As Long
    Dim target As String, nm As String
    Dim dict As Object
    Dim qty As Long, amt As Long
    Dim grand As Double, sumCnt As Long, sumQty As Long

    target = InputBox("対象月を yyyymm で入力", "月次売上集計", Format(Date, "yyyymm"))
    If Len(target) <> 6 Then Exit Sub

    Set ws = ThisWorkbook.Worksheets("売上明細")
    Set dict = CreateObject("Scripting.Dictionary")
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row

    ' 担当者ごとの 件数・数量・売上 (配列は 1 始まり、担当者は最初に出てきた順)
    Dim n As Long
    Dim names() As String, cnt() As Long, qsum() As Long, tot() As Double
    n = 0
    For r = 2 To lastRow
        nm = Trim(ws.Cells(r, 2).Value)
        If nm = "" Then GoTo NextRow
        If Format(ws.Cells(r, 1).Value, "yyyymm") <> target Then GoTo NextRow

        qty = ws.Cells(r, 4).Value
        ' 値引後の金額 (円未満は CLng で丸める)
        amt = CLng(qty * ws.Cells(r, 5).Value * (1 - ws.Cells(r, 6).Value))

        If Not dict.Exists(nm) Then
            n = n + 1
            ReDim Preserve names(1 To n): ReDim Preserve cnt(1 To n)
            ReDim Preserve qsum(1 To n): ReDim Preserve tot(1 To n)
            names(n) = nm
            dict.Add nm, n
        End If
        i = dict(nm)
        cnt(i) = cnt(i) + 1
        qsum(i) = qsum(i) + qty
        tot(i) = tot(i) + amt
        grand = grand + amt
        sumCnt = sumCnt + 1
        sumQty = sumQty + qty
NextRow:
    Next r
    If n = 0 Then
        MsgBox "対象月のデータがありません"
        Exit Sub
    End If

    ' 売上の多い順に並べ替え (バブルソート)
    Dim idx() As Long, t As Long
    ReDim idx(1 To n)
    For i = 1 To n
        idx(i) = i
    Next i
    For i = 1 To n - 1
        For j = 1 To n - i
            If tot(idx(j)) <= tot(idx(j + 1)) Then
                t = idx(j): idx(j) = idx(j + 1): idx(j + 1) = t
            End If
        Next j
    Next i

    ' 出力 (ケースは 12 個入り)
    Dim f As Integer
    f = FreeFile
    Open ThisWorkbook.Path & "\report_" & target & ".txt" For Output As #f
    Print #f, "担当者" & vbTab & "件数" & vbTab & "数量" & vbTab & "ケース" & vbTab & "バラ" _
        & vbTab & "売上" & vbTab & "平均" & vbTab & "構成比"
    For i = 1 To n
        k = idx(i)
        Print #f, names(k) & vbTab & cnt(k) & vbTab & qsum(k) & vbTab & (qsum(k) \ 12) _
            & vbTab & (qsum(k) Mod 12) & vbTab & Format(tot(k), "#,##0") _
            & vbTab & Format(Round(tot(k) / cnt(k), 0), "#,##0") _
            & vbTab & Format(tot(k) / grand, "0.0%")
    Next i
    Print #f, "合計" & vbTab & sumCnt & vbTab & sumQty & vbTab & (sumQty \ 12) _
        & vbTab & (sumQty Mod 12) & vbTab & Format(grand, "#,##0") _
        & vbTab & Format(Round(grand / sumCnt, 0), "#,##0") & vbTab & "100.0%"
    Close #f

    MsgBox "report_" & target & ".txt を出力しました"
End Sub
