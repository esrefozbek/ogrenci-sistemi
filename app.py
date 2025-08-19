


from flask import Flask, render_template, request, redirect, send_file
import csv
import io
import sqlite3
from werkzeug.utils import secure_filename
import os
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash




app = Flask(__name__)
app.secret_key = "supersecretkey123"  # Flask oturum yönetimi için gerekli

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login" # type: ignore



def db_baglanti():
    conn = sqlite3.connect("ogrenci.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def kullanici_tablosu_olustur():
    conn = sqlite3.connect("ogrenci.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kullanicilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            sifre TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ogrenciler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            soyad TEXT NOT NULL,
            numara TEXT UNIQUE NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alinan_dersler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ogrenci_id INTEGER NOT NULL,
            ders_adi TEXT NOT NULL,
            ogretmen_adi TEXT NOT NULL,
            FOREIGN KEY (ogrenci_id) REFERENCES ogrenciler(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


class Kullanici(UserMixin):
    def __init__(self, id, username, sifre_hash):
        self.id = id
        self.username = username
        self.sifre_hash = sifre_hash

    @staticmethod
    def get(user_id):
        conn = db_baglanti()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM kullanicilar WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        print(row["sifre"])  # hash düzgün görünüyor mu?
        conn.close()
        if row:
            return Kullanici(row["id"], row["username"], row["sifre"])
        return None


@login_manager.user_loader
def load_user(user_id):
    return Kullanici.get(user_id)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        sifre_hash = generate_password_hash(password)

        conn = db_baglanti()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO kullanicilar (username, sifre) VALUES (?, ?)",
                           (username, sifre_hash))
            conn.commit()
        except sqlite3.IntegrityError:
            return "⚠️ Bu kullanıcı adı zaten kullanılıyor!"
        conn.close()
        return redirect("/login")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = db_baglanti()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM kullanicilar WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()

        if row and check_password_hash(row["sifre"], password):
            user = Kullanici(row["id"], row["username"], row["sifre"])
            login_user(user)
            return redirect("/")
        else:
            return "Kullanıcı adı veya şifre yanlış!"
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")


@app.route("/")
@login_required
def index():
    arama = request.args.get("q", "")  # URL'den ?q=... parametresi
    conn = db_baglanti()
    cursor = conn.cursor()

    if arama:
        cursor.execute("""
            SELECT o.id AS ogrenci_id, o.ad, o.soyad, o.numara,
                   d.id AS ders_id, d.ders_adi, d.ogretmen_adi
            FROM ogrenciler o
            LEFT JOIN alinan_dersler d ON o.id = d.ogrenci_id
            WHERE o.ad LIKE ? OR o.soyad LIKE ? OR o.numara LIKE ?
        """, (f"%{arama}%", f"%{arama}%", f"%{arama}%"))
    else:
        cursor.execute("""
            SELECT o.id AS ogrenci_id, o.ad, o.soyad, o.numara,
                   d.id AS ders_id, d.ders_adi, d.ogretmen_adi
            FROM ogrenciler o
            LEFT JOIN alinan_dersler d ON o.id = d.ogrenci_id
        """)

    veriler = cursor.fetchall()
    conn.close()
    return render_template("index.html", veriler=veriler, arama=arama)


@app.route("/ogrenci-ekle", methods=["GET", "POST"])
@login_required
def ogrenci_ekle():
    if request.method == "POST":
        ad = request.form["ad"]
        soyad = request.form["soyad"]
        numara = request.form["numara"]

        conn = db_baglanti()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO ogrenciler (ad, soyad, numara) VALUES (?, ?, ?)",
                           (ad, soyad, numara))
            conn.commit()
        except sqlite3.IntegrityError:
            return "⚠️ Bu numara zaten var!"
        conn.close()
        return redirect("/")
    return render_template("ogrenci_ekle.html")


@app.route("/ders-ekle", methods=["GET", "POST"])
@login_required
def ders_ekle():
    conn = db_baglanti()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ad, soyad FROM ogrenciler")
    ogrenciler = cursor.fetchall()

    if request.method == "POST":
        ogr_id = request.form["ogrenci_id"]
        ders_adi = request.form["ders_adi"]
        ogretmen_adi = request.form["ogretmen_adi"]

        cursor.execute("""
            INSERT INTO alinan_dersler (ogrenci_id, ders_adi, ogretmen_adi)
            VALUES (?, ?, ?)
        """, (ogr_id, ders_adi, ogretmen_adi))
        conn.commit()
        conn.close()
        return redirect("/")

    conn.close()
    return render_template("ders_ekle.html", ogrenciler=ogrenciler)


@app.route("/ogrenci-sil/<int:ogr_id>")
@login_required
def ogrenci_sil(ogr_id):
    conn = db_baglanti()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ogrenciler WHERE id = ?", (ogr_id,))
    conn.commit()
    conn.close()
    return redirect("/")


@app.route("/ders-sil/<int:ders_id>")
@login_required
def ders_sil(ders_id):
    conn = db_baglanti()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alinan_dersler WHERE id = ?", (ders_id,))
    conn.commit()
    conn.close()
    return redirect("/")


@app.route("/ogrenci-guncelle/<int:ogr_id>", methods=["GET", "POST"])
@login_required
def ogrenci_guncelle(ogr_id):
    conn = db_baglanti()
    cursor = conn.cursor()

    if request.method == "POST":
        ad = request.form["ad"]
        soyad = request.form["soyad"]
        numara = request.form["numara"]
        cursor.execute("UPDATE ogrenciler SET ad = ?, soyad = ?, numara = ? WHERE id = ?",
                       (ad, soyad, numara, ogr_id))
        conn.commit()
        conn.close()
        return redirect("/")

    cursor.execute("SELECT * FROM ogrenciler WHERE id = ?", (ogr_id,))
    ogrenci = cursor.fetchone()
    conn.close()
    return render_template("ogrenci_guncelle.html", ogrenci=ogrenci)


@app.route("/ders-guncelle/<int:ders_id>", methods=["GET", "POST"])
@login_required
def ders_guncelle(ders_id):
    conn = db_baglanti()
    cursor = conn.cursor()

    if request.method == "POST":
        ders_adi = request.form["ders_adi"]
        ogretmen_adi = request.form["ogretmen_adi"]
        cursor.execute("UPDATE alinan_dersler SET ders_adi = ?, ogretmen_adi = ? WHERE id = ?",
                       (ders_adi, ogretmen_adi, ders_id))
        conn.commit()
        conn.close()
        return redirect("/")

    cursor.execute("SELECT * FROM alinan_dersler WHERE id = ?", (ders_id,))
    ders = cursor.fetchone()
    conn.close()
    return render_template("ders_guncelle.html", ders=ders)


@app.route("/csv-export")
@login_required
def csv_export():
    conn = db_baglanti()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.ad, o.soyad, o.numara, d.ders_adi, d.ogretmen_adi
        FROM ogrenciler o
        LEFT JOIN alinan_dersler d ON o.id = d.ogrenci_id
    """)
    veriler = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ad", "Soyad", "Numara", "Ders Adı", "Öğretmen Adı"])  # Başlıklar

    for row in veriler:
        writer.writerow([row["ad"], row["soyad"], row["numara"],
                         row["ders_adi"] or "", row["ogretmen_adi"] or ""])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="ogrenciler_ve_dersler.csv"
    )



@app.route("/csv-import", methods=["GET", "POST"])
@login_required
def csv_import():
    if request.method == "POST":
        file = request.files.get("file")

        if not file or not file.filename.endswith(".csv"):
            return "⚠️ Lütfen geçerli bir CSV dosyası yükleyin."

        stream = io.StringIO(file.stream.read().decode("utf-8"))
        reader = csv.DictReader(stream)

        conn = db_baglanti()
        cursor = conn.cursor()

        for row in reader:
            ad = row.get("Ad")
            soyad = row.get("Soyad")
            numara = row.get("Numara")
            ders_adi = row.get("Ders Adı")
            ogretmen_adi = row.get("Öğretmen Adı")

            # Öğrenci var mı kontrolü
            cursor.execute("SELECT id FROM ogrenciler WHERE numara = ?", (numara,))
            existing = cursor.fetchone()

            if existing:
                ogrenci_id = existing["id"]
            else:
                try:
                    cursor.execute(
                        "INSERT INTO ogrenciler (ad, soyad, numara) VALUES (?, ?, ?)",
                        (ad, soyad, numara)
                    )
                    ogrenci_id = cursor.lastrowid
                except sqlite3.IntegrityError:
                    continue  # Hatalı satırı atla

            # Ders bilgisi varsa ekle
            if ders_adi and ogretmen_adi:
                cursor.execute(
                    "INSERT INTO alinan_dersler (ogrenci_id, ders_adi, ogretmen_adi) VALUES (?, ?, ?)",
                    (ogrenci_id, ders_adi, ogretmen_adi)
                )

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("csv_import.html")










if __name__ == "__main__":
    kullanici_tablosu_olustur()
    app.run(debug=True)

