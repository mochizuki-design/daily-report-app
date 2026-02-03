import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import base64 # ★追加忘れずに！

# ... (タイトル設定などはそのまま) ...

# ==========================================
# Googleスプレッドシート接続設定
# ==========================================
@st.cache_resource
def get_worksheet():
    # --- クラウド対応：Base64エンコードされた鍵を復元する ---
    if not os.path.exists('secrets.json'):
        # Secretsに 'gcp_encoded' がある場合（今回の最強パターン）
        if 'gcp_encoded' in st.secrets:
            # 英数字の塊を、元のJSONに戻してファイル作成
            decoded_bytes = base64.b64decode(st.secrets['gcp_encoded'])
            with open('secrets.json', 'wb') as f:
                f.write(decoded_bytes)
        
        # (念のため以前のパターンも残すならここですが、今回は↑だけでOK)

    # 2つのAPIを操作する権限を設定
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('secrets.json', scope)
    client = gspread.authorize(creds)
    
    # スプレッドシートを開く
    sheet = client.open("daily_report_db").sheet1
    return sheet

# ... (以下、try接続処理などはそのまま) ...

# 接続を試みる（失敗したらエラーを表示）
try:
    worksheet = get_worksheet()
    st.success("✅ Googleスプレッドシートに接続成功！")
except Exception as e:
    st.error(f"接続エラー: {e}")
    st.stop() # 接続できない場合はここで停止

# --- タブを作成 ---
tab1, tab2 = st.tabs(["✍️ 本日の作成", "🔍 クラウド履歴"])

# ==========================================
# タブ1：本日の作成
# ==========================================
with tab1:
    today_str = datetime.now().strftime('%Y-%m-%d')
    st.subheader(f"日付: {today_str}")

    # --- 初期データ ---
    if "todo_df" not in st.session_state:
        st.session_state.todo_df = pd.DataFrame(
            [{"完了": False, "タスク": "メールチェック"}, {"完了": False, "タスク": ""}],
        )
    if "obstacle_df" not in st.session_state:
        st.session_state.obstacle_df = pd.DataFrame(
            [{"完了": False, "内容": ""}]
        )

    # --- 入力フォーム ---
    st.write("#### ■ 本日のTODO")
    edited_todo = st.data_editor(
        st.session_state.todo_df,
        num_rows="dynamic",
        column_config={
            "完了": st.column_config.CheckboxColumn("完了", default=False),
            "タスク": st.column_config.TextColumn("タスク", width="large", required=True)
        },
        use_container_width=True,
        key="todo_editor"
    )

    st.write("#### ■ 障害リスト")
    edited_obstacle = st.data_editor(
        st.session_state.obstacle_df,
        num_rows="dynamic",
        column_config={
            "完了": st.column_config.CheckboxColumn("解決", default=False),
            "内容": st.column_config.TextColumn("内容", width="large")
        },
        use_container_width=True,
        key="obstacle_editor"
    )

    st.write("#### ■ 本日の振り返り")
    reflection = st.text_area("振り返り", height=150, placeholder="2〜3行で...", label_visibility="collapsed")

    st.write("#### ■ 会議・会話メモ")
    memo = st.text_area("メモ", height=400, placeholder="詳細なメモ...", label_visibility="collapsed")

    # --- 保存ボタン（スプレッドシートへ送信） ---
    if st.button("クラウドに保存する", type="primary"):
        # 1. データを文字列に変換する（セルに入れるため）
        todo_text = ""
        for index, row in edited_todo.iterrows():
            if row["タスク"]:
                mark = "✅" if row["完了"] else "⬜"
                todo_text += f"{mark} {row['タスク']}\n"
        
        obs_text = ""
        for index, row in edited_obstacle.iterrows():
            if row["内容"]:
                mark = "✅" if row["完了"] else "⬜"
                obs_text += f"{mark} {row['内容']}\n"
        
        # 2. 保存する行データを作成
        # カラム順: [日付, TODO, 障害, 振り返り, メモ]
        row_data = [today_str, todo_text, obs_text, reflection, memo]
        
        # 3. スプレッドシートに追加
        try:
            worksheet.append_row(row_data)
            st.success(f"スプレッドシートに保存しました！ ({today_str})")
            st.balloons() # お祝いのエフェクト
        except Exception as e:
            st.error(f"保存に失敗しました: {e}")


# ==========================================
# タブ2：クラウド履歴・編集
# ==========================================
with tab2:
    st.subheader("スプレッドシートのデータを閲覧・編集")
    
    if st.button("🔄 最新データを読み込む"):
        st.cache_data.clear()
        st.rerun()

    # データを取得
    try:
        # 全データを取得
        data = worksheet.get_all_values()
        
        if len(data) <= 1:
            st.info("まだデータがありません。")
        else:
            # Pandas DataFrameにする
            df = pd.DataFrame(data[1:], columns=data[0])
            
            # 日付でソート
            df = df[df["日付"] != ""]
            df = df.sort_values(by="日付", ascending=False)
            
            # 選択ボックス
            report_list = df["日付"].tolist()
            selected_date = st.selectbox("日付を選択", report_list)
            
            if selected_date:
                # 選択された行データを取得
                row = df[df["日付"] == selected_date].iloc[0]

                st.divider()

                # --- 編集モードスイッチ ---
                is_edit_mode = st.toggle(f"✏️ {selected_date} の日報を編集する")

                if is_edit_mode:
                    # 編集用フォーム
                    new_todo = st.text_area("TODO (リスト形式)", value=row["TODO"], height=150)
                    new_obs = st.text_area("障害リスト", value=row["障害リスト"], height=100)
                    new_ref = st.text_area("振り返り", value=row["振り返り"], height=100)
                    new_memo = st.text_area("会議メモ", value=row["会議メモ"], height=300)

                    if st.button("変更を上書き保存する", type="primary"):
                        try:
                            # 1. スプレッドシート上でその日付の場所（行）を探す
                            cell = worksheet.find(selected_date)
                            row_number = cell.row
                            
                            # 2. その行を更新する
                            # カラム順: [日付, TODO, 障害, 振り返り, メモ]
                            worksheet.update(f"A{row_number}:E{row_number}", [[selected_date, new_todo, new_obs, new_ref, new_memo]])
                            
                            st.success("修正内容をスプレッドシートに反映しました！")
                            st.balloons()
                            
                            # 少し待ってからリロード（反映確認用）
                            st.cache_data.clear()
                        except Exception as e:
                            st.error(f"更新エラー: {e}")

                else:
                    # 閲覧モード
                    st.markdown(f"### 📅 {row['日付']}")
                    st.markdown("#### ■ 本日のTODO")
                    st.text(row["TODO"])
                    st.markdown("#### ■ 障害リスト")
                    st.text(row["障害リスト"])
                    st.markdown("#### ■ 本日の振り返り")
                    st.write(row["振り返り"])
                    st.markdown("#### ■ 会議・会話メモ")
                    st.write(row["会議メモ"])
                
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")