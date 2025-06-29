from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook
from io import BytesIO
from flask import send_file
import os
from werkzeug.utils import secure_filename
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Konfigurasi MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  # ganti sesuai password mysql kamu
app.config['MYSQL_DB'] = 'restoran_db'

mysql = MySQL(app)

# Route home (redirect ke login)
@app.route('/') # Route untuk halaman utama
def home(): # berfungsi untuk mengarahkan ke halaman login
    return redirect(url_for('login')) # berfungsi untuk mengarahkan ke halaman login

# Route login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close()

        if user:
            # Pastikan password ada di index 2, sesuaikan dengan urutan kolom di tabel
            if check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['role'] = user[4]
                flash('Login berhasil!', 'success')
                if user[4] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('pelanggan_dashboard'))
            else:
                flash('Password salah!', 'danger')
        else:
            flash('Username tidak ditemukan!', 'danger')
    return render_template('auth/login.html')

# Route register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']

        cur = mysql.connection.cursor()
        # cek username sudah ada atau belum
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        existing_user = cur.fetchone()
        if existing_user:
            flash('Username sudah terdaftar!', 'danger')
            cur.close()
            return redirect(url_for('register'))

        cur.execute("INSERT INTO users (username, password, email, role) VALUES (%s, %s, %s, %s)",
                    (username, password, email, role))
        mysql.connection.commit()
        cur.close()

        flash('Registrasi berhasil, silakan login.', 'success')
        return redirect(url_for('login'))

    return render_template('auth/register.html')

