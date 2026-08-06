from flask import Flask, render_template, request, redirect, session, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import timedelta
from openai import OpenAI
import os

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "secret123")

app.permanent_session_lifetime = timedelta(days=30)

# ================= OPENAI =================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = None

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

# ================= SUPABASE DATABASE =================

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", "5432")


def get_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
        sslmode="require"
    )


# ================= CREATE TABLES =================

def create_tables():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        name VARCHAR(100),
        email VARCHAR(100) UNIQUE,
        password VARCHAR(255)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quizzes(
        id SERIAL PRIMARY KEY,
        user_email VARCHAR(100),
        quiz_code VARCHAR(100),
        title TEXT,
        description TEXT,
        questions JSONB,
        duration INTEGER,
        negative BOOLEAN,
        negativeMarks FLOAT,
        is_started BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS results(
        id SERIAL PRIMARY KEY,
        quiz_code VARCHAR(100),
        student_name VARCHAR(100),
        roll_no VARCHAR(100),
        department VARCHAR(100),
        marks FLOAT,
        total_marks FLOAT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    cursor.close()
    conn.close()


create_tables()
# ================= DATABASE HELPERS =================

def execute_query(query, values=None, fetchone=False, fetchall=False):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute(query, values)

    result = None

    if fetchone:
        result = cursor.fetchone()

    elif fetchall:
        result = cursor.fetchall()

    conn.commit()

    cursor.close()
    conn.close()

    return result


# ================= AUTH FUNCTIONS =================

def get_user_by_email(email):
    return execute_query(
        "SELECT * FROM users WHERE email=%s;",
        (email,),
        fetchone=True
    )


def create_user(name, email, password):

    execute_query(
        """
        INSERT INTO users(name,email,password)
        VALUES(%s,%s,%s);
        """,
        (name, email, password)
    )


def login_user(email, password):

    user = execute_query(
        """
        SELECT * FROM users
        WHERE email=%s
        AND password=%s;
        """,
        (email, password),
        fetchone=True
    )

    return user


# ================= QUIZ HELPERS =================

def save_quiz(
    user_email,
    quiz_code,
    title,
    description,
    questions,
    duration,
    negative,
    negativeMarks
):

    execute_query(
        """
        INSERT INTO quizzes(
            user_email,
            quiz_code,
            title,
            description,
            questions,
            duration,
            negative,
            negativeMarks
        )

        VALUES(%s,%s,%s,%s,%s,%s,%s,%s);
        """,
        (
            user_email,
            quiz_code,
            title,
            description,
            json.dumps(questions),
            duration,
            negative,
            negativeMarks
        )
    )


def get_all_quizzes(email):

    return execute_query(
        """
        SELECT *
        FROM quizzes
        WHERE user_email=%s
        ORDER BY id DESC;
        """,
        (email,),
        fetchall=True
    )


def get_quiz(quiz_code):

    quiz = execute_query(
        """
        SELECT *
        FROM quizzes
        WHERE quiz_code=%s;
        """,
        (quiz_code,),
        fetchone=True
    )

    if quiz and quiz["questions"]:
        quiz["questions"] = json.loads(quiz["questions"])

    return quiz
    # ================= AUTH ROUTES =================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["POST"])
def register():

    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({
            "success": False,
            "message": "All fields are required."
        }), 400

    existing_user = get_user_by_email(email)

    if existing_user:
        return jsonify({
            "success": False,
            "message": "Email already registered."
        }), 400

    create_user(name, email, password)

    return jsonify({
        "success": True,
        "message": "Registration successful."
    })


@app.route("/login", methods=["POST"])
def login():

    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    user = login_user(email, password)

    if not user:
        return jsonify({
            "success": False,
            "message": "Invalid email or password."
        }), 401

    session.permanent = True
    session["user"] = user["email"]
    session["name"] = user["name"]

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "user": {
            "name": user["name"],
            "email": user["email"]
        }
    })


@app.route("/logout")
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully."
    })


@app.route("/profile")
def profile():

    if "user" not in session:
        return jsonify({
            "success": False,
            "message": "Unauthorized"
        }), 401

    return jsonify({
        "success": True,
        "name": session["name"],
        "email": session["user"]
    })

# ================= QUIZ ROUTES =================

@app.route("/create-quiz", methods=["POST"])
def create_quiz():

    if "user" not in session:
        return jsonify({"success": False, "message": "Login required"}), 401

    data = request.get_json()

    quiz_code = data.get("quiz_code")
    title = data.get("title")
    description = data.get("description")
    questions = data.get("questions", [])
    duration = data.get("duration", 30)
    negative = data.get("negative", False)
    negativeMarks = data.get("negativeMarks", 0)

    save_quiz(
        session["user"],
        quiz_code,
        title,
        description,
        questions,
        duration,
        negative,
        negativeMarks
    )

    return jsonify({
        "success": True,
        "message": "Quiz created successfully."
    })


@app.route("/my-quizzes")
def my_quizzes():

    if "user" not in session:
        return jsonify({"success": False}), 401

    quizzes = get_all_quizzes(session["user"])

    return jsonify({
        "success": True,
        "quizzes": quizzes
    })


@app.route("/quiz/<quiz_code>")
def quiz(quiz_code):

    quiz = get_quiz(quiz_code)

    if not quiz:
        return jsonify({
            "success": False,
            "message": "Quiz not found."
        }), 404

    return jsonify({
        "success": True,
        "quiz": quiz
    })


@app.route("/submit-result", methods=["POST"])
def submit_result():

    data = request.get_json()

    execute_query(
        """
        INSERT INTO results(
            quiz_code,
            student_name,
            roll_no,
            department,
            marks,
            total_marks
        )
        VALUES(%s,%s,%s,%s,%s,%s);
        """,
        (
            data["quiz_code"],
            data["student_name"],
            data["roll_no"],
            data["department"],
            data["marks"],
            data["total_marks"]
        )
    )

    return jsonify({
        "success": True,
        "message": "Result submitted successfully."
    })


@app.route("/results/<quiz_code>")
def results(quiz_code):

    result = execute_query(
        """
        SELECT *
        FROM results
        WHERE quiz_code=%s
        ORDER BY id DESC;
        """,
        (quiz_code,),
        fetchall=True
    )

    return jsonify({
        "success": True,
        "results": result
    })
    # ================= HEALTH CHECK =================

@app.route("/health")
def health():
    return jsonify({
        "success": True,
        "message": "AI Quiz Creator Backend Running"
    })


# ================= 404 =================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "message": "Route not found."
    }), 404


# ================= 500 =================

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "message": "Internal server error."
    }), 500


# ================= START APP =================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
