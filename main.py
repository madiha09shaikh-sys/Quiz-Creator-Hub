from flask import Flask, render_template, request, redirect, session, jsonify
import mysql.connector
import json
from datetime import timedelta
import requests
from openai import OpenAI

app = Flask(__name__)

app.secret_key = "secret123"

# ================= SESSION =================

app.permanent_session_lifetime = timedelta(days=30)

# ================= DATABASE =================
client = OpenAI(
    api_key="sk-xxxxxxxx"
)

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
# ================= AI GENERATE =================

@app.route("/generate-ai-quiz", methods=["POST"])
def generate_ai_quiz():

    try:

        data = request.get_json()

        topic = data.get("topic")

        count = int(data.get("count", 5))

        level = data.get("level")

        prompt = f"""
        Generate {count} UNIQUE MCQ quiz questions.

        Topic: {topic}

        Difficulty: {level}

        Rules:

        - Every question must be unique
        - No repeated questions
        - Generate 4 options
        - Only one correct answer
        - Make intelligent questions
        - Return ONLY valid JSON
        - No explanation
        - No markdown

        JSON Format:

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

        response = client.chat.completions.create(

            model="gpt-4.1-mini",

            messages=[
                {
                    "role": "system",
                    "content": "You are a professional AI quiz generator."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=1.2

        )

        text = response.choices[0].message.content

        # CLEAN RESPONSE

        text = text.replace("```json", "")

        text = text.replace("```", "")

        text = text.strip()

        # CONVERT TO JSON

        questions = json.loads(text)

        # VALIDATE QUESTIONS

        final_questions = []

        for q in questions:

            if (
                "q" in q and
                "options" in q and
                "correct" in q and
                len(q["options"]) == 4
            ):

                final_questions.append({

                    "q": q["q"],

                    "options": q["options"],

                    "correct": int(q["correct"])

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

# ================= JOIN =================



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

# ================= UPDATE QUIZ =================

@app.route("/update-quiz", methods=["POST"])
def update_quiz():

    data = request.get_json()

    code = data.get("code")

    quiz = data.get("quiz")

    questions = json.dumps(
        quiz["questions"]
    )

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
        questions,
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

# ================= DELETE QUIZ =================

@app.route("/delete-quiz", methods=["POST"])
def delete_quiz():

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

# ================= CHECK RESULT =================

@app.route("/check-result")
def check_result():

    code = request.args.get("code")

    roll = request.args.get("roll")

    conn = get_db()

    cursor = conn.cursor()

    cursor.execute("""

    SELECT id

    FROM results

    WHERE quiz_code=%s

    AND roll_no=%s

    LIMIT 1

    """, (

        code,

        roll

    ))

    result = cursor.fetchone()

    cursor.close()

    conn.close()

    return jsonify({
        "exists": True if result else False
    })

# ================= SAVE RESULT =================

@app.route("/save-result", methods=["POST"])
def save_result():

    try:

        data = request.get_json()

        code = data["code"]

        roll = data["roll"]

        conn = get_db()

        cursor = conn.cursor()

        # PREVENT SAME STUDENT AGAIN

        cursor.execute("""

        SELECT id

        FROM results

        WHERE quiz_code=%s

        AND roll_no=%s

        LIMIT 1

        """, (

            code,

            roll

        ))

        already = cursor.fetchone()

        if already:

            cursor.close()

            conn.close()

            return jsonify({

                "success": False,

                "message": "Already Attempted"

            })

        cursor.execute("""

        INSERT INTO results (

            quiz_code,

            student_name,

            roll_no,

            department,

            marks,

            total_marks

        )

        VALUES (%s,%s,%s,%s,%s,%s)

        """, (

            code,

            data["name"],

            roll,

            data["department"],

            data["marks"],

            data["total"]

        ))

        conn.commit()

        cursor.close()

        conn.close()

        return jsonify({
            "success": True
        })

    except Exception as e:

        print(e)

        return jsonify({
            "success": False
        })

# ================= RESULT PAGE =================

@app.route("/result")
def result_page():

    if "user" not in session:

        return redirect("/auth")

    code = request.args.get("code")

    conn = get_db()

    cursor = conn.cursor(dictionary=True)

    cursor.execute("""

    SELECT *

    FROM results

    WHERE quiz_code=%s

    ORDER BY marks DESC

    """, (code,))

    students = cursor.fetchall()

    cursor.close()

    conn.close()

    return render_template(

        "result.html",

        students=students,

        code=code

    )

# ================= PLAY QUIZ =================

@app.route("/play_quiz")
def play_quiz():

    code = request.args.get("code")

    return render_template(

        "play_quiz.html",

        code=code

    )

# ================= QUIZ DETAIL =================

@app.route("/quiz_detail")
def quiz_detail():

    if "user" not in session:

        return redirect("/auth")

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

        return "Quiz Not Found"

    try:

        if isinstance(quiz["questions"], str):

            quiz["questions"] = json.loads(
                quiz["questions"]
            )

    except Exception as e:

        print(e)

        quiz["questions"] = []

    return render_template(

        "quiz_detail.html",

        quiz=quiz

    )

# ================= PROFILE =================

@app.route("/profile")
def profile():

    if "user" not in session:

        return redirect("/auth")

    email = session["email"]

    conn = get_db()

    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT * FROM users
        WHERE email=%s
    """, (email,))

    user = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(*) as total
        FROM quizzes
        WHERE user_email=%s
    """, (email,))

    quiz_count = cursor.fetchone()["total"]

    cursor.close()

    conn.close()

    return render_template(

        "profile.html",

        name=user["name"],

        email=user["email"],

        quiz_count=quiz_count

    )
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

        # SESSION UPDATE
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
