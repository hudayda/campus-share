from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import csv
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'super_secret_social_responsibility_key'

REQ_FILE = 'requests.csv'
USER_FILE = 'users.csv'
MSG_FILE = 'messages.csv'

# CSV Dosyalarını Pandas olmadan güvenle okuyup yazan yardımcı fonksiyonlar
def read_csv_rows(file_path, fieldnames):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return []
    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def write_csv_rows(file_path, fieldnames, rows):
    with open(file_path, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def append_csv_row(file_path, fieldnames, row):
    file_exists = os.path.exists(file_path) and os.path.getsize(file_path) > 0
    with open(file_path, mode='a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

@app.route('/')
def index_page():
    if 'username' in session:
        return redirect(url_for('feed_page'))
    return render_template('index.html')

@app.route('/feed')
def feed_page():
    if 'username' not in session: return redirect(url_for('index_page'))
    reqs = read_csv_rows(REQ_FILE, ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type'])
    
    total_helped = sum(1 for r in reqs if 'Completed' in r.get('status', '') or 'Teslim' in r.get('status', ''))
    active_in_box = sum(1 for r in reqs if 'Kutu' in r.get('status', ''))
    
    return render_template('feed.html', requests=reqs, total_helped=total_helped, active_in_box=active_in_box)

@app.route('/post')
def post_page():
    if 'username' not in session: return redirect(url_for('index_page'))
    return render_template('post.html')

@app.route('/chat/<int:req_id>')
def chat_page(req_id):
    if 'username' not in session: return redirect(url_for('index_page'))
    reqs = read_csv_rows(REQ_FILE, ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type'])
    req_data = next((r for r in reqs if int(r['id']) == req_id), None)
    if not req_data: return "İlan bulunamadı", 404
    return render_template('chat.html', req=req_data)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index_page'))

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    username = request.form.get('username')
    password = request.form.get('password')
    users = read_csv_rows(USER_FILE, ['username', 'password'])
    
    if any(u['username'] == username for u in users):
        return "Bu kullanıcı adı veya e-posta zaten kayıtlı!", 400
        
    append_csv_row(USER_FILE, ['username', 'password'], {'username': username, 'password': password})
    session['username'] = username
    return redirect(url_for('feed_page'))

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    username = request.form.get('username')
    password = request.form.get('password')
    users = read_csv_rows(USER_FILE, ['username', 'password'])
    
    user_check = any(u['username'] == username and str(u['password']) == str(password) for u in users)
    if user_check:
        session['username'] = username
        return redirect(url_for('feed_page'))
    return "Hatalı giriş bilgileri!", 401

@app.route('/api/requests/', methods=['GET', 'POST'])
def api_requests():
    fields = ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type']
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        post_type = request.form.get('type', 'İhtiyaç Talebi')
        
        reqs = read_csv_rows(REQ_FILE, fields)
        next_id = max([int(r['id']) for r in reqs]) + 1 if reqs else 1
        
        new_req = {
            'id': next_id, 'title': title, 'description': description, 'category': category,
            'status': 'Beklemede', 'timestamp': datetime.now().strftime('%d.%m.%Y %H:%M'), 'helper_id': '', 'type': post_type
        }
        append_csv_row(REQ_FILE, fields, new_req)
        return redirect(url_for('feed_page'))
    else:
        reqs = read_csv_rows(REQ_FILE, fields)
        return jsonify(reqs)

@app.route('/api/requests/<int:req_id>/offer/', methods=['POST'])
def api_make_offer(req_id):
    fields = ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type']
    reqs = read_csv_rows(REQ_FILE, fields)
    for r in reqs:
        if int(r['id']) == req_id:
            r['status'] = 'Süreç Başlatıldı'
            r['helper_id'] = session.get('username', 'Anonim Paydaş')
    write_csv_rows(REQ_FILE, fields, reqs)
    return redirect(url_for('chat_page', req_id=req_id))

@app.route('/api/requests/<int:req_id>/messages/', methods=['GET', 'POST'])
def api_messages(req_id):
    fields = ['request_id', 'sender', 'message', 'timestamp']
    if request.method == 'POST':
        msg_text = request.form.get('message')
        new_msg = {
            'request_id': req_id, 'sender': session.get('username', 'Anonim'),
            'message': msg_text, 'timestamp': datetime.now().strftime('%H:%M')
        }
        append_csv_row(MSG_FILE, fields, new_msg)
        return redirect(url_for('chat_page', req_id=req_id))
    else:
        msgs = read_csv_rows(MSG_FILE, fields)
        filtered = [m for m in msgs if int(m['request_id']) == req_id]
        return jsonify(filtered)

@app.route('/api/requests/<int:req_id>/drop/', methods=['POST'])
def api_drop_item(req_id):
    fields = ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type']
    reqs = read_csv_rows(REQ_FILE, fields)
    for r in reqs:
        if int(r['id']) == req_id:
            r['status'] = 'Kutuya Bırakıldı'
            r['timestamp'] = datetime.now().strftime('%d.%m.%Y %H:%M')
    write_csv_rows(REQ_FILE, fields, reqs)
    return redirect(url_for('chat_page', req_id=req_id))

@app.route('/api/requests/<int:req_id>/pickup/', methods=['POST'])
def api_confirm_pickup(req_id):
    fields = ['id', 'title', 'description', 'category', 'status', 'timestamp', 'helper_id', 'type']
    reqs = read_csv_rows(REQ_FILE, fields)
    for r in reqs:
        if int(r['id']) == req_id:
            r['status'] = 'Kutudan Teslim Alındı (Tamamlandı)'
            r['timestamp'] = datetime.now().strftime('%d.%m.%Y %H:%M')
    write_csv_rows(REQ_FILE, fields, reqs)
    return redirect(url_for('feed_page'))

if __name__ == '__main__':
    app.run(debug=True, port=80)
