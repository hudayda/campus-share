from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'super_secret_social_responsibility_key'

REQ_FILE = 'requests.csv'
USER_FILE = 'users.csv'
MSG_FILE = 'messages.csv'

def load_df(file_path, columns):
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return pd.read_csv(file_path)
    return pd.DataFrame(columns=columns)

@app.route('/')
def index_page():
    if 'username' in session:
        return redirect(url_for('feed_page'))
    return render_template('index.html')

@app.route('/feed')
def feed_page():
    if 'username' not in session: return redirect(url_for('index_page'))
    df = load_df(REQ_FILE, ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type'])
    
    # Eğer eski verilerde 'type' sütunu yoksa hata vermemesi için dolduruyoruz
    if 'type' not in df.columns:
        df['type'] = 'İhtiyaç Talebi'
        
    reqs = df.to_dict(orient='records')
    
    # İstatistikler (Hocaya sunum için harika göstergeler)
    total_helped = len(df[df['status'].str.contains('Completed|Kutudan', na=False)])
    active_in_box = len(df[df['status'].str.contains('Box|Kutuda', na=False)])
    
    return render_template('feed.html', requests=reqs, total_helped=total_helped, active_in_box=active_in_box)

@app.route('/post')
def post_page():
    if 'username' not in session: return redirect(url_for('index_page'))
    return render_template('post.html')

@app.route('/chat/<int:req_id>')
def chat_page(req_id):
    if 'username' not in session: return redirect(url_for('index_page'))
    df = load_df(REQ_FILE, ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type'])
    req_data = df[df['id'] == req_id]
    if req_data.empty: return "İlan bulunamadı", 404
    return render_template('chat.html', req=req_data.iloc[0].to_dict())

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index_page'))

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    username = request.form.get('username')
    password = request.form.get('password')
    df = load_df(USER_FILE, ['username', 'password'])
    if username in df['username'].values:
        return "Bu kullanıcı adı veya e-posta zaten kayıtlı!", 400
    new_user = pd.DataFrame([{'username': username, 'password': password}])
    df = pd.concat([df, new_user], ignore_index=True)
    df.to_csv(USER_FILE, index=False)
    session['username'] = username
    return redirect(url_for('feed_page'))

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    username = request.form.get('username')
    password = request.form.get('password')
    df = load_df(USER_FILE, ['username', 'password'])
    user_check = df[(df['username'] == username) & (df['password'] == str(password))]
    if not user_check.empty:
        session['username'] = username
        return redirect(url_for('feed_page'))
    return "Hatalı giriş bilgileri!", 401

@app.route('/api/requests/', methods=['GET', 'POST'])
def api_requests():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        post_type = request.form.get('type', 'İhtiyaç Talebi') # İhtiyaç mı Bağış mı?
        
        df = load_df(REQ_FILE, ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type'])
        next_id = int(df['id'].max() + 1) if not df.empty else 1
        
        new_req = {
            'id': next_id, 'title': title, 'description': description, 'category': category,
            'status': 'Beklemede', 'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M'), 'helper_id': '', 'type': post_type
        }
        df = pd.concat([df, pd.DataFrame([new_req])], ignore_index=True)
        df.to_csv(REQ_FILE, index=False)
        return redirect(url_for('feed_page'))
    else:
        df = load_df(REQ_FILE, ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type'])
        return jsonify(df.to_dict(orient='records'))

@app.route('/api/requests/<int:req_id>/offer/', methods=['POST'])
def api_make_offer(req_id):
    df = load_df(REQ_FILE, ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type'])
    if req_id in df['id'].values:
        df.loc[df['id'] == req_id, 'status'] = 'Süreç Başlatıldı'
        df.loc[df['id'] == req_id, 'helper_id'] = session.get('username', 'Anonim Paydaş')
        df.to_csv(REQ_FILE, index=False)
    return redirect(url_for('chat_page', req_id=req_id))

@app.route('/api/requests/<int:req_id>/messages/', methods=['GET', 'POST'])
def api_messages(req_id):
    if request.method == 'POST':
        msg_text = request.form.get('message')
        df = load_df(MSG_FILE, ['request_id', 'sender', 'message', 'timestamp'])
        new_msg = {
            'request_id': req_id, 'sender': session.get('username', 'Anonim'),
            'message': msg_text, 'timestamp': datetime.now().strftime('%H:%M')
        }
        df = pd.concat([df, pd.DataFrame([new_msg])], ignore_index=True)
        df.to_csv(MSG_FILE, index=False)
        return redirect(url_for('chat_page', req_id=req_id))
    else:
        df = load_df(MSG_FILE, ['request_id', 'sender', 'message', 'timestamp'])
        filtered = df[df['request_id'] == req_id]
        return jsonify(filtered.to_dict(orient='records'))

@app.route('/api/requests/<int:req_id>/drop/', methods=['POST'])
def api_drop_item(req_id):
    df = load_df(REQ_FILE, ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type'])
    if req_id in df['id'].values:
        df.loc[df['id'] == req_id, 'status'] = 'Kutuya Bırakıldı'
        df.loc[df['id'] == req_id, 'timestamp'] = datetime.now().strftime('%d.%m.%Y %H:%M')
        df.to_csv(REQ_FILE, index=False)
    return redirect(url_for('chat_page', req_id=req_id))

@app.route('/api/requests/<int:req_id>/pickup/', methods=['POST'])
def api_confirm_pickup(req_id):
    df = load_df(REQ_FILE, ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type'])
    if req_id in df['id'].values:
        df.loc[df['id'] == req_id, 'status'] = 'Kutudan Teslim Alındı (Tamamlandı)'
        df.loc[df['id'] == req_id, 'timestamp'] = datetime.now().strftime('%d.%m.%Y %H:%M')
        df.to_csv(REQ_FILE, index=False)
    return redirect(url_for('feed_page'))

if __name__ == '__main__':
    app.run(debug=True, port=80)
