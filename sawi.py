import streamlit as st 
import pandas as pd 
import os 
import io 
import sqlite3 
from datetime import datetime 
from fpdf import FPDF 
import tempfile

def adapt_datetime(val): 
    return val.isoformat()
# ---------- FUNGSI DATABASE ----------
def init_db():
    conn = sqlite3.connect('kasir.db')
    
    # Register adapter datetime
    sqlite3.register_adapter(datetime, adapt_datetime)
    
    c = conn.cursor()
    
    # Tabel users
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    )
    ''')
    
    # Tabel produk
    c.execute('''
    CREATE TABLE IF NOT EXISTS produk (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT NOT NULL,
        harga INTEGER NOT NULL,
        stok INTEGER NOT NULL,
        gambar TEXT
    )
    ''')
    
    # Tabel riwayat transaksi
    c.execute('''
    CREATE TABLE IF NOT EXISTS riwayat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT NOT NULL,
        harga INTEGER NOT NULL,
        qty INTEGER NOT NULL,
        kasir TEXT NOT NULL,
        waktu TIMESTAMP NOT NULL,
        nota TEXT NOT NULL
    )
    ''')
    
    # Tabel nomor nota
    c.execute('''
    CREATE TABLE IF NOT EXISTS nomor_nota (
        tanggal TEXT PRIMARY KEY,
        nomor INTEGER NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()

# ---------- FUNGSI PENGELOLAAN USER ----------
def load_users():
    conn = sqlite3.connect('kasir.db')
    c = conn.cursor()
    c.execute("SELECT username, password FROM users")
    result = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return result

def save_user(username, password):
    conn = sqlite3.connect('kasir.db')
    c = conn.cursor()
    c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()
    conn.close()


# ---------- FUNGSI REGISTRASI ----------
def register():
    st.image("images/logokasir.png", width=100)
    st.title("Registrasi Akun Kasir")

    username = st.text_input("Username Baru")
    password = st.text_input("Password Baru", type="password")
    confirm_password = st.text_input("Konfirmasi Password", type="password")

    if st.button("Daftar"):
        if not username or not password or not confirm_password:
            st.error("Semua kolom harus diisi.")
        elif password != confirm_password:
            st.error("Password dan konfirmasi tidak cocok.")
        else:
            users = load_users()
            if username in users:
                st.error("Username sudah terdaftar.")
            else:
                save_user(username, password)
                st.success("Registrasi berhasil! Silakan login.")
                st.session_state.page = "login"
                st.rerun()

# ---------- FUNGSI LOGIN ----------
def login():
    st.image("images/logokasir.png", width=100)
    st.title("Login Kasir")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        users = load_users()
        if username in users and users[username] == password:
            st.success("Login berhasil!")
            st.session_state.logged_in = True
            st.session_state.username = username
            st.rerun()
        else:
            st.error("Username atau password salah.")

    if st.button("Daftar Akun Baru"):
        st.session_state.page = "register"
        st.rerun()

# ---------- FUNGSI HALAMAN KASIR ----------
def get_nomor_nota():
    conn = sqlite3.connect('kasir.db')
    c = conn.cursor()
    today = datetime.now().strftime("%d%m%y")
    
    c.execute("SELECT nomor FROM nomor_nota WHERE tanggal = ?", (today,))
    result = c.fetchone()
    
    if result is None:
        nomor = 1
        c.execute("INSERT INTO nomor_nota (tanggal, nomor) VALUES (?, ?)", (today, nomor))
    else:
        nomor = result[0] + 1
        c.execute("UPDATE nomor_nota SET nomor = ? WHERE tanggal = ?", (nomor, today))
    
    conn.commit()
    conn.close()
    
    return f"CS/{today}/{str(nomor).zfill(4)}"

# ---------- FUNGSI KASIR ----------
def halaman_kasir():
    st.subheader("🛒 Kasir")
    
    init_db()
    
    # Ambil data produk
    conn = sqlite3.connect('kasir.db')
    df = pd.read_sql_query("SELECT * FROM produk WHERE stok > 0", conn)
    conn.close()

    if "keranjang" not in st.session_state:
        st.session_state.keranjang = []

    if not df.empty:
        for i, row in df.iterrows():
            col_img, col1, col2, col3 = st.columns([1.5, 3, 2, 1])
            with col_img:
                if pd.notna(row.get("gambar", None)) and os.path.exists(row["gambar"]):
                    st.image(row["gambar"], width=60)
                else:
                    st.empty()

            with col1:
                st.markdown(f"{row['nama']}")
                st.caption(f"Rp{row['harga']:,} | Stok: {int(row['stok'])}")
   
            with col2:
                jumlah = st.number_input(f"Jumlah {row['nama']}", min_value=0, max_value=int(row["stok"]), key=f"jumlah_{i}")

            with col3:
                if st.button("Tambah", key=f"btn_{i}"):
                    if jumlah > 0:
                        st.session_state.keranjang.append((row["nama"], row["harga"], jumlah))
                        st.success(f"{row['nama']} ditambahkan!")
    else:
        st.info("Belum ada produk tersedia atau stok habis.")


    if st.session_state.keranjang:
        st.write("### Keranjang Belanja")
        total = 0
        for nama, harga, qty in st.session_state.keranjang:
            st.write(f"{nama} x {qty} = Rp{harga * qty}")
            total += harga * qty
        st.write(f"### Total: Rp{total}")

    if st.button("🧾 Cetak Struk"):
        conn = sqlite3.connect('kasir.db')
        c = conn.cursor()
        stok_kurang = False

        # Periksa stok dalam transaksi
        for nama, harga, qty in st.session_state.keranjang:
            c.execute("SELECT stok FROM produk WHERE nama = ?", (nama,))
            result = c.fetchone()
            if result and result[0] >= qty:
                c.execute("UPDATE produk SET stok = stok - ? WHERE nama = ?", (qty, nama))
            else:
                st.error(f"Stok {nama} tidak cukup!")
                stok_kurang = True
                break

        if not stok_kurang:
            conn.commit()

            now = datetime.now()
            waktu_str = now.strftime("%d %b %y %H:%M")
            nomor_nota = get_nomor_nota()

            total = sum(harga * qty for _, harga, qty in st.session_state.keranjang)

            # struk
            struk_lines = []
            struk_lines.append("         Kasir Hijau")
            struk_lines.append("=" * 30)
            struk_lines.append(f"No Nota : {nomor_nota}")
            struk_lines.append(f"Waktu   : {waktu_str}")
            struk_lines.append("-" * 30)

            for nama, harga, qty in st.session_state.keranjang:
                total_item = harga * qty
                struk_lines.append(f"{qty} {nama:<20} {total_item:>7,}".replace(",", "."))

            struk_lines.append("-" * 30)
            struk_lines.append(f"Subtotal {len(st.session_state.keranjang)} Produk    {total:>7,}".replace(",", "."))
            struk_lines.append(f"Total Tagihan            {total:>7,}".replace(",", "."))
            struk_lines.append("")
            struk_lines.append("Kartu Debit/Kredit")
            struk_lines.append(f"Total Bayar              {total:>7,}".replace(",", "."))
            struk_lines.append("=" * 30)
            struk_lines.append(f"Terbayar {waktu_str}")
            struk_lines.append("Dicetak: Kasir")

            struk = "\n".join(struk_lines)
            st.text_area("🧾 Struk Transaksi", struk, height=300)
            st.download_button("📥 Unduh Struk TXT", data=struk, file_name="struk_pembelian.txt", mime="text/plain")

            # MEMBUAT VERSI PDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Courier", size=10)
            for line in struk_lines:
                pdf.cell(0, 10, txt=line, ln=1)

            pdf_bytes = pdf.output(dest="S").encode("latin-1")
            pdf_buffer = io.BytesIO(pdf_bytes)

            st.download_button("📄 Unduh Struk PDF", data=pdf_buffer, file_name="struk_pembelian.pdf", mime="application/pdf")

            # SIMPAN RIWAYAT
            for nama, harga, qty in st.session_state.keranjang:
                c.execute("""
                    INSERT INTO riwayat (nama, harga, qty, kasir, waktu, nota)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nama, harga, qty, st.session_state.username, now, nomor_nota))
            
            conn.commit()
            st.success("Pembelian berhasil!")
            st.session_state.keranjang = []
        
        conn.close()

# ----------- RESET DATA PRODUK -------------
def reset_data():
    if st.sidebar.button("🧹 Reset Data Produk"):
        conn = sqlite3.connect('kasir.db')
        c = conn.cursor()
        c.execute("DELETE FROM produk")
        conn.commit()
        conn.close()
        st.success("Data produk berhasil direset!")

# ----------- FUNGSI TAMBAH PRODUK -------------   
def halaman_tambah_produk():
    st.title("Tambah Produk Baru")

    nama = st.text_input("Nama Produk")
    harga_str = st.text_input("Harga (contoh: 5000)")
    stok = st.number_input("Stok", min_value=0, step=1)
    gambar = st.file_uploader("Gambar Produk", type=["jpg", "jpeg", "png"])

    if st.button("Simpan"):
        try: 
            harga = int(harga_str.replace('.', '').replace(',', ''))
        except ValueError:
            st.error("Harga tidak valid. Harap isi angka seperti: 5.000")
            return
        
        # SIMPAN GAMBAR
        gambar_path = ""
        if gambar:
            os.makedirs("images/produk", exist_ok=True)
            gambar_path = f"images/produk/{nama.replace(' ', '_')}.png"
            with open(gambar_path, "wb") as f:
                f.write(gambar.read())

        # SIMPAN KE DATABASE
        conn = sqlite3.connect('kasir.db')
        c = conn.cursor()
        c.execute("""
            INSERT INTO produk (nama, harga, stok, gambar)
            VALUES (?, ?, ?, ?)
        """, (nama, harga, stok, gambar_path))
        conn.commit()
        conn.close()
        
        st.success("Produk berhasil ditambahkan!")

    
# ---------- FUNGSI HAPUS PRODUK SATUAN ----------
def hapus_produk():
    st.subheader("🗑 Hapus Produk")

    conn = sqlite3.connect('kasir.db')
    df = pd.read_sql_query("SELECT * FROM produk", conn)
    conn.close()
    
    if df.empty:
        st.info("Tidak ada produk yang tersedia.")
        return
    
    produk_list = df["nama"].tolist()
    produk_dipilih = st.selectbox("Pilih produk yang ingin dihapus:", produk_list)

    if st.button("Hapus Produk"):
        conn = sqlite3.connect('kasir.db')
        c = conn.cursor()
        c.execute("DELETE FROM produk WHERE nama = ?", (produk_dipilih,))
        conn.commit()
        conn.close()
        st.success(f"Produk '{produk_dipilih}' berhasil dihapus.")

# ---------- EDIT PRODUK -----------
def edit_produk():
    st.subheader("✏ Edit Produk")

    conn = sqlite3.connect('kasir.db')
    df = pd.read_sql_query("SELECT * FROM produk", conn)
    conn.close()
    
    if df.empty:
        st.info("Tidak ada produk untuk diedit.")
        return
    
    produk_list = df["nama"].tolist()
    produk_dipilih = st.selectbox("Pilih produk yang ingin diedit:", produk_list)

    if produk_dipilih:
        produk_row = df[df["nama"] == produk_dipilih].iloc[0]

        nama_baru = st.text_input("Nama Produk", value=produk_row["nama"])
        harga_str_baru = st.text_input("Harga (misal: 5.000)", value=f"{int(produk_row['harga']):,}".replace(",", "."))
        stok_baru = st.number_input("Stok", min_value=0, value=int(produk_row["stok"]))

        if st.button("Simpan Perubahan"):
            try:
                harga_baru = int(harga_str_baru.replace('.', '').replace(',', ''))
            except ValueError:
                st.error("Harga tidak valid. Harap isi angka seperti: 5.000")
                return

            # UPDATE DATA
            conn = sqlite3.connect('kasir.db')
            c = conn.cursor()
            c.execute("""
                UPDATE produk 
                SET nama = ?, harga = ?, stok = ? 
                WHERE nama = ?
            """, (nama_baru, harga_baru, stok_baru, produk_dipilih))
            conn.commit()
            conn.close()

            st.success(f"Produk '{produk_dipilih}' berhasil diperbarui!")

# ---------- FUNGSI LAPORAN ----------
def halaman_laporan():
    st.subheader("📊 Laporan Produk")
    
    conn = sqlite3.connect('kasir.db')
    df = pd.read_sql_query("SELECT * FROM produk", conn)
    st.dataframe(df)

    st.subheader("🧾 Riwayat Transaksi")

    # Cek apakah ada riwayat transaksi
    c = conn.cursor()
    c.execute("SELECT count(*) FROM riwayat")
    count = c.fetchone()[0]
    
    if count == 0:
        st.info("Belum ada riwayat transaksi.")
        conn.close()
        return
    
    # Ambil data riwayat
    riwayat_df = pd.read_sql_query("SELECT * FROM riwayat", conn)
    conn.close()
    
    try:
        riwayat_df["waktu"] = pd.to_datetime(riwayat_df["waktu"], format='ISO8601')
    except Exception:
        # Fallback jika format ISO8601 tidak bekerja
        try:
            riwayat_df["waktu"] = pd.to_datetime(riwayat_df["waktu"], errors='coerce')
        except Exception:
            st.error("Gagal mengkonversi format tanggal. Beberapa fitur laporan mungkin tidak berfungsi.")

    # PILIHAN FILTER
    filter_jenis = st.radio("Filter berdasarkan:", ["Harian", "Mingguan", "Bulanan"], horizontal=True)

    now = pd.Timestamp.now()
    if filter_jenis == "Harian":
        tanggal = st.date_input("Pilih Tanggal", now.date())
        filtered = riwayat_df[riwayat_df["waktu"].dt.date == tanggal]

    elif filter_jenis == "Mingguan":
        tahun = st.number_input("Tahun", value=now.year, step=1)
        minggu = st.selectbox("Pilih Minggu ke-", list(range(1, 54)), index=now.isocalendar()[1] - 1)
    
        filtered = riwayat_df[
        (riwayat_df["waktu"].dt.isocalendar().week == minggu) &
        (riwayat_df["waktu"].dt.year == tahun)
    ]

    elif filter_jenis == "Bulanan":
        bulan = st.selectbox("Pilih Bulan", list(range(1, 13)), index=now.month - 1)
        tahun = st.number_input("Tahun", value=now.year, step=1)
        filtered = riwayat_df[
        (riwayat_df["waktu"].dt.month == bulan) &
        (riwayat_df["waktu"].dt.year == tahun)
        ]
    
    if filtered.empty:
        st.warning("Tidak ada transaksi untuk periode yang dipilih.")
    else:
        st.dataframe(filtered)

    try:
        total_transaksi = (filtered["harga"] * filtered["qty"]).sum()
        jumlah_item = filtered["qty"].sum()
        jumlah_nota = filtered["nota"].nunique()

        # TAMPILAN RINGKASAN
        st.markdown("### Ringkasan:")
        
        col1, col2 = st.columns([1, 20])
        with col1:
            st.write("")
        with col2:
            st.markdown(f"• Total Penjualan: **Rp{int(total_transaksi):,}**".replace(",", "."))
            st.markdown(f"• Total Item Terjual: **{int(jumlah_item)}**")
            st.markdown(f"• Jumlah Transaksi (Nota): **{jumlah_nota}**")

        # UNDUH SEBAGAI CSV
        csv = filtered.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Unduh Laporan CSV", csv, "laporan_transaksi.csv", "text/csv")
    except Exception:
        st.error("Terjadi kesalahan dalam mengolah data laporan.")

    # Buat PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Laporan Transaksi", ln=True, align="C")

    # Tambahkan isi data
    for index, row in filtered.iterrows():
        pdf.cell(200, 10, txt=f"{row['waktu']} | {row['nota']} | {row['harga']} x {row['qty']}", ln=True)

    # Simpan ke file sementara
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                pdf.output(tmp_file.name)
    with open(tmp_file.name, "rb") as f:
            st.download_button("📄 Unduh Laporan PDF", f.read(), "laporan_transaksi.pdf", "application/pdf")
    

# ---------- FUNGSI LOGOUT ----------   
def logout():
    if st.sidebar.button("🔒 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.page = "login"
        st.rerun()

# ---------- MAIN ----------

def main(): 
    init_db()
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False 
    if 'page' not in st.session_state:
        st.session_state.page = "login"

    if st.session_state.logged_in:
        st.sidebar.image("images/logokasir.png", width=100)
        st.sidebar.markdown(f"### Halo, {st.session_state.username}")

        menu_options = {
            "Kasir": "🛒 Kasir",
            "Tambah Produk": "➕ Tambah Produk",
            "Edit Produk": "✏ Edit Produk",
            "Hapus Produk": "🗑 Hapus Produk",
            "Laporan": "📊 Laporan"
        }

        if 'menu' not in st.session_state:
            st.session_state.menu = "Kasir"

        for key, label in menu_options.items():
            if st.sidebar.button(label):
                st.session_state.menu = key
        logout()
        reset_data()

        if st.session_state.menu == "Kasir":
            halaman_kasir()
        if st.session_state.menu == "Tambah Produk":
            halaman_tambah_produk()
        elif st.session_state.menu == "Edit Produk":
            edit_produk()
        elif st.session_state.menu == "Hapus Produk":
             hapus_produk()
        elif st.session_state.menu == "Laporan":
             halaman_laporan()

    else:
        if st.session_state.page == "login":
            login()
        elif st.session_state.page == "register":
            register()

if __name__ == "__main__":
    main()
    