# Dashboard admin - VERSI LENGKAP DENGAN STATISTIK
# Ganti bagian dashboard admin di main.py
# Cari fungsi admin_dashboard() dan ganti bagian query pendapatan hari ini

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'role' in session and session['role'] == 'admin':
        try:
            cur = mysql.connection.cursor()
            
            # Tanggal hari ini
            today_str = date.today().strftime('%Y-%m-%d')
            
            # 1. Total pesanan hari ini
            cur.execute("""
                SELECT COUNT(*) FROM pesanan 
                WHERE DATE(created_at) = %s
            """, (today_str,))
            result = cur.fetchone()
            today_orders = result[0] if result else 0
            
            # 2. Pendapatan hari ini - DIPERBAIKI untuk konsisten dengan laporan
            cur.execute("""
                SELECT COALESCE(SUM(p.jumlah * m.harga), 0) 
                FROM pesanan p
                JOIN menu m ON p.id_menu = m.id
                WHERE DATE(p.created_at) = %s AND p.status = 'selesai'
            """, (today_str,))
            result = cur.fetchone()
            today_revenue = int(result[0]) if result and result[0] else 0
            
            # 3. Total pesanan menunggu
            cur.execute("SELECT COUNT(*) FROM pesanan WHERE status = 'menunggu'")
            result = cur.fetchone()
            total_menunggu = result[0] if result else 0
            
            # 4. Total transaksi keseluruhan
            cur.execute("SELECT COUNT(*) FROM pesanan")
            result = cur.fetchone()
            total_transaksi = result[0] if result else 0
            
            # 5. Total item terjual
            cur.execute("SELECT COALESCE(SUM(jumlah), 0) FROM pesanan WHERE status = 'selesai'")
            result = cur.fetchone()
            total_items = result[0] if result else 0
            
            # 6. Total penjualan keseluruhan - SESUAI DENGAN LAPORAN
            cur.execute("""
                SELECT COALESCE(SUM(p.jumlah * m.harga), 0) 
                FROM pesanan p
                JOIN menu m ON p.id_menu = m.id
                WHERE p.status = 'selesai'
            """)
            result = cur.fetchone()
            total_penjualan = int(result[0]) if result and result[0] else 0
            
            # 7. Aktivitas terbaru (5 pesanan terakhir)
            cur.execute("""
                SELECT p.id, u.username, p.created_at, p.status, 
                       (p.jumlah * m.harga) as total_harga, m.nama
                FROM pesanan p
                JOIN users u ON p.id_user = u.id
                JOIN menu m ON p.id_menu = m.id
                ORDER BY p.created_at DESC
                LIMIT 5
            """)
            recent_orders = cur.fetchall()
            
            # Format aktivitas
            recent_activities = []
            for order in recent_orders:
                try:
                    # Jika created_at adalah datetime object
                    if isinstance(order[2], datetime):
                        time_str = order[2].strftime('%d/%m/%Y %H:%M')
                    else:
                        # Jika created_at adalah string
                        time_str = datetime.strptime(str(order[2]), '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
                except:
                    time_str = str(order[2]) if order[2] else 'N/A'
                    
                activity = {
                    'title': f'Pesanan #{order[0]} - {order[1]}',
                    'description': f'{order[5]} | Status: {order[3]} | Total: Rp {"{:,}".format(int(order[4]))}',
                    'time': time_str
                }
                recent_activities.append(activity)
            
            cur.close()
            
            # Data untuk template
            return render_template('admin/dashboard.html',
                today_orders=today_orders,
                today_revenue=today_revenue,
                total_menunggu=total_menunggu,
                total_transaksi=total_transaksi,
                total_items=total_items,
                total_penjualan=total_penjualan,  # Ini yang terhubung dengan laporan
                recent_activities=recent_activities,
                current_time=datetime.now(),
                last_backup='2 jam lalu'  # Placeholder untuk backup info
            )
            
        except Exception as e:
            print(f"Error in admin_dashboard: {e}")
            flash('Terjadi kesalahan saat memuat dashboard.', 'danger')
            # Data default jika error
            return render_template('admin/dashboard.html',
                today_orders=0,
                today_revenue=0,
                total_menunggu=0,
                total_transaksi=0,
                total_items=0,
                total_penjualan=0,
                recent_activities=[],
                current_time=datetime.now(),
                last_backup='N/A'
            )
    else:
        flash('Anda harus login sebagai admin!', 'danger')
        return redirect(url_for('login'))
    
# Dashboard pelanggan - PERBAIKAN
@app.route('/pelanggan/dashboard')
def pelanggan_dashboard():
    if 'role' in session and session['role'] == 'pelanggan':
        try:
            cur = mysql.connection.cursor()
            
            # Query untuk pesanan terbaru dengan total harga
            cur.execute("""
                SELECT p.id, m.nama, p.jumlah, p.status, p.created_at, (p.jumlah * m.harga) as total_harga
                FROM pesanan p
                JOIN menu m ON p.id_menu = m.id
                WHERE p.id_user = %s
                ORDER BY p.created_at DESC
                LIMIT 5
            """, (session['user_id'],))
            recent_orders = cur.fetchall()
            cur.close()
            
            return render_template('pelanggan/dashboard.html', 
                                current_time=datetime.now(),
                                recent_orders=recent_orders)  # Ubah nama variabel
                                
        except Exception as e:
            print(f"Error in pelanggan_dashboard: {e}")
            flash('Terjadi kesalahan saat memuat dashboard.', 'warning')
            return render_template('pelanggan/dashboard.html', 
                                current_time=datetime.now(),
                                recent_orders=[])  # Empty list jika error
    else:
        flash('Anda harus login sebagai pelanggan!', 'danger')
        return redirect(url_for('login'))

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Berhasil logout.', 'success')
    return redirect(url_for('login'))

# Pastikan sudah import
from flask import abort

# Fungsi cek admin login
def admin_required():
    if 'role' not in session or session['role'] != 'admin':
        flash('Anda harus login sebagai admin!', 'danger')
        return False
    return True

# ===== RUANG KERJA ADMIN ====== 
# Daftar menu makanan/minuman
@app.route('/admin/menu')
def menu_list():
    if not admin_required():
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    # Pilih kolom spesifik supaya urutan jelas: id, nama, kategori, harga
    cur.execute("SELECT id, nama, kategori, harga FROM menu ORDER BY kategori, nama")
    menus = cur.fetchall()
    cur.close()

    # menus berupa list tuple (id, nama, kategori, harga)
    return render_template('admin/menu_list.html', menus=menus)

@app.route('/admin/menu/tambah', methods=['GET', 'POST'])
def menu_tambah():
    if not admin_required():
        return redirect(url_for('login'))

    if request.method == 'POST':
        nama = request.form['nama']
        kategori = request.form['kategori']
        harga = request.form['harga']

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO menu (nama, kategori, harga) VALUES (%s, %s, %s)",
                    (nama, kategori, harga))
        mysql.connection.commit()
        cur.close()

        flash('Menu berhasil ditambahkan!', 'success')
        return redirect(url_for('menu_list'))

    return render_template('admin/menu_tambah.html')

# Edit menu
@app.route('/admin/menu/edit/<int:id>', methods=['GET', 'POST'])
def menu_edit(id):
    if not admin_required():
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        nama = request.form['nama']
        kategori = request.form['kategori']
        harga = request.form['harga']

        cur.execute("UPDATE menu SET nama=%s, kategori=%s, harga=%s WHERE id=%s", (nama, kategori, harga, id))
        mysql.connection.commit()
        cur.close()
        flash('Menu berhasil diperbarui!', 'success')
        return redirect(url_for('menu_list'))

    cur.execute("SELECT * FROM menu WHERE id = %s", (id,))
    menu = cur.fetchone()
    cur.close()
    return render_template('admin/menu_edit.html', menu=menu)

