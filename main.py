from flask import Flask, render_template, request, session, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import json
from datetime import timedelta
from openai import OpenAI
import os


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "secret123")

app.permanent_session_lifetime = timedelta(days=30)


# =========================================================
# OPENAI
# =========================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = None

if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# SUPABASE DATABASE
# =========================================================
#
# Railway Variables mein ye variable add karna hai:
#
# DATABASE_URL
#
# Example:
# postgresql://postgres.xxxxx:password@aws-xxxxx.pooler.supabase.com:5432/postgres
#
# Password yahan code mein mat likhna.
#


DATABASE_URL = os.getenv("DATABASE_URL")


def get_db():

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is not configured."
        )

    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require"
    )


# =========================================================
# DATABASE TABLES
# =========================================================
#
# Tables already Supabase mein create hain:
#
# users
# quizzes
# results
#
# Isliye Railway startup par CREATE TABLE nahi kar rahe.
#
# Agar future mein tables automatically create karne ho
# to create_tables() function ko manually call kar sakte ho.
#


def create_tables():

    conn = get_db()

    try:

        cursor = conn.cursor()

        # USERS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id SERIAL PRIMARY KEY,
                name VARCHAR(100),
                email VARCHAR(100) UNIQUE,
                password VARCHAR(255)
            );
        """)

        # QUIZZES
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

        # RESULTS
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

    finally:

        conn.close()


# =========================================================
# DATABASE HELPER
# =========================================================


def execute_query(
    query,
    values=None,
    fetchone=False,
    fetchall=False
):

    conn = get_db()

    try:

        cursor = conn.cursor(
            cursor_factory=RealDictCursor
        )

        cursor.execute(query, values)

        result = None

        if fetchone:
            result = cursor.fetchone()

        elif fetchall:
            result = cursor.fetchall()

        conn.commit()

        cursor.close()

        return result

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# =========================================================
# AUTH FUNCTIONS
# =========================================================


def get_user_by_email(email):

    return execute_query(
        """
        SELECT *
        FROM users
        WHERE email = %s;
        """,
        (email,),
        fetchone=True
    )


def create_user(
    name,
    email,
    password
):

    execute_query(
        """
        INSERT INTO users(
            name,
            email,
            password
        )
        VALUES(
            %s,
            %s,
            %s
        );
        """,
        (
            name,
            email,
            password
        )
    )


def login_user(
    email,
    password
):

    return execute_query(
        """
        SELECT *
        FROM users
        WHERE email = %s
        AND password = %s;
        """,
        (
            email,
            password
        ),
        fetchone=True
    )


# =========================================================
# QUIZ FUNCTIONS
# =========================================================


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
            negativemarks
        )
        VALUES(
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        );
        """,
        (
            user_email,
            quiz_code,
            title,
            description,
            Json(questions),
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
        WHERE user_email = %s
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
        WHERE quiz_code = %s;
        """,
        (quiz_code,),
        fetchone=True
    )

    if quiz and quiz.get("questions"):

        if isinstance(
            quiz["questions"],
            str
        ):

            try:

                quiz["questions"] = json.loads(
                    quiz["questions"]
                )

            except json.JSONDecodeError:

                quiz["questions"] = []

    return quiz


# =========================================================
# HOME
# =========================================================


@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# REGISTER
# =========================================================


@app.route(
    "/register",
    methods=["POST"]
)
def register():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "Invalid request data."
            }), 400

        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        if not name or not email or not password:

            return jsonify({
                "success": False,
                "message": "All fields are required."
            }), 400

        email = email.strip().lower()

        existing_user = get_user_by_email(
            email
        )

        if existing_user:

            return jsonify({
                "success": False,
                "message": "Email already registered."
            }), 400

        create_user(
            name,
            email,
            password
        )

        return jsonify({
            "success": True,
            "message": "Registration successful."
        })

    except Exception as e:

        print(
            "REGISTER ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": "Registration failed.",
            "error": str(e)
        }), 500


# =========================================================
# LOGIN
# =========================================================


@app.route(
    "/login",
    methods=["POST"]
)
def login():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "Invalid request data."
            }), 400

        email = data.get("email")
        password = data.get("password")

        if not email or not password:

            return jsonify({
                "success": False,
                "message": "Email and password are required."
            }), 400

        email = email.strip().lower()

        user = login_user(
            email,
            password
        )

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

    except Exception as e:

        print(
            "LOGIN ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": "Login failed.",
            "error": str(e)
        }), 500


# =========================================================
# LOGOUT
# =========================================================


@app.route("/logout")
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully."
    })


# =========================================================
# PROFILE
# =========================================================


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


# =========================================================
# CREATE QUIZ
# =========================================================


@app.route(
    "/create-quiz",
    methods=["POST"]
)
def create_quiz():

    try:

        if "user" not in session:

            return jsonify({
                "success": False,
                "message": "Login required"
            }), 401

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "Invalid quiz data."
            }), 400

        quiz_code = data.get(
            "quiz_code"
        )

        title = data.get(
            "title"
        )

        description = data.get(
            "description",
            ""
        )

        questions = data.get(
            "questions",
            []
        )

        duration = data.get(
            "duration",
            30
        )

        negative = data.get(
            "negative",
            False
        )

        negativeMarks = data.get(
            "negativeMarks",
            0
        )

        if not quiz_code:

            return jsonify({
                "success": False,
                "message": "Quiz code is required."
            }), 400

        if not title:

            return jsonify({
                "success": False,
                "message": "Quiz title is required."
            }), 400

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
            "message": "Quiz created successfully.",
            "quiz_code": quiz_code
        })

    except Exception as e:

        print(
            "CREATE QUIZ ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": "Quiz creation failed.",
            "error": str(e)
        }), 500


# =========================================================
# MY QUIZZES
# =========================================================


@app.route("/my-quizzes")
def my_quizzes():

    try:

        if "user" not in session:

            return jsonify({
                "success": False,
                "message": "Login required."
            }), 401

        quizzes = get_all_quizzes(
            session["user"]
        )

        return jsonify({
            "success": True,
            "quizzes": quizzes
        })

    except Exception as e:

        print(
            "MY QUIZZES ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": "Unable to load quizzes.",
            "error": str(e)
        }), 500


# =========================================================
# GET QUIZ
# =========================================================


@app.route(
    "/quiz/<quiz_code>"
)
def quiz(quiz_code):

    try:

        quiz_data = get_quiz(
            quiz_code
        )

        if not quiz_data:

            return jsonify({
                "success": False,
                "message": "Quiz not found."
            }), 404

        return jsonify({
            "success": True,
            "quiz": quiz_data
        })

    except Exception as e:

        print(
            "GET QUIZ ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": "Unable to load quiz.",
            "error": str(e)
        }), 500


# =========================================================
# START QUIZ
# =========================================================


@app.route(
    "/start-quiz/<quiz_code>",
    methods=["POST"]
)
def start_quiz(quiz_code):

    try:

        quiz_data = get_quiz(
            quiz_code
        )

        if not quiz_data:

            return jsonify({
                "success": False,
                "message": "Quiz not found."
            }), 404

        execute_query(
            """
            UPDATE quizzes
            SET is_started = TRUE
            WHERE quiz_code = %s;
            """,
            (quiz_code,)
        )

        return jsonify({
            "success": True,
            "message": "Quiz started successfully."
        })

    except Exception as e:

        print(
            "START QUIZ ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": "Unable to start quiz.",
            "error": str(e)
        }), 500


# =========================================================
# SUBMIT RESULT
# =========================================================


@app.route(
    "/submit-result",
    methods=["POST"]
)
def submit_result():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "success": False,
                "message": "Invalid result data."
            }), 400

        required_fields = [
            "quiz_code",
            "student_name",
            "roll_no",
            "department",
            "marks",
            "total_marks"
        ]

        for field in required_fields:

            if field not in data:

                return jsonify({
                    "success": False,
                    "message": f"{field} is required."
                }), 400

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
            VALUES(
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            );
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

    except Exception as e:

        print(
            "SUBMIT RESULT ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": "Result submission failed.",
            "error": str(e)
        }), 500


# =========================================================
# GET RESULTS
# =========================================================


@app.route(
    "/results/<quiz_code>"
)
def results(quiz_code):

    try:

        result = execute_query(
            """
            SELECT *
            FROM results
            WHERE quiz_code = %s
            ORDER BY id DESC;
            """,
            (quiz_code,),
            fetchall=True
        )

        return jsonify({
            "success": True,
            "results": result
        })

    except Exception as e:

        print(
            "RESULTS ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": "Unable to load results.",
            "error": str(e)
        }), 500


# =========================================================
# HEALTH CHECK
# =========================================================


@app.route("/health")
def health():

    try:

        conn = get_db()

        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1;"
        )

        cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "message": "AI Quiz Creator Backend Running",
            "database": "Supabase Connected"
        })

    except Exception as e:

        print(
            "HEALTH DATABASE ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": "Backend running but database connection failed.",
            "database": "Disconnected",
            "error": str(e)
        }), 500


# =========================================================
# 404 ERROR
# =========================================================


@app.errorhandler(404)
def not_found(error):

    return jsonify({
        "success": False,
        "message": "Route not found."
    }), 404


# =========================================================
# 500 ERROR
# =========================================================


@app.errorhandler(500)
def internal_error(error):

    return jsonify({
        "success": False,
        "message": "Internal server error."
    }), 500


# =========================================================
# START APP
# =========================================================


if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )
