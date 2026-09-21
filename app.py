from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)

app.secret_key = "college-notice-board-secret-key"
# ---------------------------------------------------
# FILE UPLOAD CONFIGURATION
# ---------------------------------------------------

UPLOAD_FOLDER = "uploads"

ALLOWED_EXTENSIONS = {"pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# ---------------------------------------------------
# DATABASE
# ---------------------------------------------------

DATABASE = "database.db"


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():

    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin'
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            posted_date TEXT NOT NULL,
            attachment TEXT,
            status TEXT NOT NULL DEFAULT 'published',
            created_by INTEGER,
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    """)

    admin = connection.execute(
        "SELECT * FROM users WHERE email = ?",
        ("admin@college.com",)
    ).fetchone()

    if admin is None:

        password_hash = generate_password_hash("admin123")

        connection.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
        """, (
            "College Administrator",
            "admin@college.com",
            password_hash,
            "admin"
        ))

    connection.commit()
    connection.close()


# ---------------------------------------------------
# USER LOGIN
# ---------------------------------------------------

class User(UserMixin):

    def __init__(self, user_id, name, email, password, role):

        self.id = user_id
        self.name = name
        self.email = email
        self.password = password
        self.role = role


@login_manager.user_loader
def load_user(user_id):

    connection = get_db_connection()

    user = connection.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    connection.close()

    if user:

        return User(
            user["id"],
            user["name"],
            user["email"],
            user["password"],
            user["role"]
        )

    return None


# ---------------------------------------------------
# HOME PAGE
# ---------------------------------------------------

@app.route("/")
def home():

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    connection = get_db_connection()

    query = """
        SELECT *
        FROM notices
        WHERE status = 'published'
    """

    parameters = []

    if search:
        query += """
            AND (
                title LIKE ?
                OR description LIKE ?
            )
        """

        search_value = f"%{search}%"

        parameters.extend([
            search_value,
            search_value
        ])

    if category:
        query += " AND category = ?"
        parameters.append(category)

    query += " ORDER BY id DESC"

    notices = connection.execute(
        query,
        parameters
    ).fetchall()

    connection.close()

    return render_template(
        "index.html",
        notices=notices,
        search=search,
        selected_category=category
    )


# ---------------------------------------------------
# ADMIN LOGIN
# ---------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()

        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(user["password"], password):

            logged_user = User(
                user["id"],
                user["name"],
                user["email"],
                user["password"],
                user["role"]
            )

            login_user(logged_user)

            return redirect(url_for("dashboard"))

        return """
        <h2>Invalid email or password</h2>
        <a href="/login">Try Again</a>
        """

    return render_template("login.html")


# ---------------------------------------------------
# ADMIN DASHBOARD
# ---------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    connection = get_db_connection()

    notices = connection.execute("""
        SELECT *
        FROM notices
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "dashboard.html",
        notices=notices
    )


# ---------------------------------------------------
# ADD NOTICE
# ---------------------------------------------------

@app.route("/add-notice", methods=["GET", "POST"])
@login_required
def add_notice():

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        posted_date = request.form["posted_date"]
        status = request.form["status"]

        attachment_filename = None

        # Check whether a file was uploaded
        if "attachment" in request.files:

            file = request.files["attachment"]

            if file and file.filename:

                if not allowed_file(file.filename):

                    return """
                    <h2>Invalid file type</h2>
                    <p>Only PDF files are allowed.</p>
                    <a href="/add-notice">Go Back</a>
                    """

                filename = secure_filename(file.filename)

                # Prevent filename conflicts
                base, extension = os.path.splitext(filename)

                counter = 1
                original_filename = filename

                while os.path.exists(
                    os.path.join(app.config["UPLOAD_FOLDER"], filename)
                ):

                    filename = f"{base}_{counter}{extension}"

                    counter += 1

                file.save(
                    os.path.join(
                        app.config["UPLOAD_FOLDER"],
                        filename
                    )
                )

                attachment_filename = filename

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO notices
            (title, description, category, posted_date,
             attachment, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            description,
            category,
            posted_date,
            attachment_filename,
            status,
            current_user.id
        ))

        connection.commit()
        connection.close()

        return redirect(url_for("dashboard"))

    return render_template("add_notice.html")

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        posted_date = request.form["posted_date"]
        status = request.form["status"]

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO notices
            (title, description, category, posted_date, status, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            title,
            description,
            category,
            posted_date,
            status,
            current_user.id
        ))

        connection.commit()
        connection.close()

        return redirect(url_for("dashboard"))

    return render_template("add_notice.html")

# ---------------------------------------------------
# EDIT NOTICE
# ---------------------------------------------------

@app.route("/edit-notice/<int:notice_id>", methods=["GET", "POST"])
@login_required
def edit_notice(notice_id):

    connection = get_db_connection()

    notice = connection.execute(
        "SELECT * FROM notices WHERE id = ?",
        (notice_id,)
    ).fetchone()

    if notice is None:
        connection.close()
        return "Notice not found", 404

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        posted_date = request.form["posted_date"]
        status = request.form["status"]

        connection.execute("""
            UPDATE notices
            SET title = ?,
                description = ?,
                category = ?,
                posted_date = ?,
                status = ?
            WHERE id = ?
        """, (
            title,
            description,
            category,
            posted_date,
            status,
            notice_id
        ))

        connection.commit()
        connection.close()

        return redirect(url_for("dashboard"))

    connection.close()

    return render_template(
        "edit_notice.html",
        notice=notice
    )


# ---------------------------------------------------
# DELETE NOTICE
# ---------------------------------------------------

@app.route("/delete-notice/<int:notice_id>", methods=["POST"])
@login_required
def delete_notice(notice_id):

    connection = get_db_connection()

    connection.execute(
        "DELETE FROM notices WHERE id = ?",
        (notice_id,)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("dashboard"))
# ---------------------------------------------------
# DOWNLOAD ATTACHMENT
# ---------------------------------------------------

@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )
# ---------------------------------------------------
# LOGOUT
# ---------------------------------------------------

@app.route("/logout")
@login_required
def logout():

    logout_user()

    return redirect(url_for("home"))


# ---------------------------------------------------
# START APPLICATION
# ---------------------------------------------------

if __name__ == "__main__":

    init_database()

    app.run(debug=True)