# Hapus menu
@app.route('/admin/menu/hapus/<int:id>', methods=['POST'])
def menu_hapus(id):
    if 'role' not in session or session['role'] != 'admin':
        flash('Akses ditolak', 'danger')
        return redirect(url_for('login'))

    try:
        cur = mysql.connection.cursor()
        
        # 1. Cek apakah menu ada
        cur.execute("SELECT nama FROM menu WHERE id = %s", (id,))
        menu = cur.fetchone()
        if not menu:
            flash('Menu tidak ditemukan!', 'danger')
            return redirect(url_for('menu_list'))
        
        menu_name = menu[0]
        
        # 2. Cek dependensi pesanan
        cur.execute("SELECT COUNT(*) FROM pesanan WHERE id_menu = %s", (id,))
        if cur.fetchone()[0] > 0:
            flash(f'Menu "{menu_name}" tidak bisa dihapus karena ada pesanan terkait', 'warning')
            return redirect(url_for('menu_list'))
        
        # 3. Eksekusi penghapusan
        cur.execute("DELETE FROM menu WHERE id = %s", (id,))
        mysql.connection.commit()
        
        flash(f'Menu "{menu_name}" berhasil dihapus!', 'success')
        
    except Exception as e:
        mysql.connection.rollback()
        app.logger.error(f'Gagal hapus menu: {str(e)}')
        flash(f'Gagal menghapus menu. Error: {str(e)}', 'danger')
        
    finally:
        if cur:
            cur.close()
    
    return redirect(url_for('menu_list'))

# Daftar pelanggan (role = 'pelanggan' saja)
@app.route('/admin/pelanggan')
def pelanggan_list():
    if not admin_required():
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username, email FROM users WHERE role = 'pelanggan' ORDER BY id")
    pelanggan = cur.fetchall()
    cur.close()
    return render_template('admin/pelanggan_list.html', pelanggan=pelanggan)

# Tambah pelanggan baru
@app.route('/admin/pelanggan/tambah', methods=['GET', 'POST'])
def pelanggan_tambah():
    if not admin_required():
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        email = request.form['email']
        role = 'pelanggan'  # otomatis role pelanggan

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (username, password, email, role) VALUES (%s, %s, %s, %s)",
                    (username, password, email, role))
        mysql.connection.commit()
        cur.close()
        flash('Pelanggan berhasil ditambahkan!', 'success')
        return redirect(url_for('pelanggan_list'))

    return render_template('admin/pelanggan_tambah.html')

# Edit pelanggan
@app.route('/admin/pelanggan/edit/<int:id>', methods=['GET', 'POST'])
def pelanggan_edit(id):
    if not admin_required():
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username, email FROM users WHERE id=%s AND role='pelanggan'", (id,))
    pelanggan = cur.fetchone()

    if not pelanggan:
        cur.close()
        flash('Pelanggan tidak ditemukan!', 'danger')
        return redirect(url_for('pelanggan_list'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']

        cur.execute("UPDATE users SET username=%s, email=%s WHERE id=%s AND role='pelanggan'",
                    (username, email, id))
        mysql.connection.commit()
        cur.close()
        flash('Pelanggan berhasil diupdate!', 'success')
        return redirect(url_for('pelanggan_list'))

    cur.close()
    return render_template('admin/pelanggan_edit.html', pelanggan=pelanggan)

# ===== RUANG KERJA PELANGGAN =====
@app.route('/pelanggan/menu')
def pelanggan_menu():
    if 'role' in session and session['role'] == 'pelanggan':
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM menu")
        data_menu = cur.fetchall()
        cur.close()
        return render_template('pelanggan/menu.html', menu=data_menu)
    return redirect(url_for('login'))

@app.route('/pelanggan/pesan/<int:id_menu>', methods=['GET', 'POST'])
def pelanggan_pesan(id_menu):
    if 'role' in session and session['role'] == 'pelanggan':
        if request.method == 'POST':
            jumlah = int(request.form['jumlah'])
            id_user = session['user_id']
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO pesanan (id_user, id_menu, jumlah, status) VALUES (%s, %s, %s, %s)",
                        (id_user, id_menu, jumlah, 'menunggu'))
            mysql.connection.commit()
            cur.close()
            flash('Pesanan berhasil dikirim.')
            return redirect(url_for('pelanggan_riwayat'))
        return render_template('pelanggan/form_pesan.html', id_menu=id_menu)
    return redirect(url_for('login'))

@app.route('/pelanggan/riwayat')
def pelanggan_riwayat():
    if 'role' in session and session['role'] == 'pelanggan':
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT pesanan.id, menu.nama, pesanan.jumlah, pesanan.status 
            FROM pesanan JOIN menu ON pesanan.id_menu = menu.id 
            WHERE pesanan.id_user = %s
        """, (session['user_id'],))
        riwayat = cur.fetchall()
        cur.close()
        return render_template('pelanggan/riwayat.html', riwayat=riwayat)
    return redirect(url_for('login'))

# ===== ROUTE BARU YANG DITAMBAHKAN =====
@app.route('/mulai-pesan')
def mulai_pesan():
    if 'role' in session and session['role'] == 'pelanggan':
        return render_template('mulai_pesan.html')
    else:
        flash('Anda harus login sebagai pelanggan!', 'danger')
        return redirect(url_for('login'))

@app.route('/riwayat-pesan')
def riwayat_pesan():
    if 'role' in session and session['role'] == 'pelanggan':
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT p.id, m.nama, p.jumlah, p.status, p.created_at, (p.jumlah * m.harga) as total_harga
            FROM pesanan p
            JOIN menu m ON p.id_menu = m.id 
            WHERE p.id_user = %s
            ORDER BY p.created_at DESC
        """, (session['user_id'],))
        riwayat = cur.fetchall()
        cur.close()
        return render_template('riwayat_pesan.html', riwayat=riwayat)
    else:
        flash('Anda harus login sebagai pelanggan!', 'danger')
        return redirect(url_for('login'))

