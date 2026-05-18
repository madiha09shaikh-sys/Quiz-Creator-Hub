from flask import Flask, render_template, request, redirect, session, jsonify
import mysql.connector
import json
from datetime import timedelta

app = Flask(__name__)

app.secret_key = "secret123"

# ================= SESSION LOGIN =================

app.permanent_session_lifetime = timedelta(days=30)

# ================= DATABASE =================

def get_db():

    return mysql.connector.connect(

        host="tramway.proxy.rlwy.net",

        user="root",

        password="aqrFUhLfxYapyZzojaZaqZlmpsuOAkld",

        database="railway",

        port=37240,

        connection_timeout=60,

        autocommit=True

    )

# ================= CREATE TABLES =================

def create_tables():

    conn = get_db()

    cursor = conn.cursor()

    # USERS TABLE

    cursor.execute("""

    CREATE TABLE IF NOT EXISTS users (

        id INT AUTO_INCREMENT PRIMARY KEY,

        name VARCHAR(100),

        email VARCHAR(100) UNIQUE,

        password VARCHAR(100)

    )

    """)

    # QUIZZES TABLE

    cursor.execute("""

    CREATE TABLE IF NOT EXISTS quizzes (

        id INT AUTO_INCREMENT PRIMARY KEY,

        user_email VARCHAR(100),

        quiz_code VARCHAR(100),

        title VARCHAR(255),

        description TEXT,

        questions LONGTEXT,

        duration INT,

        negative BOOLEAN,

        negativeMarks FLOAT,

        is_started BOOLEAN DEFAULT FALSE,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )

    """)

    # RESULTS TABLE

    cursor.execute("""

    CREATE TABLE IF NOT EXISTS results (

        id INT AUTO_INCREMENT PRIMARY KEY,

        quiz_code VARCHAR(100),

        student_name VARCHAR(100),

        roll_no VARCHAR(100),

        department VARCHAR(100),

        marks FLOAT,

        total_marks FLOAT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

    )

    """)

    conn.commit()

    cursor.close()

    conn.close()

create_tables()

# ================= INDEX PAGE =================

@app.route("/")
def index():

    if "user" in session:

        return redirect("/home")

    return render_template("index.html")

# ================= AUTH =================

@app.route("/auth", methods=["GET", "POST"])
def auth():

    if "user" in session:

        return redirect("/home")

    msg = ""

    if request.method == "POST":

        form_type = request.form["form_type"]

        # REGISTER

        if form_type == "register":

            name = request.form["name"]

            email = request.form["email"]

            password = request.form["password"]

            try:

                conn = get_db()

                cursor = conn.cursor()

                cursor.execute("""

                INSERT INTO users (

                    name,

                    email,

                    password

                )

                VALUES (%s,%s,%s)

                """, (

                    name,

                    email,

                    password

                ))

                conn.commit()

                msg = "Registered Successfully"

            except:

                msg = "Email already exists"

            finally:

                cursor.close()

                conn.close()

        # LOGIN

        elif form_type == "login":

            email = request.form["email"]

            password = request.form["password"]

            conn = get_db()

            cursor = conn.cursor()

            cursor.execute("""

            SELECT *

            FROM users

            WHERE email=%s

            AND password=%s

            """, (

                email,

                password

            ))

            user = cursor.fetchone()

            cursor.close()

            conn.close()

            if user:

                session.permanent = True

                session["user"] = user[1]

                session["email"] = user[2]

                return redirect("/home")

            else:

                msg = "Invalid Login"

    return render_template(

        "auth.html",

        msg=msg

    )

# ================= HOME =================

@app.route("/home")
def home():

    if "user" not in session:

        return redirect("/auth")

    conn = get_db()

    cursor = conn.cursor(dictionary=True)

    cursor.execute("""

    SELECT *

    FROM quizzes

    WHERE user_email=%s

    ORDER BY id DESC

    """, (session["email"],))

    quizzes = cursor.fetchall()

    cursor.close()

    conn.close()

    return render_template(

        "home.html",

        user=session["user"],

        quizzes=quizzes

    )

# ================= CREATE PAGE =================

@app.route("/create")
def create():

    if "user" not in session:

        return redirect("/auth")

    return render_template("create_quiz.html")

# ================= JOIN PAGE =================

@app.route("/join")
def join():

    if "user" not in session:

        return redirect("/auth")

    return render_template("join_quiz.html")

# ================= SAVE QUIZ =================

