Attribute VB_Name = "Module1"
Option Explicit

' ============================================================
'  顧客マスタ整形マクロ
'  シート「顧客」(1行目は見出し)
'     A:顧客コード  B:氏名  C:フリガナ  D:住所  E:電話  F:ポイント
'  基幹システム取込用に整形して customers_load.txt (タブ区切り) に出す。
'  旧システムの制約: 氏名は 20 バイトまで、フリガナは半角カナ。
'  2018/11 情報システム課 作成 / 2024/02 法人フラグを追加
' ============================================================

Public Sub 顧客マスタ整形()
    Dim ws As Worksheet
    Dim lastRow As Long, r As Long, i As Long
    Dim code As String, nm As String, kana As String, addr As String
    Dim pref As String, rest As String, bldg As String
    Dim t As String, c As String, digits As String, tel As String
    Dim corp As String, sp As Long
    Dim f As Integer

    Set ws = ThisWorkbook.Worksheets("顧客")
    lastRow = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row

    f = FreeFile
    Open ThisWorkbook.Path & "\customers_load.txt" For Output As #f
    Print #f, "CODE" & vbTab & "NAME" & vbTab & "CORP" & vbTab & "KANA" & vbTab & "PREF" _
        & vbTab & "ADDR" & vbTab & "BLDG" & vbTab & "TEL" & vbTab & "POINT"

    For r = 2 To lastRow
        ' --- 顧客コード: C + 数字4桁 以外は取り込まない
        code = Trim(ws.Cells(r, 1).Value)
        If Not code Like "C####" Then
            Print #f, code & vbTab & "ERROR コード不正"
            GoTo NextRow
        End If

        ' --- 氏名: 全角スペースを半角に、連続スペースは1つに
        nm = Trim(Replace(ws.Cells(r, 2).Value, "　", " "))
        Do While InStr(nm, "  ") > 0
            nm = Replace(nm, "  ", " ")
        Loop
        If nm Like "*株式会社*" Or nm Like "*(株)*" Or nm Like "*（株）*" Then
            corp = "1"
        Else
            corp = "0"
        End If
        ' 旧システムは 20 バイト (Shift_JIS) まで
        Do While LenB(StrConv(nm, vbFromUnicode)) > 20
            nm = Left(nm, Len(nm) - 1)
        Loop

        ' --- フリガナ: ひらがなはカタカナにしてから半角に
        kana = StrConv(StrConv(Trim(ws.Cells(r, 3).Value), vbKatakana), vbNarrow)

        ' --- 住所: 都道府県 / 市区町村番地 / 建物名 (最後のスペースの後ろ)
        addr = Replace(Trim(ws.Cells(r, 4).Value), "　", " ")
        If Mid(addr, 4, 1) = "県" Then
            pref = Left(addr, 4)
        Else
            pref = Left(addr, 3)
        End If
        rest = Mid(addr, Len(pref) + 1)
        sp = InStrRev(rest, " ")
        If sp > 0 Then
            bldg = Trim(Mid(rest, sp + 1))
            rest = Trim(Left(rest, sp - 1))
        Else
            bldg = ""
        End If
        rest = Replace(rest, "－", "-")

        ' --- 電話: 数字だけ取り出して ハイフン区切りに
        t = StrConv(ws.Cells(r, 5).Value, vbNarrow)
        digits = ""
        For i = 1 To Len(t)
            c = Mid(t, i, 1)
            If c Like "#" Then digits = digits & c
        Next i
        If Len(digits) = 10 And (Left(digits, 2) = "03" Or Left(digits, 2) = "06") Then
            tel = Left(digits, 2) & "-" & Mid(digits, 3, 4) & "-" & Mid(digits, 7)
        ElseIf Len(digits) = 10 Then
            tel = Left(digits, 3) & "-" & Mid(digits, 4, 3) & "-" & Mid(digits, 7)
        ElseIf Len(digits) = 11 Then
            tel = Left(digits, 3) & "-" & Mid(digits, 4, 4) & "-" & Mid(digits, 8)
        Else
            tel = ""
        End If

        Print #f, code & vbTab & nm & vbTab & corp & vbTab & kana & vbTab & pref & vbTab & rest _
            & vbTab & bldg & vbTab & tel & vbTab & CStr(Val(ws.Cells(r, 6).Value))
NextRow:
    Next r
    Close #f
    MsgBox "customers_load.txt を出力しました"
End Sub