@app.route('/edit-profil', methods=['GET', 'POST'])
def edit_profil():
    if 'role' in session:
        if request.method == 'POST':
            username = request.form['username']
            email = request.form['email']
            password_lama = request.form.get('password_lama')
            password_baru = request.form.get('password_baru')
            
            cur = mysql.connection.cursor()
            
            # Jika password lama diisi, lakukan pengecekan dan update password
            if password_lama and password_baru:
                # Ambil password lama dari database
                cur.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
                user_data = cur.fetchone()
                
                # Cek apakah password lama benar
                if user_data and check_password_hash(user_data[0], password_lama):
                    # Update dengan password baru
                    password_hash = generate_password_hash(password_baru)
                    cur.execute("UPDATE users SET username=%s, email=%s, password=%s WHERE id=%s",
                              (username, email, password_hash, session['user_id']))
                    flash('Profil dan password berhasil diperbarui!', 'success')
                else:
                    flash('Password lama tidak sesuai!', 'danger')
                    cur.close()
                    return redirect(url_for('edit_profil'))
            else:
                # Update tanpa mengubah password
                cur.execute("UPDATE users SET username=%s, email=%s WHERE id=%s",
                          (username, email, session['user_id']))
                flash('Profil berhasil diperbarui!', 'success')
            
            mysql.connection.commit()
            session['username'] = username  # Update session username
            cur.close()
            
            # Redirect berdasarkan role
            if session['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('pelanggan_dashboard'))
        
        # GET request - tampilkan form edit
        cur = mysql.connection.cursor()
        cur.execute("SELECT username, email FROM users WHERE id = %s", (session['user_id'],))
        user_data = cur.fetchone()
        cur.close()
        
        return render_template('edit_profil.html', user=user_data)
    else:
        flash('Anda harus login terlebih dahulu!', 'danger')
        return redirect(url_for('login'))

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ekstensi file yang diizinkan
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_bukti/<int:id_pesanan>', methods=['GET', 'POST'])
def upload_bukti(id_pesanan):
    if 'role' not in session or session['role'] != 'pelanggan':
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Tidak ada file yang dipilih')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('Tidak ada file yang dipilih')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Simpan nama file ke database
            cur = mysql.connection.cursor()
            cur.execute("UPDATE pesanan SET bukti_pembayaran=%s WHERE id=%s", (filename, id_pesanan))
            mysql.connection.commit()
            cur.close()

            flash('Bukti pembayaran berhasil diupload')
            return redirect(url_for('pelanggan_riwayat'))
        else:
            flash('File tidak diperbolehkan')
            return redirect(request.url)

    return render_template('pelanggan/upload.html', id_pesanan=id_pesanan)

@app.route('/pelanggan/rating', methods=['GET', 'POST'])
def pelanggan_rating():
    if 'role' in session and session['role'] == 'pelanggan':
        if request.method == 'POST':
            rating = request.form['rating']
            saran = request.form['saran']
            id_user = session['user_id']
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO rating_saran (id_user, rating, saran) VALUES (%s, %s, %s)",
                        (id_user, rating, saran))
            mysql.connection.commit()
            cur.close()
            flash('Terima kasih atas feedback Anda!')
            return redirect(url_for('pelanggan_dashboard'))
        return render_template('pelanggan/rating.html')
    return redirect(url_for('login'))

