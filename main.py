from flask import Flask, render_template, request, redirect, session, jsonify
import mysql.connector
import json
import requests
from datetime import timedelta

app = Flask(__name__)

app.secret_key = "secret123"

# ================= OPENAI API KEY =================

OPENAI_API_KEY = "sk-YOUR-REAL-OPENAI-KEY"

# ================= SESSION =================

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

    # USERS

    cursor.execute("""

    CREATE TABLE IF NOT EXISTS users (

        id INT AUTO_INCREMENT PRIMARY KEY,

        name VARCHAR(100),

        email VARCHAR(100) UNIQUE,

        password VARCHAR(100)

    )

    """)

    # QUIZZES

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

    # RESULTS

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

# ================= INDEX =================

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

# ================= CREATE =================

@app.route("/create")
def create():

    if "user" not in session:

        return redirect("/auth")

    return render_template("create_quiz.html")

# ================= AI GENERATE =================

@app.route("/generate-ai-quiz", methods=["POST"])
def generate_ai_quiz():

    try:

        data = request.get_json()

        topic = data.get("topic")
        count = int(data.get("count", 5))
        level = data.get("level")

        prompt = f"""
You are a professional AI Quiz Generator.

Generate {count} UNIQUE multiple choice questions about "{topic}".

Difficulty Level: {level}

IMPORTANT RULES:

1. Every question MUST be unique.
2. Questions MUST be related to the topic.
3. Each question MUST have 4 DIFFERENT options.
4. Only ONE option should be correct.
5. Wrong options should look realistic.
6. Do NOT repeat options.
7. Do NOT repeat questions.
8. Questions should feel like real exam/interview questions.
9. Return ONLY valid JSON.
10. No markdown.
11. No explanation.

JSON FORMAT:

[
  {{
    "q":"Question here",
    "options":[
      "Option 1",
      "Option 2",
      "Option 3",
      "Option 4"
    ],
    "correct":0
  }}
]
"""

        response = requests.post(

            "https://api.openai.com/v1/chat/completions",

            headers={

                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"

            },

            json={

                "model":"gpt-3.5-turbo",

                "messages":[
                    {
                        "role":"system",
                        "content":"You are an expert AI quiz generator."
                    },
                    {
                        "role":"user",
                        "content":prompt
                    }
                ],

                "temperature":0.9

            }

        )

        result = response.json()

        # ================= API ERROR =================

        if "choices" not in result:

            print(result)

            return jsonify({

                "success": False,

                "message": "OpenAI API Error"

            })

        text = result["choices"][0]["message"]["content"]

        # ================= CLEAN RESPONSE =================

        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

        questions = json.loads(text)

        # ================= FINAL CLEAN =================

        final_questions = []

        used_questions = set()

        for q in questions:

            if "q" not in q:
                continue

            if "options" not in q:
                continue

            if len(q["options"]) != 4:
                continue

            # REMOVE DUPLICATE QUESTIONS

            question_text = q["q"].strip().lower()

            if question_text in used_questions:
                continue

            used_questions.add(question_text)

            # REMOVE DUPLICATE OPTIONS

            unique_options = []

            for op in q["options"]:

                clean_op = str(op).strip()

                if clean_op not in unique_options:
                    unique_options.append(clean_op)

            if len(unique_options) != 4:
                continue

            correct_index = int(q.get("correct", 0))

            if correct_index < 0 or correct_index > 3:
                correct_index = 0

            final_questions.append({

                "q": q["q"].strip(),

                "options": unique_options,

                "correct": correct_index

            })

        return jsonify({

            "success": True,

            "questions": final_questions

        })

    except Exception as e:

        print("AI ERROR:", e)

        return jsonify({

            "success": False,

            "message": str(e)

        })

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

# ================= START QUIZ =================

@app.route("/start-quiz/<code>")
def start_quiz(code):

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

# ================= STOP QUIZ =================

@app.route("/stop-quiz/<code>")
def stop_quiz(code):

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

# ================= UPDATE PROFILE =================

@app.route("/update-profile", methods=["POST"])
def update_profile():

    if "email" not in session:
        return jsonify({
            "success": False
        })

    try:

        data = request.get_json()

        new_name = data.get("name")

        conn = get_db()

        cursor = conn.cursor()

        cursor.execute("""

        UPDATE users
        SET name=%s
        WHERE email=%s

        """, (

            new_name,
            session["email"]

        ))

        conn.commit()

        cursor.close()
        conn.close()

        session["user"] = new_name

        return jsonify({
            "success": True
        })

    except Exception as e:

        print(e)

        return jsonify({
            "success": False
        })

# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/auth")

# ================= RUN =================

if __name__ == "__main__":

    app.run(debug=True)
