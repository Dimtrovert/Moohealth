from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for
from threading import Thread
import time, datetime, random
import csv
import io
import pandas as pd
import os

app = Flask(__name__)

# Data Sapi (SiTernak style)
cow_data = {
    'suhu': 38.5,
    'jantung_bpm': 70,
    'status': 'SEHAT',
    'last_update': None
}

# Menyimpan riwayat data untuk grafik dan CSV
history_data = []

# Path file CSV input dan output
input_file = "c:/Users/dimas/Downloads/Moohealth.csv"
output_file = "c:/Users/dimas/Downloads/Moohealth.csv"

# Periksa apakah file input ada
if not os.path.exists(input_file):
    # Jika file tidak ada, buat file CSV kosong dengan header yang sesuai
    with open(input_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Suhu (C)', 'Jantung (BPM)'])
    print(f"File {input_file} tidak ditemukan. File baru telah dibuat dengan header default.")

# Membaca file CSV
data = pd.read_csv(input_file)

# Memilih hanya kolom 'Suhu (C)' dan 'Jantung (BPM)'
data_cleaned = data[['Suhu (C)', 'Jantung (BPM)']]

# Menyimpan data yang telah dibersihkan ke file baru
data_cleaned.to_csv(output_file, index=False)

print(f"Data dengan kolom yang dipilih telah disimpan ke {output_file}")

# Add a secret key for session management
app.secret_key = 'your_secret_key'

@app.route('/')
def index():
    return render_template('index.html')

# (Endpoint opsional untuk login)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Simple authentication logic (replace with database validation as needed)
        if username == 'superadmin' and password == 'password':
            session['user'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid username or password')

    return render_template('login.html')

@app.before_request
def restrict_dashboard_access():
    allowed_routes = ['login', 'static']
    if 'user' not in session and request.endpoint not in allowed_routes:
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user', None)  # Remove user session
    return redirect(url_for('login'))  # Redirect to login page

# --- API Endpoints ---

@app.route('/api/cow-data', methods=['GET'])
def get_cow_data():
    return jsonify(cow_data)

@app.route('/api/history', methods=['GET'])
def get_history():
    # Mengembalikan 20 data terakhir untuk grafik
    return jsonify(history_data[-20:])

@app.route('/api/download-csv', methods=['GET'])
def download_csv():
    # Fitur Download seperti di "SiTernak"
    limit = request.args.get('limit', default=1000, type=int)
    data_to_export = history_data[-limit:] if limit > 0 else history_data
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Timestamp', 'Suhu (C)', 'Jantung (BPM)', 'Status'])
    for row in data_to_export:
        cw.writerow([row['timestamp'], row['suhu'], row['jantung_bpm'], row['status']])
        
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=MooHealth_Data.csv"}
    )

# --- ESP32 Receiver Endpoint ---
# Anda akan menggunakan endpoint ini di kode ESP32 Anda (POST JSON)
@app.route('/esp32/sensor_sapi', methods=['POST'])
def receive_cow_sensor():
    try:
        data = request.get_json()
        cow_data.update({
            'suhu': data.get('suhu', cow_data['suhu']),
            'jantung_bpm': data.get('jantung_bpm', cow_data['jantung_bpm']),
            'status': data.get('status', 'SEHAT'),
            'last_update': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Simpan ke riwayat
        history_data.append({
            'timestamp': cow_data['last_update'],
            'suhu': cow_data['suhu'],
            'jantung_bpm': cow_data['jantung_bpm'],
            'status': cow_data['status']
        })
        # Batasi riwayat di memori (misal 5000) agar server tidak berat
        if len(history_data) > 5000:
            history_data.pop(0)

        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400


# --- Dummy Data Generator (Hanya untuk testing visual) ---
def dummy_sensor_loop():
    while True:
        # Simulasi fluktuasi data sapi
        cow_data['suhu'] = round(38.0 + random.uniform(-0.5, 0.8), 2)
        cow_data['jantung_bpm'] = int(70 + random.uniform(-5, 10))
        cow_data['last_update'] = datetime.datetime.now().strftime('%H:%M:%S')
        
        # Logika status sederhana
        if cow_data['suhu'] > 39.0:
            cow_data['status'] = 'PERHATIAN (SUHU TINGGI)'
        else:
            cow_data['status'] = 'SEHAT'

        history_data.append({
            'timestamp': cow_data['last_update'],
            'suhu': cow_data['suhu'],
            'jantung_bpm': cow_data['jantung_bpm'],
            'status': cow_data['status']
        })
        if len(history_data) > 5000:
            history_data.pop(0)
            
        time.sleep(3) # Update tiap 3 detik

if __name__ == '__main__':
    # Jalankan thread dummy data (Hapus baris ini jika sudah connect ESP32 beneran)
    Thread(target=dummy_sensor_loop, daemon=True).start()
    
    app.run(host='0.0.0.0', port=5000, debug=True)