# ==== KELOLA PESANAN OLEH ADMIN =====
@app.route('/admin/pesanan')
def admin_pesanan():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT p.id, u.username, m.nama, p.jumlah, p.status, p.bukti_pembayaran
        FROM pesanan p
        JOIN users u ON p.id_user = u.id
        JOIN menu m ON p.id_menu = m.id
        ORDER BY p.created_at DESC
    """)
    pesanan = cur.fetchall()
    cur.close()
    return render_template('admin/pesanan.html', pesanan=pesanan)

@app.route('/admin/pesanan/update/<int:id>', methods=['POST'])
def update_status_pesanan(id):
    if 'role' not in session or session['role'] != 'admin':
        flash('Akses ditolak. Harap login sebagai admin.', 'danger')
        return redirect(url_for('login'))
    
    try:
        status = request.form.get('status')
        if status not in ['menunggu', 'diproses', 'selesai']:
            flash('Status tidak valid', 'danger')
            return redirect(url_for('admin_pesanan'))
        
        cur = mysql.connection.cursor()
        
        # Update status pesanan
        cur.execute(
            "UPDATE pesanan SET status = %s WHERE id = %s",
            (status, id)
        )
        mysql.connection.commit()
        
        # Dapatkan detail pesanan untuk pesan flash
        cur.execute(
            "SELECT m.nama FROM pesanan p JOIN menu m ON p.id_menu = m.id WHERE p.id = %s",
            (id,)
        )
        menu = cur.fetchone()
        menu_name = menu[0] if menu else "Pesanan"
        cur.close()
        
        flash(f'Status pesanan "{menu_name}" berhasil diubah menjadi {status}!', 'success')
    except Exception as e:
        print(f"Error updating order status: {e}")
        flash('Gagal mengupdate status pesanan', 'danger')
    
    return redirect(url_for('admin_pesanan'))

@app.context_processor
def inject_total_menunggu():
    if 'role' in session and session['role'] == 'admin':
        cur = mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) FROM pesanan WHERE status = 'menunggu'")
        total = cur.fetchone()[0]
        cur.close()
        return dict(total_menunggu=total)
    return dict(total_menunggu=0)

@app.route('/admin/laporan', methods=['GET', 'POST'])
def laporan_penjualan():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    query = """
        SELECT p.id, u.username, m.nama, p.jumlah, m.harga, (p.jumlah * m.harga) AS total, p.created_at
        FROM pesanan p
        JOIN users u ON p.id_user = u.id
        JOIN menu m ON p.id_menu = m.id
        WHERE p.status = 'selesai'
    """
    values = []

    # Filter tanggal
    if request.method == 'POST':
        tanggal_mulai = request.form['tanggal_mulai']
        tanggal_selesai = request.form['tanggal_selesai']
        if tanggal_mulai and tanggal_selesai:
            query += " AND DATE(p.created_at) BETWEEN %s AND %s"
            values.extend([tanggal_mulai, tanggal_selesai])

    query += " ORDER BY p.created_at DESC"
    cur.execute(query, tuple(values))
    laporan = cur.fetchall()

    # Hitung grand total
    grand_total = sum(row[5] for row in laporan) if laporan else 0

    cur.close()

    return render_template('admin/laporan.html', laporan=laporan, grand_total=grand_total)

@app.route('/admin/laporan/export/excel', methods=['GET'])
def export_laporan_excel():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT u.username, m.nama, p.jumlah, m.harga, (p.jumlah * m.harga) AS total, p.created_at
        FROM pesanan p
        JOIN users u ON p.id_user = u.id
        JOIN menu m ON p.id_menu = m.id
        WHERE p.status = 'selesai'
        ORDER BY p.created_at DESC
    """)
    laporan = cur.fetchall()
    cur.close()

    # Buat workbook dan sheet
    wb = Workbook()
    ws = wb.active
    ws.title = "Laporan Penjualan"

    # Header
    ws.append(["Pelanggan", "Menu", "Jumlah", "Harga", "Total", "Tanggal"])

    # Isi data
    for row in laporan:
        ws.append([
            row[0], row[1], row[2],
            float(row[3]), float(row[4]),
            row[5].strftime('%d-%m-%Y')
        ])

    # Simpan ke memori (stream)
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(output,
                     download_name="laporan_penjualan.xlsx",
                     as_attachment=True,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == '__main__':
    app.run(debug=True)