@app.route("/save-quiz", methods=["POST"])
def save_quiz():

    if "email" not in session:

        return jsonify({
            "success": False
        })

    data = request.get_json()

    code = data.get("code")

    title = data.get("title")

    description = data.get("description")

    questions = json.dumps(
        data.get("questions")
    )

    duration = data.get("duration")

    negative = data.get("negative")

    negativeMarks = data.get("negativeMarks")

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""

    INSERT INTO quizzes (

        user_email,

        quiz_code,

        title,

        description,

        questions,

        duration,

        negative,

        negativeMarks,

        is_started

    )

    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)

    """, (

        session["email"],

        code,

        title,

        description,

        questions,

        duration,

        negative,

        negativeMarks,

        False

    ))

    conn.commit()

    cursor.close()

    conn.close()

    return jsonify({
        "success": True
    })

# ================= GET QUIZ =================

@app.route("/get-quiz")
def get_quiz():

    code = request.args.get("code")

    conn = get_db()

    cursor = conn.cursor(dictionary=True)

    cursor.execute("""

    SELECT *

    FROM quizzes

    WHERE quiz_code=%s

    """, (code,))

    quiz = cursor.fetchone()

    cursor.close()

    conn.close()

    if not quiz:

        return jsonify({

            "success": False,

            "message": "Quiz not found"

        })

    try:

        if isinstance(quiz["questions"], str):

            quiz["questions"] = json.loads(
                quiz["questions"]
            )

        if quiz["questions"] is None:

            quiz["questions"] = []

    except Exception as e:

        print(e)

        quiz["questions"] = []

    return jsonify({

        "success": True,

        "quiz": {

            "id": quiz["id"],

            "quiz_code": quiz["quiz_code"],

            "title": quiz["title"],

            "description": quiz["description"],

            "questions": quiz["questions"],

            "duration": quiz["duration"],

            "negative": quiz["negative"],

            "negativeMarks": quiz["negativeMarks"],

            "is_started": quiz["is_started"]

        }

    })

# ================= UPDATE QUIZ =================

@app.route("/update-quiz", methods=["POST"])
def update_quiz():

    try:

        data = request.get_json()

        code = data.get("code")

        quiz = data.get("quiz")

        conn = get_db()

        cursor = conn.cursor()

        cursor.execute("""

        UPDATE quizzes

        SET

            title=%s,

            description=%s,

            questions=%s,

            duration=%s,

            negative=%s,

            negativeMarks=%s

        WHERE quiz_code=%s

        """, (

            quiz["title"],

            quiz["description"],

            json.dumps(quiz["questions"]),

            quiz["duration"],

            quiz["negative"],

            quiz["negativeMarks"],

            code

        ))

        conn.commit()

        cursor.close()

        conn.close()

        return jsonify({
            "success": True
        })

    except Exception as e:

        print("UPDATE ERROR:", e)

        return jsonify({
            "success": False
        })

# ================= START QUIZ =================

@app.route("/start-quiz", methods=["POST"])
def start_quiz():

    try:

        data = request.get_json()

        code = data.get("code")

        conn = get_db()

        cursor = conn.cursor()

        cursor.execute("""

        UPDATE quizzes

        SET is_started=TRUE

        WHERE quiz_code=%s

        """, (code,))

        conn.commit()

        cursor.close()

        conn.close()

        return jsonify({
            "success": True
        })

    except Exception as e:

        print("START ERROR:", e)

        return jsonify({
            "success": False
        })

# ================= STOP QUIZ =================

@app.route("/stop-quiz", methods=["POST"])
def stop_quiz():

    try:

        data = request.get_json()

        code = data.get("code")

        conn = get_db()

        cursor = conn.cursor()

        cursor.execute("""

        UPDATE quizzes

        SET is_started=FALSE

        WHERE quiz_code=%s

        """, (code,))

        conn.commit()

        cursor.close()

        conn.close()

        return jsonify({
            "success": True
        })

    except Exception as e:

        print("STOP ERROR:", e)

        return jsonify({
            "success": False
        })

# ================= DELETE QUIZ =================

@app.route("/delete-quiz", methods=["POST"])
def delete_quiz():

    try:

        data = request.get_json()

        code = data.get("code")

        conn = get_db()

        cursor = conn.cursor()

        cursor.execute("""

        DELETE FROM quizzes

        WHERE quiz_code=%s

        """, (code,))

        conn.commit()

        cursor.close()

        conn.close()

        return jsonify({
            "success": True
        })

    except Exception as e:

        print("DELETE ERROR:", e)

        return jsonify({
            "success": False
        })

# ================= PLAY QUIZ =================

@app.route("/play_quiz")
def play_quiz():

    code = request.args.get("code")

    return render_template(

        "play_quiz.html",

        code=code

    )

# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/auth")

# ================= RUN =================

if __name__ == "__main__":

    app.run(debug=True)
